"""판정과 검출: 글 하나가 광고인지(classify), 요소 하나에서 어떤 기법의 검출이 나오는지,
프레임 하나와 그 안의 iframe 을 재귀로 훑어 검출을 모으는 방법(walk_frame).
"""
import re
from scan_control import check_cancelled
from scan_exclusions import ScanExclusions

import attachments as attach_mod
import evidence as evidence_mod
import lexicon
from judgement import judge
from extract_extra_js import BLOCK_SELECTORS, EXTRACT_EXTRA
from extract_js import EXTRACT
from normalize import (deleet_all, describe_homoglyph, describe_jamo, has_homoglyph,
                       disguised_chars, hangul_alts, has_jamo_obfuscation, normalize, ZERO_WIDTH)
from selector_js import BUILD_SELECTOR
from visibility_js import VISIBILITY_HELPERS
from urls import page_key
from browser import pdf_viewer_frame


# 자식 iframe 요소 하나에 대해 (절대 src, 그 src 가 문서에서 유일한가, 유일하지 않을 때의 선택자)를
# 한 번의 왕복으로 구한다. iframe 마다 frame_element·get_property·json_value·개수 세기로 네 번 오가던 것을 줄였다.
FRAME_STEP_JS = "(el) => {" + BUILD_SELECTOR + VISIBILITY_HELPERS + """
  const up = n => n.parentElement || (n.getRootNode && n.getRootNode().host) || null;
  // src="" 인 iframe(메일 전송용 숨은 틀 등)의 el.src 는 페이지 자기 주소다. 속성이 비었으면 주소가 없는 것이다
  const s = (el.getAttribute('src') || '').trim() ? (el.src || '') : '';
  const unique = !!s && !s.includes('"') &&
    Array.from(document.querySelectorAll('iframe')).filter((f) => (f.src || '') === s).length === 1;
  // iframe 자체가 바깥 페이지에서 숨겨졌는가. 안쪽 글은 iframe 안에서는 보이는 글이라 따로 알려 줘야 한다
  const cs = getComputedStyle(el), r = el.getBoundingClientRect();
  const hidden = {transparent:false, offscreen:false, reasons:[]};
  let reason = null, alpha = 1;
  for (let n = el; n; n = up(n)) {
    const style = getComputedStyle(n);
    alpha *= Number(style.opacity) * filterOpacity(style.filter);
    if (clipPathZero(style.clipPath, n.getBoundingClientRect()) || clipRectZero(style))
      reason = 'clip 영역 0';
    if (style.contentVisibility === 'hidden') reason = 'content-visibility:hidden';
  }
  if (alpha <= 0.05) { hidden.transparent = true; hidden.reasons.push('iframe opacity:0'); }
  if (!el.getClientRects().length) reason = 'display:none';
  else if (cs.visibility === 'hidden' || cs.visibility === 'collapse') reason = 'visibility:hidden';
  else if (r.width <= 1 || r.height <= 1) reason = '크기 ' + Math.round(r.width) + 'x' + Math.round(r.height);
  else if (r.right + scrollX <= 0 || r.bottom + scrollY <= 0 || r.left < -1000 || r.top < -1000)
    reason = '화면 밖 좌표 left:' + Math.round(r.left) + 'px';
  else if (clippedByAncestor(el, r)) reason = '상위 요소 overflow:hidden 영역 밖';
  if (reason) { hidden.offscreen = true; hidden.reasons.push(reason); }
  return { src: s, unique, selector: unique ? null : buildSelector(el), hidden };
}"""


# 숨긴 글 추출(EXTRACT)과 추가 유형 추출(EXTRACT_EXTRA)을 한 번의 왕복으로 한다 (왕복 한 번이 수 ms 다).
# 둘 다 DOM 을 읽기만 하므로 순서대로 붙여 실행해도 따로 부를 때와 결과가 같다. 추가 유형이 실패하면 null.
EXTRACT_BOTH = ("(primaryOnly) => { const nodes = (" + EXTRACT + ")(); let extra = null; try { extra = ("
                + EXTRACT_EXTRA + ")({extra: !primaryOnly}); } catch (e) {} return [nodes, extra]; }")
