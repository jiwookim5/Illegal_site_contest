"""적격평가 채점 시뮬레이터.

붙임2/붙임4 규칙을 재현한다.
 - url + location + technique 3개가 모두 일치해야 정답
 - location은 문자열이 아니라 '가리키는 요소'로 비교
 - 선택자가 2개 이상의 요소를 가리키면 오답
 - URL은 끝 슬래시 / http-https / # 이하를 무시, 쿼리는 순서만 무시
"""
import json, re, argparse, sys
from urllib.parse import urlparse, parse_qsl, unquote
from playwright.sync_api import sync_playwright

import schema_check

# 요강에 시간 배점 산식이 없어 자체 가정: 60초 이내 만점, 1800초에서 0점
TIME_FULL_SEC, TIME_ZERO_SEC = 60, 1800

# 요소의 고유 경로를 계산하는 JS. 선택자 표기가 달라도 같은 요소면 같은 값이 나온다.
CANON_JS = """el => {
  const parts = [];
  while (el && el.nodeType === 1 && el.tagName !== 'HTML') {
    let i = 1, s = el;
    while ((s = s.previousElementSibling)) i++;
    parts.unshift(el.tagName.toLowerCase() + '[' + i + ']');
    el = el.parentElement;
  }
  return parts.join('/');
}"""


def norm_url(u, base):
    if u.startswith("/"):
        u = base + u
    p = urlparse(u)
    path = unquote(p.path + (";" + p.params if p.params else "")).rstrip("/") or "/"   # 한글 경로는 그대로 적든 %EA… 로 적든 같은 주소
    q = tuple(sorted(parse_qsl(p.query, keep_blank_values=True)))
    return (p.netloc, path, q)          # scheme과 fragment는 비교 대상이 아님


def find_frame_elements(frame, sel):
    """iframe 선택자 해석.

    요강은 iframe src가 상대경로여도 location에는 절대주소로 적으라고 요구한다.
    따라서 속성값 그대로는 매칭되지 않으므로, 절대 URL로 비교하는 경로를 둔다.
    """
    handles = frame.query_selector_all(sel)
    if handles:
        return handles
    m = re.search(r'src\s*=\s*"([^"]+)"', sel)
    if not m:
        return []
    want = m.group(1).rstrip("/")
    tag = sel.split("[")[0] or "iframe"
    return [h for h in frame.query_selector_all(tag)
            if (h.get_property("src").json_value() or "").rstrip("/") == want]


def resolve(page, location):
    """location을 실제 요소로 해석. 유일하지 않거나 없으면 None."""
    parts = [s.strip() for s in location.split(">>>")]
    frame = page.main_frame
    chain = []
    for sel in parts[:-1]:                       # iframe 단계들
        handles = find_frame_elements(frame, sel)
        if len(handles) != 1:
            return None
        chain.append(handles[0].evaluate(CANON_JS))
        frame = handles[0].content_frame()
        if frame is None:
            return None
    handles = frame.query_selector_all(parts[-1])
    if len(handles) != 1:                        # 0개 또는 2개 이상 → 오답
        return None
    chain.append(handles[0].evaluate(CANON_JS))
    return "||".join(chain)


# 사람이 확인하듯 화면을 끝까지 내리고 '더보기'를 눌러, 나중에 불러오는 댓글도 채점 대상에 올린다
MORE_JS = """() => {
  let n = 0;
  for (const el of document.querySelectorAll('button, a[href="#"], a[href^="javascript:"], span, div')) {
    const t = (el.textContent || '').trim();
    if (t.length <= 15 && /더\\s*보기|more/i.test(t) && el.children.length === 0) { el.click(); n++; }
  }
  return n;
}"""


def reveal_lazy(pw_page):
    try:
        pw_page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        # 스크롤 직후에는 IntersectionObserver 가 아직 요청을 보내지 않아 networkidle 이 바로 통과된다
        pw_page.wait_for_timeout(200)
        pw_page.wait_for_load_state("networkidle")
        if pw_page.evaluate(MORE_JS):
            pw_page.wait_for_load_state("networkidle")
            pw_page.wait_for_timeout(300)
        pw_page.evaluate("() => window.scrollTo(0, 0)")
    except Exception:
        pass


