"""연계 링크 목적지 확인. 누리집이 걸어 둔 바깥 링크가 광고 사이트로 바뀌지 않았는지 본다.

악용 방식
  행사·사업 누리집이나 유관 단체 도메인이 만료되면 누구나 그 도메인을 살 수 있다.
  도박·성인 광고 업자가 사들이면, 기관 누리집의 '패밀리 사이트'·배너 링크가 그대로
  광고 사이트로 안내하는 통로가 된다. 기관 누리집 안에는 아무것도 바뀌지 않으므로
  담당자가 자기 누리집을 열어 봐도 알아채기 어렵다.

점검 방식 (기본 꺼짐)
  점검 중 모은 바깥 링크를 도메인마다 한 번만 GET 으로 받아 글자로 판정한다.
  브라우저로 열지 않는다. 스크립트를 실행하지 않고 그림도 받지 않는다
  (광고 사이트의 악성 스크립트가 담당자 PC 에서 돌지 않게).
  목적지 안의 링크는 따라가지 않는다. 다른 기관 누리집을 점검하는 기능이 아니다.
  공공 도메인(go.kr 등)은 개인이 살 수 없으므로 조회하지 않는다.

등급
  피해 발생 또는 광고 확인됨  목적지 제목이나 글 여러 덩어리가 광고로 판정된다
  주의       목적지가 도메인 판매·만료 안내 페이지이거나, 도메인 주소 자체가 없다
             (지금은 광고가 없지만 누구나 사서 광고 사이트로 바꿀 수 있다)
"""
import html
import re
import time
from urllib.parse import urljoin, urlparse

from search_reflect import tag_attrs

EXTRA_CODE = "LINK_HIJACKED(연계 사이트 변질)"
MAX_HOSTS = 50            # 한 번 점검에서 조회하는 바깥 도메인 수 상한
BUDGET_SEC = 120          # 연계 링크 확인에 쓰는 시간 상한
TIMEOUT_MS = 8000
MAX_BLOCKS = 400

# 개인이 살 수 없는 공공 도메인. 만료돼도 광고 업자 손에 넘어가지 않는다.
_PUBLIC_SUFFIX = ("go.kr", "korea.kr", "mil.kr", "ac.kr", "re.kr", "gov", "mil", "edu")
# 도메인이 만료될 일이 없는 대형 서비스 (뷰어 내려받기·SNS 링크 등)
_PLATFORMS = ("naver.com", "daum.net", "kakao.com", "google.com", "youtube.com", "youtu.be",
              "facebook.com", "instagram.com", "twitter.com", "x.com", "apple.com",
              "microsoft.com", "adobe.com", "hancom.com")
_FILE_EXT = (".pdf", ".hwp", ".hwpx", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".xls",
             ".xlsx", ".doc", ".docx", ".ppt", ".pptx", ".mp4", ".exe", ".msi")