# EXTRACT 가 비워 둔 선택자를, 광고로 판정된 항목 번호에만 만든다 (extract_js.py 의 targets)
NODE_SELECTORS = ("(ids) => {" + BUILD_SELECTOR + """
  const targets = window.__hwonhiTargets || [];
  return ids.map(i => targets[i] ? buildSelector(targets[i]) : null);
}""")


def frame_step(parent, child):
    """부모 프레임에서 자식 iframe을 가리키는 location 조각을 만든다.

    요강은 src가 상대경로여도 절대주소로 적도록 요구한다.
    같은 src의 iframe이 여럿이거나 src가 없으면(스크립트로 채운 iframe) 일반 요소처럼
    유일한 선택자를 만든다. 문서 전체 순번을 :nth-of-type 에 넣으면, iframe 들이 서로 다른
    부모 안에 있을 때 아무것도 못 가리키거나 여럿을 가리킨다 (nth-of-type 은 형제 사이 순번).
    """
    info = parent.evaluate(FRAME_STEP_JS, child.frame_element())
    hidden = info.get("hidden")
    if info["unique"]:
        return f'iframe[src="{info["src"]}"]', info["src"], hidden
    return info["selector"], info["src"], hidden


VISIBLE_CODE = "VISIBLE_AD(게시판 노출 광고)"
VISIBLE_GUIDE = ("게시글·댓글을 삭제하고 작성자(아이피)를 차단합니다. 같은 문구가 반복해 올라오면 "
                 "자동 등록 방지(캡차)와 금칙어 필터에 이 문구의 연락처·핵심어를 추가합니다.")
_BOARDISH = re.compile(r"(board|bbs|visit|guest|comment|reply|cmt|view|article|post|content|"
                       r"subject|title|notice|qna|free)", re.I)


def visible_findings(frame, prefix, url, texts, reported):
    """화면에 그대로 보이는 광고 글. 숨긴 광고(주요 4종)와 겹치는 글은 빼고 보고한다."""
    picked = []
    for t in texts:
        text = t["text"]
        verdict = classify(text, strict=True, context=(t.get('context') or {}).get('kind'))
        if verdict["is_ad"] or verdict.get("review_candidate"):
            picked.append((t["i"], text, verdict))
    if not picked:
        return []
    try:
        sels = frame.evaluate(BLOCK_SELECTORS, {'ids': [i for i, _, _ in picked], 'reported': reported})
    except Exception:
        return []
    rows = []
    for (_, text, verdict), selector in zip(picked, sels):
        if not selector:
            continue
        # 자모·닮은꼴 글자를 여러 요소에 나눠 쓴 글(<span>ㅋㅏ</span><span>ㅈㅣ</span>...)은
        # 조각마다 보면 광고가 아니고, 문단으로 합쳐야 위장이 드러난다. 보여도 주요 4종이다.
        disguise = disguise_techniques(text, verdict)
        level = judge(verdict, [reason for _, reason in disguise])
        for code, reason in disguise:
            rows.append({
                "url": url, "location": prefix + selector, "technique": code,
                "evidence_text": text, "normalized": verdict["normalized"],
                "reason": reason + " (여러 요소에 나눠 쓴 글을 합쳐 판정)",
                "keywords": verdict["evidence"], "extra_finding": None, "judgement": level,
            })
        if disguise:
            continue
        where = "게시글·댓글" if _BOARDISH.search(selector + " " + url) else "본문"
        rows.append({
            "url": url, "location": prefix + selector, "technique": "ETC",
            "evidence_text": text, "normalized": verdict["normalized"],
            "reason": f"{where}에 그대로 보이는 광고 문구", "keywords": verdict["evidence"],
            "extra_finding": VISIBLE_CODE, "guide": VISIBLE_GUIDE, "judgement": judge(verdict),
        })
    return rows