def build_index(pw_page, base, items, key_fn):
    """항목들을 (url, 요소경로, technique) 집합으로 변환."""
    by_url = {}
    for it in items:
        by_url.setdefault(it["url"], []).append(it)
    out, unresolved = set(), []
    for url, group in by_url.items():
        full = base + url if url.startswith("/") else url
        pw_page.goto(full, wait_until="networkidle")
        # 페이지를 연 뒤 스크립트가 늦게 끼워 넣는 광고도 사람이 보듯 나타날 때까지 기다린다
        pw_page.wait_for_timeout(2000)
        reveal_lazy(pw_page)
        for it in group:
            path = resolve(pw_page, it["location"])
            if path is None:
                unresolved.append(it)
                continue
            out.add((norm_url(url, base), path, key_fn(it)))
    return out, unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--result", required=True)
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    key = json.load(open(args.key, encoding="utf-8"))
    base = key["base"]
    # 요강 붙임4: 파일 전체가 파싱되지 않거나 구조가 틀리면 0점(평가 제외), 스키마를 어긴 항목은 오답
    file_err, item_err, warn, result = schema_check.check(args.result, entry_url=key.get("entry_url"))
    schema_lines = schema_check.report(args.result, file_err, item_err, warn,
                                       result.get("findings") if isinstance(result, dict) else None)
    if file_err:
        print("\n".join(schema_lines))
        print("=" * 58)
        print(f"  정답 {len(key['answers'])}건 / 제출 0건 / 정탐 0건")
        print("  결과 파일 스키마 오류: 성능 점수 0점 (요강: 파싱 불가·스키마 미준수 시 평가 제외)")
        print("=" * 58)
        return
    findings = [f for i, f in enumerate(result["findings"]) if i not in item_err]
    elapsed = float(result["meta"]["elapsed_sec"])

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        truth, bad_key = build_index(page, base, key["answers"], lambda i: i["technique"])
        subs, unresolved = build_index(
            page, base,
            [{"url": f.get("url", ""), "location": f.get("location", ""),
              "technique": f.get("technique", "")} for f in findings],
            lambda i: i["technique"])
        browser.close()

    if bad_key:
        print(f"[경고] 정답셋 자체가 해석 불가한 항목 {len(bad_key)}개")
        for b in bad_key:
            print("   ", b["url"], b["location"])

    hit = truth & subs
    missed = truth - subs
    false_pos = subs - truth

    n_truth = len(truth)
    # 해석 불가·스키마를 어긴 제출분도 분모에 포함(오답 처리). 요강 붙임4 는 '채점 제외'라고도 해서 불리한 쪽으로 센다
    n_sub = len(subs) + len(unresolved) + len(item_err)
    detect = 45 * len(hit) / n_truth if n_truth else 0
    accuracy = 35 * len(hit) / n_sub if n_sub else 0
    if elapsed <= TIME_FULL_SEC:
        t = 20.0
    elif elapsed >= TIME_ZERO_SEC:
        t = 0.0
    else:
        t = 20 * (TIME_ZERO_SEC - elapsed) / (TIME_ZERO_SEC - TIME_FULL_SEC)

    print("=" * 58)
    print(f"  정답 {n_truth}건 / 제출 {n_sub}건 / 정탐 {len(hit)}건")
    print("-" * 58)
    print(f"  정답 검출 개수   {detect:5.1f} / 45   ({len(hit)}/{n_truth})")
    print(f"  정답 추출 정확도 {accuracy:5.1f} / 35   (정탐 {len(hit)} / 제출 {n_sub})")
    print(f"  검출 시간        {t:5.1f} / 20   ({elapsed:.1f}초) ※산식은 자체 가정")
    print("-" * 58)
    print(f"  총점             {detect + accuracy + t:5.1f} / 100")
    print("=" * 58)

    def show(title, rows):
        if not rows:
            return
        print(f"\n[{title}] {len(rows)}건")
        for u, path, tech in sorted(rows):
            print(f"  - {u[1]}{('?' + '&'.join(f'{k}={v}' for k, v in u[2])) if u[2] else ''}"
                  f"  [{tech}]  {path}")

    if schema_lines:
        print(f"\n[스키마] 항목 오류 {len(item_err)}건 (오답 처리), 주의 {len(warn)}건")
        for line in schema_lines:
            print("  " + line)
    show("미검출", missed)
    show("오탐", false_pos)
    if unresolved:
        print(f"\n[해석 불가한 제출 선택자] {len(unresolved)}건 (유일성 위반 또는 미존재)")
        for it in unresolved:
            print("  -", it["url"], "|", it["location"])


if __name__ == "__main__":
    main()