_DROP = re.compile(r"<(script|style|noscript|template)\b[^>]*>.*?</\1\s*>", re.I | re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_BODY = re.compile(r"<body[^>]*>(.*)", re.I | re.S)
_BLOCK = re.compile(r"<(?:/?(?:p|div|li|ul|ol|h[1-6]|td|th|tr|table|section|article|header|"
                    r"footer|nav|main|aside|dd|dt|dl|form|blockquote|pre|a)\b[^>]*|br\s*/?)>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_META = re.compile(r"<meta\b[^>]*>", re.I)
_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?([\w-]+)""", re.I)
# 스크립트로 다른 주소로 넘기는 껍데기 페이지 (실행하지 않고 주소만 읽는다)
_JS_JUMP = re.compile(r"""location(?:\.href)?\s*=\s*["'](https?://[^"']+)["']|"""
                      r"""location\.(?:replace|assign)\(\s*["'](https?://[^"']+)["']""", re.I)
# 도메인 판매·주차·만료 안내 페이지
_PARKED = re.compile(r"(this domain (?:name )?(?:is|may be) for sale|buy this domain|"
                     r"domain (?:name )?(?:is )?for sale|parked (?:free|domain)|sedoparking|"
                     r"dan\.com|afternic|hugedomains|(?:this )?domain (?:name )?has expired|"
                     r"도메인(?:을|이)?\s*(?:판매|매각|구매|구입)|판매\s*중인\s*도메인|"
                     r"만료된\s*도메인|도메인이\s*만료)", re.I)

CONFIRMED = "피해 발생 또는 광고 확인됨"     # 가장 심각한 등급. 바꾸기 전 이름은 '피해 확인'

GUIDE = {
    CONFIRMED: "이 링크를 삭제하거나 올바른 주소로 고치십시오. 모든 페이지 하단(패밀리 사이트·배너)에 "
                 "있는 링크라면 공통 서식(템플릿)에서 고쳐야 모든 페이지에서 사라집니다. "
                 "옛 행사·사업 누리집이라면 도메인이 만료되어 다른 사람에게 넘어간 것입니다.",
    "주의": "지금은 광고가 없지만, 도메인이 판매 중이거나 없어져 누구나 사서 광고 사이트로 바꿀 수 있습니다. "
            "더 쓰지 않는 누리집이면 링크를 지우고, 계속 쓸 누리집이면 운영 부서에 도메인 갱신을 요청하십시오.",
}


def _host_key(url):
    p = urlparse(url)
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return f"{host}:{p.port}" if p.port else host


def _under(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def worth_checking(href):
    """바깥 링크 가운데 목적지를 조회할 만한 것인지 (공공 도메인·대형 서비스·파일은 제외)."""
    p = urlparse(href)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname.lower()
    if _under(host, _PUBLIC_SUFFIX) or _under(host, _PLATFORMS):
        return False
    return not p.path.lower().endswith(_FILE_EXT)


def decode(raw: bytes, ctype: str) -> str:
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = _CHARSET.search(raw[:4096])
        enc = m.group(1).decode("ascii", "ignore") if m else None
    if enc and enc.lower().replace("_", "-") in ("euc-kr", "ks-c-5601-1987", "ksc5601"):
        enc = "cp949"
    for e in (enc, "utf-8", "cp949"):
        if not e:
            continue
        try:
            return raw.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def title_of(body):
    m = _TITLE.search(body)
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", m.group(1)))).strip() if m else ""


def text_blocks(body):
    """화면에 나올 글을 문단·칸·목록 단위 덩어리로 나눈다 (렌더링 없이 대략)."""
    body = _COMMENT.sub(" ", _DROP.sub(" ", body))
    m = _BODY.search(body)
    body = m.group(1) if m else body
    out = []
    for part in _BLOCK.split(body):
        t = _WS.sub(" ", html.unescape(_TAG.sub(" ", part))).strip()
        if len(t) >= 4:
            out.append(t[:500])
            if len(out) >= MAX_BLOCKS:
                break
    return out


def jump_target(body, base):
    """meta refresh 나 스크립트로 바로 넘기는 껍데기 페이지면 넘어갈 주소."""
    for tag in _META.findall(body):
        a = tag_attrs(tag)
        if a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", a.get("content", ""), re.I)
            if m:
                return urljoin(base, m.group(1).strip())
    m = _JS_JUMP.search(body)
    if m and len(text_blocks(body)) <= 3:      # 글이 거의 없는 페이지에서만 (본문 속 예시 코드 제외)
        return m.group(1) or m.group(2)
    return None


class LinkChecker:
    """점검 중 바깥 링크를 모았다가, 탐색이 끝난 뒤 도메인마다 한 번씩 목적지를 확인한다."""

    def __init__(self, request_ctx, manners, classify, in_scope,
                 max_hosts=MAX_HOSTS, budget_sec=BUDGET_SEC, timeout_ms=TIMEOUT_MS):
        self.request = request_ctx
        self.manners = manners
        self.classify = classify
        self.in_scope = in_scope
        self.max_hosts = max_hosts
        self.budget_sec = budget_sec
        self.timeout_ms = timeout_ms
        self.links = {}           # 도메인 -> 처음 본 링크와, 그 링크가 있는 페이지들
        self.completed = set()
        self.saved_rows = []
        self.missing = []
        self.reached = False
        self.on_checkpoint = None
        self.checked = 0          # 실제로 보낸 GET 수

    def collect(self, page_url, links, prefix=""):
        for link in links:
            href = link.get("href") or ""
            if self.in_scope(href) or not worth_checking(href):
                continue
            key = _host_key(href)
            rec = self.links.get(key)
            if rec is None:
                rec = self.links[key] = {"url": page_url, "location": prefix + link["selector"],
                                         "href": href, "text": link.get("text") or "", "pages": set()}
            rec["pages"].add(page_url)

    def _get(self, url):
        """(최종 주소, 본문 글) / 'nxdomain' / None. 파일·오류 응답은 None."""
        self.manners.wait()
        self.checked += 1
        try:
            resp = self.request.get(url, timeout=self.timeout_ms, max_redirects=5)
        except Exception as exc:
            return "nxdomain" if "ENOTFOUND" in str(exc) else None
        try:
            ctype = resp.headers.get("content-type", "")
            if resp.status >= 400 or ("html" not in ctype and "text" not in ctype and ctype):
                return None
            return resp.url, decode(resp.body(), ctype)
        except Exception:
            return None

    def run(self, should_stop=None, progress=None):
        t0 = time.perf_counter()
        rows, missing = self.saved_rows, self.missing
        reached = self.reached
        def done(key):
            self.completed.add(key)
            self.reached = reached
            if self.on_checkpoint: self.on_checkpoint()
        for key, rec in [(k, v) for k, v in self.links.items() if k not in self.completed][:self.max_hosts]:
            if (should_stop and should_stop()) or time.perf_counter() - t0 > self.budget_sec:
                break
            if progress:
                progress(rec["href"])
            got = self._get(rec["href"])
            if got is None and urlparse(rec["href"]).path not in ("", "/"):
                # 옛 행사 페이지 같은 깊은 주소는 없어도 첫 화면이 광고로 바뀌어 있을 수 있다
                p = urlparse(rec["href"])
                got = self._get(f"{p.scheme}://{p.netloc}/")
            if got == "nxdomain":
                missing.append(rec)
                done(key)
                continue
            if got is None:
                done(key)
                continue
            reached = True
            final, body = got
            hops = [final]
            row = self._judge(rec, final, body, hops)
            if row is None:
                nxt = jump_target(body, final)
                if nxt and nxt != final:
                    got = self._get(nxt)
                    if isinstance(got, tuple):
                        hops.append(got[0])
                        row = self._judge(rec, got[0], got[1], hops)
            if row:
                rows.append(row)
            done(key)
        # 폐쇄망에서는 모든 도메인이 '없음'으로 나온다. 바깥에 한 곳이라도 닿았을 때만 믿는다.
        if reached:
            for rec in missing:
                rows.append(self._row(rec, "주의", ["도메인 주소 없음"],
                                      "도메인 주소를 찾을 수 없음(만료 가능성)",
                                      f"도메인 주소({urlparse(rec['href']).hostname})를 찾을 수 없음. "
                                      "만료된 도메인이면 누구나 새로 사서 광고 사이트로 쓸 수 있음"))
            missing.clear()
        if self.on_checkpoint: self.on_checkpoint()
        return rows

    def _judge(self, rec, final, body, hops):
        title = title_of(body)
        blocks = text_blocks(body)
        words, samples = [], []
        if title:
            v = self.classify(title, strict=True)
            if v["is_ad"]:
                words += v["evidence"]
                samples.append(title)
        ad_blocks = 0
        for t in blocks:
            v = self.classify(t, strict=True)
            if v["is_ad"]:
                ad_blocks += 1
                words += v["evidence"]
                if len(samples) < 2:
                    samples.append(t)
        # 정상 누리집에 광고 댓글 하나가 붙은 정도는 '사이트가 바뀐 것'이 아니다
        if (title and samples and samples[0] == title) or ad_blocks >= 2 or \
                (ad_blocks and ad_blocks * 3 >= len(blocks)):
            route = self._route(rec, hops)
            sample = " / ".join(s[:80] for s in samples)
            return self._row(rec, CONFIRMED, sorted(set(words), key=words.index),
                             f"연계 링크 목적지가 광고 페이지임{route}",
                             f"목적지{route} 제목 '{title[:60]}', 문구 '{sample}'")
        if _PARKED.search(title + " " + " ".join(blocks[:60])) or _PARKED.search(body[:20000]):
            route = self._route(rec, hops)
            return self._row(rec, "주의", ["도메인 판매·만료 안내"],
                             f"연계 링크 목적지가 도메인 판매·만료 안내 페이지임{route}",
                             f"목적지{route} 제목 '{title[:60]}'. 도메인이 판매 중이거나 만료되어 "
                             "누구나 사서 광고 사이트로 쓸 수 있음")
        return None

    @staticmethod
    def _route(rec, hops):
        moved = [h for h in hops if _host_key(h) != _host_key(rec["href"])]
        return f"(넘겨진 주소 {moved[-1][:80]})" if moved else ""

    def _row(self, rec, grade, keywords, reason, detail):
        more = len(rec["pages"]) - 1
        where = f" 같은 링크가 다른 페이지 {more}곳에도 있음." if more > 0 else ""
        label = rec["text"][:40] or "(글자 없는 링크)"
        return {
            "url": rec["url"], "location": rec["location"], "technique": "ETC",
            "normalized": "", "extra_finding": EXTRA_CODE,
            "is_violation": grade == CONFIRMED, "grade": grade,
            "keywords": keywords, "reason": reason,
            "evidence_text": f"[{grade}] 연계 링크 '{label}' ({rec['href'][:80]}): {detail}.{where}",
            "guide": GUIDE[grade],
        }