def extra_findings(frame, prefix, url, data, attach=None, reflect=None, reported=(), linkcheck=None):
    """주요 4종 밖의 추가 탐지 유형을 모은다 (data: EXTRACT_EXTRA 결과). 결과는 result_extra.json 으로 간다."""
    if not data:
        return []
    rows = []

    def add(text, location, kind, reason, context=None, conceal=()):
        verdict = classify(text, context=(context or {}).get('kind'))
        if not (verdict["is_ad"] or verdict.get("review_candidate")):
            return
        rows.append({
            "url": url, "location": prefix + location, "technique": "ETC",
            "evidence_text": text, "normalized": verdict["normalized"],
            "reason": reason, "keywords": verdict["evidence"],
            "extra_finding": kind, "judgement": judge(verdict, conceal),
        })

    for m in data.get("metas", []):
        add(m["text"], m["selector"], "META_SPAM(메타 태그 오염)",
            f"{m['where']} 값에 광고 문구", conceal=["메타 태그 값 (화면에 보이지 않음)"])
    for a in data.get("attrs", []):
        add(a["text"], a["selector"], "ATTR_SPAM(속성값 은닉)",
            f"{a['attr']} 속성에 광고 문구", a.get('context'), conceal=[f"{a['attr']} 속성값 (화면에 보이지 않음)"])
    for link in data.get("links", []):
        target = f"{link['text']} {link['href']}"
        add(target, link["selector"], "LINK_SPAM(외부 링크 삽입)",
            f"외부 주소로 나가는 링크: {link['href'][:60]}")
    if linkcheck is not None:
        linkcheck.collect(url, data.get("links", []), prefix)
    if attach is not None:
        files = [f for f in data.get("files", [])
                 if attach_mod.looks_like_attachment(f["href"], f["text"])]
        rows.extend(attach.check(url, files, prefix))
    if reflect is not None:
        rows.extend(reflect.check(url, data.get("forms", []), prefix))
    rows.extend(visible_findings(frame, prefix, url, data.get("texts", []), reported))
    return rows


class EvidenceMap(dict):
    """증거 키 -> 사진·원본. 같은 위치·같은 문구의 광고(공통 서식·위젯)는 처음 한 번만 찍고 다시 쓴다."""

    def __init__(self):
        super().__init__()
        self.by_content = {}


def walk_frame(frame, prefix, url, results, iframe_urls, evidence_dir=None, evid_map=None,
               attach=None, reflect=None, linkcheck=None, frame_hidden=None, primary_only=False,
               frame_failures=None):
    """프레임 하나를 훑고, 중첩된 iframe까지 재귀적으로 내려간다.

    frame_hidden: 바깥 iframe의 투명·화면 밖 은닉 상태를 중첩 프레임까지 전달한다.
    frame_failures: 글을 읽지 못한 하위 iframe 의 위치(prefix)를 모은다. '광고 없음'과 '못 봄'을 가른다.
    """
    check_cancelled()
    exclusions = getattr(getattr(frame.page, "context", None), "_hwonhi_exclusions", None)
    if isinstance(exclusions, ScanExclusions) and exclusions.skip(frame.url):
        return
    hits = []
    try:
        extracted = frame.evaluate(EXTRACT_BOTH, primary_only)
        if not isinstance(extracted, list) or len(extracted) != 2:
            raise RuntimeError("본문 추출 결과가 없습니다 (이동·프레임 소멸 가능)")
        nodes, extra = extracted
    except Exception:
        # 페이지 본문을 못 읽었으면 '광고 없음'이 아니라 '못 봄'이다. 부른 쪽이 실패로 남긴다.
        # 하위 iframe(바깥 위젯 등)은 막혀 있는 일이 흔해 그대로 넘어간다.
        if not prefix:
            raise
        if frame_failures is not None:
            frame_failures.append(prefix)
        nodes, extra = [], None
    font_text = getattr(frame.page, '_hwonhi_font_text', None)
    if font_text:
        nodes = [font_text.recover(n) for n in nodes]
    if frame_hidden:
        reasons = [f"숨긴 iframe 안 ({why})" for why in frame_hidden.get("reasons", [])]
        nodes = [dict(n, offscreen=n.get("offscreen", False) or frame_hidden.get("offscreen", False),
                      transparent=n.get("transparent", False) or frame_hidden.get("transparent", False),
                      reasons=list(n.get("reasons") or []) + reasons) for n in nodes]
    # 선택자는 위치(location)로만 쓰고 판정에는 쓰지 않는다. 검출 건이 나올 항목에만 만든다.
    # 문장·쪼갠 글 합치기에서 위치로 쓰는 항목도 그 자신이 검출 건을 내는 항목이다.
    # 광고로 판정돼도 검출 건이 없는 글(위장 없이 보이는 글)이 있으므로, 아래에서도 이 판정(produces)만 쓴다
    produces = [bool(findings_from_node(url, dict(n, selector=n.get("selector") or ""))) for n in nodes]
    need = [i for i, n in enumerate(nodes) if produces[i] and n.get("selector") is None]
    if need:
        try:
            sels = frame.evaluate(NODE_SELECTORS, need)
            if not isinstance(sels, list) or len(sels) != len(need):
                raise RuntimeError("검출 위치를 읽지 못했습니다 (이동·프레임 소멸 가능)")
        except Exception:
            if not prefix:
                raise
            nodes, extra, sels, produces = [], None, [], []
        for i, selector in zip(need, sels):
            nodes[i]["selector"] = selector or ""
    # 숨긴 문장과 그 안의 꾸밈 태그(<b>·<a> 등)가 둘 다 광고면 문장 한 건으로 합친다 (extract_js.py 의 sp·full)
    merged_into, absorbed = set(), set()
    for i, node in enumerate(nodes):
        check_cancelled()
        p = node.get("sp")
        if p is not None and produces[i] and produces[p]:
            absorbed.add(i)
            merged_into.add(p)
    for i, node in enumerate(nodes):
        if node.get('sentenceGroup') and produces[i]:
            absorbed.update(node['parts'])
    reported = set()                     # 따로 광고로 잡힌 조각의 번호
    for i, node in enumerate(nodes):
        check_cancelled()
        if i in absorbed:
            reported.add(i)
            continue
        # 쪼갠 조각을 합친 글은, 조각 가운데 하나라도 이미 잡혔으면 같은 광고를 두 번 세지 않도록 뺀다
        if node.get("parts") and not node.get("sentenceGroup") and reported.intersection(node["parts"]):
            continue
        if i in merged_into:
            node = dict(node, text=node["full"])
        elif not produces[i]:
            continue
        rows = findings_from_node(url, node, prefix=prefix)
        if rows and node.get("full") and i not in merged_into:
            # 꾸밈 태그 글자를 빼면 근거 문구가 중간이 빈 문장이 된다. 원문 문장 그대로 적는다
            for r in rows:
                r["evidence_text"] = node["full"].strip()
        if primary_only:
            rows = [r for r in rows if r["technique"] in {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"}]
        if not rows:
            continue
        reported.add(i)
        key = evidence_mod.key_for(url, rows[0]["location"])
        for r in rows:
            r["evidence_key"] = key
        hits.append((node, key))
        results.extend(rows)

    reported = [{'selector': n['selector'], 'text': n['text'].strip()} for n, _ in hits]
    extra_rows = extra_findings(frame, prefix, url, extra, attach, reflect, reported, linkcheck)
    results.extend(r for r in extra_rows if not primary_only or r["technique"] in
                   {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"})

    # 증거 촬영은 추출이 모두 끝난 뒤에 한다.
    # 은닉 해제가 DOM 을 바꾸므로 판정 도중에 섞이면 안 된다.
    if evidence_dir is not None and evid_map is not None:
        reuse = getattr(evid_map, "by_content", {})
        for node, key in hits:
            if key in evid_map:
                continue
            same = (prefix + node["selector"], node["text"].strip())
            if same not in reuse:
                # 사진 이름은 iframe 경로까지 넣은 위치로 만든다. 다른 iframe 의 같은 선택자(div.ad)가 덮어쓰지 않게
                image, outer = evidence_mod.capture(
                    frame, node["selector"], url, prefix + node["selector"], evidence_dir)
                reuse[same] = {"image": image, "html": outer}
            evid_map[key] = reuse[same]
    for child in frame.child_frames:
        check_cancelled()
        # Playwright 는 페이지를 옮겨 사라진 iframe 을 최상위 프레임의 child_frames 에서 지우지 않는다.
        # 그대로 두면 페이지마다 사라진 iframe 이 하나씩 쌓여, 점검 시간이 페이지 수의 제곱으로 는다
        # (iframe 위젯이 있는 180페이지 누리집에서 실패 호출 1만 5천 번·18초).
        if child.is_detached() or pdf_viewer_frame(child):
            continue
        try:
            step, src, hidden = frame_step(frame, child)
        except Exception:
            continue
        # iframe 으로 본 주소는 독립 페이지로 다시 세지 않는다 (scan.assemble). 자기 페이지를 가리키는
        # iframe(src="#" 등)까지 넣으면 이 페이지의 검출이 모두 지워진다 (gen.go.kr 배너모음 글 11건)
        if src and page_key(src) != page_key(url):
            iframe_urls.add(page_key(src))
        inherited = frame_hidden or {}
        hidden = hidden or {}
        combined = {flag: bool(inherited.get(flag) or hidden.get(flag)) for flag in ("transparent", "offscreen")}
        combined["reasons"] = list(dict.fromkeys(inherited.get("reasons", []) + hidden.get("reasons", [])))
        walk_frame(child, prefix + step + " >>> ", url, results, iframe_urls,
                   evidence_dir, evid_map, attach, reflect, linkcheck, combined, primary_only, frame_failures)


_VERDICTS = {}           # (사전 판, 글, strict) -> 판정. 메뉴·하단 글은 페이지마다 같아 다시 판정하지 않는다
_VERDICTS_MAX = 50000


def classify(text: str, strict: bool = False, context: str | None = None, font_decoded: bool = False):
    """한 텍스트 덩어리에 적용된 문자 난독화 기법과 광고 여부를 판정한다.

    strict 는 화면에 그대로 보이는 글에 쓴다 (lexicon.match 참고).
    같은 글은 기억해 둔 판정을 돌려준다 (돌려받은 dict 를 고치면 안 된다).
    """
    key = (lexicon.VERSION, text, strict, context, font_decoded)
    hit = _VERDICTS.get(key)
    if hit is None:
        if len(_VERDICTS) >= _VERDICTS_MAX:
            _VERDICTS.clear()
        hit = _VERDICTS[key] = _classify(text, strict, context, font_decoded)
    return hit


_KEYWORD_LISTS = ("STRONG", "TOPIC", "MEDIUM")   # 약한 말(vip·event)은 전각으로 적어도 위장이라 하기 어렵다
_PLAIN_SEP = re.compile(r"[\s.·・_\-*^~|/\\]+")


def _keywords(s):
    return [w for c in _KEYWORD_LISTS for w in getattr(lexicon, c) if w in s]


def _only_fullwidth(text):
    """닮은꼴 글자가 모두 전각 영문·숫자·기호인가. 한글 문서 편집기가 흔히 쓰는 표기다
    (원문자 🅞·수학용 굵은 글자·키릴은 일상 표기가 아니라 위장용이다)."""
    chars = disguised_chars(text)
    return bool(chars) and all("\uff01" <= c <= "\uff5e" for c in chars)


def _disguise_hides_word(text, evidence):
    """위장을 풀어야만 읽히는 사전 낱말이 있는가.

    'ＱＲ코드 이벤트 무료 지급'처럼 전각 약어를 쓴 정상 공지는 위장 글자가 있어도 낱말은 모두
    원문에서 그대로 읽힌다. 이런 글의 위장 글자를 광고 신호로 세면 약한 말만으로 광고가 된다.
    """
    # Preserve disguised gambling words even when the lexicon evidence comes from
    # promotional wording/contact signals. Whole tokens avoid matching "alphabet".
    tokens = re.findall(r"[A-Za-z\uff21-\uff3a\uff41-\uff5a]+", text)
    if any(normalize(token) in {"bet", "poker"} and has_homoglyph(token) for token in tokens):
        return True
    plain = _PLAIN_SEP.sub("", "".join(ch for ch in text if ch not in ZERO_WIDTH)).lower()
    words = [w for w in evidence if any(w in getattr(lexicon, c) for c in _KEYWORD_LISTS)]
    return any(w not in plain for w in words)


# 띄어쓰기 없이 대소문자·숫자가 섞여 길게 이어진 base64 꼴 덩어리. 사람이 읽는 글이 아니며,
# 숫자를 글자로 되돌려 읽으면 우연히 낱말이 생긴다 (목포 누리집 og:description 에 든 23만 자 base64 에서
# 'sl0t'·'t0t0' 가 slot·toto 로 읽혀 광고로 판정됐다). 판정 전에 빈칸으로 바꾼다
_BLOB = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")


def _strip_blobs(text):
    return _BLOB.sub(lambda m: " " if re.search(r"[A-Z]", m.group()) and re.search(r"[a-z]", m.group())
                     and re.search(r"\d", m.group()) else m.group(), text)


def _classify(text, strict, context=None, font_decoded=False):
    text = _strip_blobs(text)
    norm = normalize(text)
    homoglyph = has_homoglyph(text)
    jamo = has_jamo_obfuscation(text)
    detail = None

    def match(obfuscated):
        nonlocal detail
        detail = lexicon.match_detail(norm, obfuscated=obfuscated, raw=text, strict=strict, context=context)
        return detail["is_ad"], detail["evidence"]

    is_ad, evidence = match(homoglyph or jamo or font_decoded)
    if is_ad and homoglyph and not jamo and _only_fullwidth(text) and not _disguise_hides_word(text, evidence):
        is_ad, evidence = match(font_decoded)
    # 한글 사이 숫자(카ㅈ1노·머7튀)나 떼어 낸 받침(머ㄱ튀)은 다르게 풀어 봐야 낱말이 나온다.
    # 그렇게 풀어서만 업종·확정·거래 낱말이 새로 나올 때 그 위장으로 본다
    known, via = set(_keywords(norm)), None
    for code, alt in hangul_alts(norm):
        if set(_keywords(alt)) - known:
            if code == "HOMOGLYPH":
                homoglyph = True
            else:
                jamo = True
            norm, via = alt, code
            is_ad, evidence = match(True)
            break
    # 요강의 닮은꼴 글자 위장에는 숫자로 글자를 바꾼 것(cas1n0)도 든다. 숫자를 되돌려야만
    # 사전 낱말이 읽히는 경우만 위장으로 본다 (모델명 'mp3'·'5G' 같은 표기는 해당 없음)
    leet = [w for w in evidence if w not in norm and any(w in a for a in deleet_all(norm))]
    if leet and not homoglyph:
        homoglyph = True
        if not jamo:            # 위장 신호를 반영해 다시 판정한다
            is_ad, evidence = match(True)
    return {
        "normalized": norm,
        "is_ad": is_ad,
        "review_candidate": detail.get("review_candidate", False),
        "evidence": evidence,
        "leet": leet,
        "homoglyph": homoglyph,
        "jamo": jamo,
        "hangul_alt": via,          # 한글 사이 숫자·떼어 낸 받침을 풀어서 읽었으면 그 기법
        # 판정 내역(낱말 묶음·점수·감점·상한 규칙). 결과 파일에는 쓰지 않고 화면의 판정 등급에 쓴다
        "score": {k: v for k, v in detail.items() if k not in ("is_ad", "evidence")},
    }


def disguise_techniques(text, verdict):
    """문자 위장 기법(HOMOGLYPH·JAMO)과 그 설명."""
    out = []
    if verdict["homoglyph"]:
        if has_homoglyph(text):
            why = describe_homoglyph(text)
        elif verdict["leet"]:
            why = f"숫자를 글자 대신 섞음 ({', '.join(verdict['leet'])})"
        else:
            why = f"한글 자모 자리에 닮은 숫자·글자를 섞음 → '{verdict['normalized']}'"
        out.append(("HOMOGLYPH", why))
    if verdict["jamo"]:
        out.append(("JAMO", f"떼어 낸 받침을 앞 음절에 붙여 읽음 → '{verdict['normalized']}'"
                    if verdict.get("hangul_alt") == "JAMO" else describe_jamo(text)))
    return out


# 링크 묶음·문장 경계. 숨긴 글 덩어리를 이 경계로 나눈 조각도 따로 판정한다
_SEGMENT = re.compile(r"\s*[·•|｜]\s*|\n+|(?<=[.!?。])\s+")


def _segment_verdict(text, context=None):
    """숨긴 글 덩어리에서 광고로 판정되는 조각의 판정. 없으면 None.

    누리집 하단 링크 묶음('개인정보처리방침 · 불법촬영물 신고 안내 · 메이저놀이터 추천 바로가기')에
    광고를 끼우면, 덩어리 전체로는 다른 조각의 신고·불법 같은 안내 낱말이 광고 점수를 깎는다.
    각 조각은 그 조각 안의 안내 낱말로만 깎인다.
    """
    segs = [s for s in _SEGMENT.split(text) if s and len(s.strip()) >= 4]
    if len(segs) < 2:
        return None
    for s in segs:
        v = classify(s.strip(), context=context)
        if v["is_ad"]:
            return v
    return None


_HOST_IN_TEXT = re.compile(r"(?<![\w.-])(?:[a-z0-9가-힣-]+\.)+(?:com|net|kr|cc|vip|shop|top|xyz|bet|win|club|site|online|io|me|link)(?![\w.-])", re.I)


def linked_ad_verdict(node, context):
    """A hidden signup variant pointing at a domain advertised by a sibling.

    A Unicode domain or generic signup wording alone is insufficient. Keep the
    evidence on this anchor, and require independently classified advertising
    promoting exactly the same host in the same hidden link container.
    """
    text = node['text']
    if context == 'quotation' or not ('가입' in text and '코드' in text):
        return None
    hosts = {h.lower() for h in _HOST_IN_TEXT.findall(text)}
    hosts = {h for h in hosts if not re.search(r'(?:^|\.)(?:go\.kr|korea\.kr|ac\.kr|gov)$', h)}
    for peer in node.get('hiddenLinkPeers', []):
        if hosts.intersection(h.lower() for h in _HOST_IN_TEXT.findall(peer)):
            verdict = classify(peer, strict=True)
            if verdict['is_ad'] and any(w in normalize(peer) for w in lexicon.STRONG):
                own = classify(text)
                return dict(own, is_ad=True, evidence=own['evidence'] + ['인접 숨김 광고와 같은 도메인'])
    return None


def findings_from_node(url, node, prefix=""):
    """추출된 요소 하나에서 (기법별로 분리된) 검출 건들을 만든다."""
    text = node["text"].strip()
    if not text:
        return []
    # 화면에 보이는 글(닮은꼴·자모 위장만 있는 글)은 보이는 글 기준으로 엄격하게 본다
    hidden = node["transparent"] or node["offscreen"] or node.get("occluded")
    context = (node.get("context") or {}).get("kind")
    verdict = classify(text, strict=not (hidden or node.get("fontDecoded")), context=context,
                       font_decoded=bool(node.get("fontDecoded")))
    basis = "whole"
    if not verdict["is_ad"] and hidden and not (verdict.get("score") or {}).get("exempt"):
        seg = _segment_verdict(text, context=context)
        if seg is not None:
            whole = verdict
            # 위장 기법(HOMOGLYPH·JAMO)은 글 전체에서 본 것을 그대로 둔다
            verdict = dict(seg, homoglyph=whole["homoglyph"] or seg["homoglyph"], jamo=whole["jamo"] or seg["jamo"])
            basis = "segment"
    if not verdict['is_ad'] and hidden:
        linked = linked_ad_verdict(node, context)
        if linked is not None:
            verdict = linked
            basis = "linked"
    if not (verdict["is_ad"] or verdict.get("review_candidate")):
        return []                      # 감춰져 있어도 광고가 아니면 보고하지 않는다

    location = prefix + node["selector"]
    techniques = disguise_techniques(text, verdict)
    if node["transparent"]:
        techniques.append(("TRANSPARENT", ", ".join(node["reasons"]) or "투명 처리"))
    if node["offscreen"]:
        techniques.append(("OFFSCREEN", ", ".join(node["reasons"]) or "화면 밖 은닉"))
    # 요강의 주요 4종에 없는 기법은 추가 유형으로 돌린다.
    # 주요 유형으로 올리면 정답셋에 없는 항목이 되어 정확도 배점만 깎인다.
    if node.get("occluded"):
        techniques.append(("OCCLUDED", "다른 요소에 덮여 보이지 않음"))
    conceal = [reason for _, reason in techniques]
    if node.get('fontDecoded'):
        conceal.append("글꼴을 바꿔 다른 글자로 보이게 함")
    elif node.get('canvasText'):
        conceal.append("글자를 canvas 그림으로 그림")
    elif node.get('visualOrder'):
        conceal.append("CSS 표시 순서로 글자 순서를 뒤섞음")
    elif node.get('generated'):
        conceal.append(f"CSS {node['generated']} content로 넣음")
    level = judge(verdict, conceal, basis)

    # Plain visible CSS content is absent from DOM text nodes, so the visible-block
    # collector cannot report it. Keep existing disguise/hidden classifications first.
    if (node.get('fontDecoded') or node.get('canvasText')) and not techniques:
        font = node.get('fontDecoded')
        return [{
            'url': url, 'location': location, 'technique': 'ETC',
            'evidence_text': text, 'normalized': verdict['normalized'],
            'reason': '글꼴 윤곽 일치로 복원한 광고 문구' if font else 'canvas 그리기와 최종 픽셀로 확인한 광고 문구',
            'keywords': verdict['evidence'], 'extra_finding': 'FONT_TEXT_AD(글꼴 치환 광고)' if font else 'CANVAS_TEXT_AD(canvas 문구 광고)',
            'guide': VISIBLE_GUIDE, 'judgement': level,
        }]
    if node.get('visualOrder') and not techniques:
        return [{
            'url': url, 'location': location, 'technique': 'ETC',
            'evidence_text': text, 'normalized': verdict['normalized'],
            'reason': 'CSS 표시 순서를 복원한 광고 문구',
            'keywords': verdict['evidence'], 'extra_finding': VISIBLE_CODE, 'guide': VISIBLE_GUIDE,
            'judgement': level,
        }]
    if node.get("generated") and not techniques:
        return [{
            "url": url, "location": location, "technique": "ETC",
            "evidence_text": text, "normalized": verdict["normalized"],
            "reason": f"CSS {node['generated']} content로 표시한 광고 문구",
            "keywords": verdict["evidence"], "extra_finding": VISIBLE_CODE,
            "guide": "해당 요소의 스타일시트에서 광고 content를 제거하고 삽입 경로를 확인합니다.",
            "judgement": level,
        }]

    out = []
    for code, reason in techniques:
        out.append({
            "url": url,
            "location": location,
            "technique": code,
            "evidence_text": text,
            "normalized": verdict["normalized"],
            "reason": reason,
            "keywords": verdict["evidence"],
            "extra_finding": "OCCLUDED(레이어 은폐)" if code == "OCCLUDED" else None,
            "judgement": level,
        })
    return out
