"""검색 노출 점검 결과 보고서(report.html).

점검 결과 보고서(ui/report_html.py)와 같은 디자인·틀로 만든다: 인쇄 단추, 요약 타일, 정보 표,
붉은 선 안내 상자, 상세 목록, 결재란. 인쇄하면 PDF 로 저장하거나 종이로 낼 수 있다.
검색 화면·현재 화면 증거 파일은 같은 폴더의 상대 경로로 연결한다.
"""
import html
from collections import Counter
from urllib.parse import unquote, urlsplit

TYPE_NAMES = {
    "SEARCH_REMOVED_AD": "삭제 응답 URL의 검색 노출 잔존",
    "SEARCH_PARAMETER_AD": "광고 파라미터 URL의 검색 노출",
    "SEARCH_LIVE_AD": "현재 페이지 광고의 검색 노출",
    "SEARCH_INDEXED_AD": "검색 제목·요약의 광고 노출",
}
STATE_NAMES = {
    "collected": "수집", "no_results": "결과 없음", "no_target_results": "대상 밖 결과만",
    "needs_review": "화면 확인 필요", "blocked": "차단", "consent_required": "동의 화면",
    "repeated_page": "같은 페이지 반복", "error": "오류", "pending": "대기", "cancelled": "중지",
    "processing": "처리 중",
}
EVIDENCE_NAMES = {"api": "검색 API 증거", "screenshot": "검색 화면", "text": "화면 텍스트", "html": "화면 HTML"}
PROBLEM_STATES = ("error", "pending", "cancelled")
ENGINE_NAMES = {"google": "구글"}

# 점검 보고서 CSS 위에 더하는 검색 보고서 전용 규칙
EXTRA_CSS = """
table.urls{table-layout:fixed}
table.urls th:nth-child(1){width:52px}
table.urls th:nth-child(2){width:30%}
table.urls th:nth-child(3){width:17%}
table.urls th:nth-child(5){width:112px}
table.urls td b{display:block}
table.urls td small{display:block}
table.queries th.num,table.queries td.num{width:70px}
.src{margin:0 0 12px}
.src:last-child{margin-bottom:0}
.src b{display:block}
.src small{display:block}
td p{margin:0 0 6px}
td ul{margin:6px 0 0;padding-left:18px}
details{margin-top:6px}
summary{cursor:pointer;color:var(--primary-60);font-size:13px;font-weight:600}
.chip.ad{border-color:var(--red);color:var(--red-dark);background:#fdeaea}
a{color:var(--primary-60)}
"""


def _e(value):
    return html.escape("" if value is None else str(value), quote=True)


def _evidence_links(evidence):
    """같은 폴더 안의 상대 경로만 링크로 만든다 (절대 경로·상위 폴더·외부 주소는 제외)."""
    links = []
    for label, path in (evidence or {}).items():
        if (isinstance(path, str) and not urlsplit(path).scheme and not path.startswith(("/", "\\"))
                and ".." not in path.split("/") and "\\" not in path):
            links.append(f'<a href="{_e(path)}">{_e(EVIDENCE_NAMES.get(label, label))}</a>')
    return " · ".join(links)


def _url_html(url):
    """긴 주소를 읽기 쉽게: 도메인·경로는 굵게, 퍼센트 인코딩된 질의는 풀어 줄여 보이고 전체 주소는 접어 둔다."""
    parts = urlsplit(url)
    head = f"{parts.netloc}{parts.path}"
    query = unquote(parts.query)
    shown = f"<small>?{_e(query[:140])}{'…' if len(query) > 140 else ''}</small>" if query else ""
    full = f"<details><summary>전체 주소</summary><code>{_e(url)}</code></details>" if query or len(url) > 90 else ""
    return f"<b>{_e(head)}</b>{shown}{full}"


def _source_html(source):
    title = source.get("title") or "(제목 없음)"
    snippet = (source.get("snippet") or "")[:300]
    engine = ENGINE_NAMES.get(source.get("engine"), source.get("engine"))
    from ui.report_html import _when
    meta = " · ".join(x for x in (_e(engine), _e(source.get("query")), _e(_when(source.get("searched_at"))),
                                  _evidence_links(source.get("evidence"))) if x)
    return f'<div class="src"><b>{_e(title)}</b>{f"<small>{_e(snippet)}</small>" if snippet else ""}<small>{meta}</small></div>'


def build(run):
    from search_submission import document
    from ui.report_html import CSS, _when, duration

    doc = document(run)
    submitted = doc["findings"]
    meta = doc["meta"]
    codes = Counter(f["extra_finding"].split("(")[0] for f in submitted)
    by_url = {}
    for f in submitted:
        by_url.setdefault(f["url"], set()).add(f["extra_finding"].split("(")[0])
    results = run.get("results", [])
    queries = run.get("queries", [])
    problems = [q for q in queries if q.get("state") in PROBLEM_STATES]
    returned = sum(q.get("returned_links", 0) or 0 for q in queries)
    sitelinks = sum(q.get("sitelinks", 0) or 0 for q in queries)
    checked = sum(1 for r in results if r.get("checked_at"))
    target = run.get("target", "")
    entry = run.get("entry_host") or target
    scope = f"{target} 및 하위 도메인" if run.get("subdomains") else target
    if entry and entry != target:
        scope += f" (입력한 주소: {entry})"
    # 여러 엔진 결과를 합친 기록에는 mode 가 없으므로 질의의 증거 파일 종류로 방식을 알아본다
    api = run.get("mode") == "api" or any("api" in (q.get("evidence") or {}) for q in queries)
    engine = "구글 (SerpApi 검색 API)" if api else "구글 (검색 화면 수집)"

    tiles = [("", "수집한 URL", len(results), "곳"),
             ("hot" if submitted else "", "광고로 판정", len(submitted), "건"),
             ("", "광고 문구가 주소에 포함", codes["SEARCH_PARAMETER_AD"], "건"),
             ("", "삭제 응답인데 노출", codes["SEARCH_REMOVED_AD"], "건"),
             ("", "현재 페이지에도 광고", codes["SEARCH_LIVE_AD"], "건")]
    parts = [f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>검색 노출 점검 결과 보고 {_e(_when(meta["started_at"])[:10])}</title>
<style>{CSS}{EXTRA_CSS}</style></head><body>
<div class="bar"><button onclick="print()">인쇄 · PDF로 저장</button>
<button class="ghost" onclick="window.close()">닫기</button></div>
<main class="sheet">
<p class="eyebrow">검색 노출 점검 결과 보고</p>
<h1>검색엔진 노출 광고 점검 결과 보고</h1>
<p class="sub">{_e(scope)} · {_e(_when(meta["started_at"]))} 검색</p>
<div class="tiles">""" + "".join(
        f'<div class="tile {c}"><span>{_e(k)}</span><b>{v}<small>{u}</small></b></div>' for c, k, v, u in tiles) + f"""</div>
<p class="unit">광고로 판정한 건수는 공모전 추가 탐지 파일(result_extra.json)에 반영하는 건수와 같습니다. 같은 URL이 여러 검색 위치에 나오면 위치별로 셉니다.
검색 제목·요약에 광고 문구가 없는 URL은 판정하지 않고 '검토 필요'로 남깁니다.</p>
<h2>검색 정보</h2>
<dl class="info">
<dt>검색 대상</dt><dd>{_e(scope)}</dd>
<dt>검색 일시</dt><dd>{_e(_when(meta["started_at"]))} ~ {_e(_when(meta["finished_at"]))} · 소요 {_e(duration(meta["elapsed_sec"]))}</dd>
<dt>검색엔진</dt><dd>{_e(engine)}</dd>
<dt>검색 규모</dt><dd>요청 {len(queries)}회(페이지 단위) · 수신 링크 {returned}건(페이지 간 중복 포함) · 그중 하위 링크 {sitelinks}건</dd>
<dt>현재 상태 검사</dt><dd>{f"수집한 URL {checked}곳을 검사했습니다 ({_e(_when(run.get('rechecked_at')))})" if checked else "하지 않았습니다 (검색 결과 수집만)"}</dd>
<dt>점검 도구</dt><dd>훤히 — 공공 누리집 숨은 불법광고 점검 도구 (검색엔진 보조 탐색)</dd>
</dl>"""]
    if run.get("stopped"):
        parts.append('<p class="note">담당자가 검색을 중지해 일부 질의만 수행한 결과입니다.</p>')
    if run.get("limit_reached"):
        parts.append('<p class="note">수집 URL 상한(300건)에 닿아 일부 결과를 담지 못했습니다.</p>')
    if problems:
        parts.append(f'<p class="note">확인하지 못한 질의가 {len(problems)}건 있습니다. 광고가 없다는 뜻이 아니므로 '
                     "아래 '질의별 수집 상태'를 확인한 뒤 다시 검색하십시오.</p>")
    for note in run.get("notes", []):
        parts.append(f'<p class="note">{_e(note)}</p>')
    parts.append('<p class="unit">검색 당시의 노출과 현재 검사 결과를 함께 검토하십시오. 광고 확정이나 색인삭제 완료를 의미하지 않으며, '
                 '검색 노출의 판정이 현재 사이트에 광고가 있다는 뜻도 아닙니다. 제출 파일은 '
                 '<a href="result_extra.json">result_extra.json</a>, 상세 근거는 results.json·review.csv, '
                 '검색 화면은 search_evidence, 현재 화면은 page_evidence 폴더에 있습니다.</p>')

    parts.append('<h2>판정 유형별 건수 <small>광고로 판정한 항목 기준</small></h2>'
                 '<table><thead><tr><th scope=col>유형</th><th scope=col class="num">건수</th></tr></thead>')
    for code, name in TYPE_NAMES.items():
        if codes[code]:
            parts.append(f'<tr><td>{_e(name)}</td><td class="num">{codes[code]}</td></tr>')
    if not submitted:
        parts.append('<tr><td colspan="2">광고로 판정한 항목이 없습니다.</td></tr>')
    parts.append("</table>")

    if submitted:
        parts.append('<h2>유형별 권장 조치 절차</h2>'
                     '<table><thead><tr><th scope=col style="width:28%">검출 유형</th>'
                     '<th scope=col>원인 및 권장 조치 절차</th></tr></thead><tbody>'
                     '<tr><td><b>현재 페이지 광고</b><br><small>SEARCH_LIVE_AD</small></td>'
                     '<td>웹페이지에 광고가 남아 있고 검색엔진에도 노출된 상태입니다.<br>'
                     '① 누리집 관리자 화면에서 해당 게시글·댓글 또는 악성 코드를 즉시 삭제합니다.<br>'
                     '② 삭제 후 Google Search Console(색인 생성 &gt; 삭제)에서 URL 임시 삭제를 요청합니다.</td></tr>'
                     '<tr><td><b>삭제 응답 잔존</b><br><small>SEARCH_REMOVED_AD</small></td>'
                     '<td>원본 게시글은 삭제(404·410)되었으나 검색엔진 캐시에 여전히 노출 중인 상태입니다.<br>'
                     '① Google Search Console의 <b>URL 삭제 도구</b> 또는 Google 오래된 콘텐츠 삭제 요청 도구를 통해 빠른 색인 제거를 신청합니다.</td></tr>'
                     '<tr><td><b>광고 파라미터 반사</b><br><small>SEARCH_PARAMETER_AD</small></td>'
                     '<td>검색창 URL 파라미터에 광고 문구가 삽입되어 검색엔진에 노출된 상태입니다.<br>'
                     '① 검색결과 출력 페이지의 <code>&lt;head&gt;</code>에 <code>&lt;meta name="robots" content="noindex"&gt;</code>를 적용합니다.<br>'
                     '② Search Console에서 비정상 파라미터가 포함된 검색결과 URL의 색인 삭제를 요청합니다.</td></tr>'
                     '<tr><td><b>검색 노출 광고</b><br><small>SEARCH_INDEXED_AD</small></td>'
                     '<td>검색 결과 제목·요약에 광고 문구가 확인된 주소입니다.<br>'
                     '① 해당 URL의 실제 화면을 점검하여 원본 글 존재 여부를 확인하고, 위 유형별 절차에 따라 삭제 및 색인 제외를 진행합니다.</td></tr>'
                     '</tbody></table>')

    parts.append(f"<h2>수집한 URL 목록 <small>{len(results)}곳</small></h2>")
    if results:
        parts.append('<table class="urls"><thead><tr><th scope=col>번호</th><th scope=col>URL</th><th scope=col>현재 상태</th>'
                     '<th scope=col>검색 당시 근거</th><th scope=col>판정</th></tr></thead>')
        ordered = sorted(results, key=lambda r: r["url"] not in by_url)       # 광고로 판정한 URL 을 앞에
        for no, r in enumerate(ordered, 1):
            findings = "".join(f"<li>{_e(f.get('location'))} · {_e(f.get('technique'))} · {_e((f.get('evidence_text') or '')[:120])}</li>"
                               for f in r.get("findings", []))
            shot = _evidence_links({"현재 화면": r["current_screenshot"]}) if r.get("current_screenshot") else ""
            http = f"HTTP {_e(r.get('http_status'))} · " if r.get("http_status") else ""
            when = _e(_when(r.get("checked_at"))) if r.get("checked_at") else ""
            final = f"<p><small>최종 URL: {_e(r['final_url'])}</small></p>" if r.get("final_url") and r["final_url"] != r["url"] else ""
            state = (f'<span class="chip">{_e(r.get("status"))}</span>'
                     + (f"<p><small>{http}{when}</small></p>" if http or when else "")
                     + (f"<p><small>{_e(r.get('detail'))}</small></p>" if r.get("detail") else "")
                     + final + (f"<p><small>{shot}</small></p>" if shot else "")
                     + (f"<ul>{findings}</ul>" if findings else ""))
            sources = r.get("sources", [])
            shown = "".join(_source_html(s) for s in sources[:2])
            rest = "".join(_source_html(s) for s in sources[2:])
            evidence = shown + (f"<details><summary>검색 출처 {len(sources) - 2}건 더 보기</summary>{rest}</details>" if rest else "")
            if r["url"] in by_url:
                verdict = '<span class="chip ad">광고 판정</span><br>' + "<br>".join(
                    f"<small>{_e(TYPE_NAMES.get(c, c))}</small>" for c in sorted(by_url[r["url"]]))
            else:
                verdict = '<span class="chip">검토 필요</span>'
            parts.append(f'<tr><td class="id">{no}</td><td class="ev">{_url_html(r["url"])}</td><td>{state}</td>'
                         f'<td class="ev">{evidence}</td><td>{verdict}</td></tr>')
        parts.append("</table>")
    else:
        parts.append('<p class="empty">수집한 URL이 없습니다.</p>')

    parts.append(f"<h2>질의별 수집 상태 <small>{len(queries)}건</small></h2>"
                 "<p>no_results(결과 없음)는 해당 질의의 결과가 없다는 뜻이며 사이트 전체의 광고 부재를 의미하지 않습니다. "
                 "대상 밖 결과만 반환된 질의와 같은 페이지가 반복된 질의도 따로 표시합니다.</p>")
    if queries:
        parts.append('<table class="queries"><thead><tr><th scope=col>검색어</th><th scope=col class="num">페이지</th>'
                     '<th scope=col>상태</th><th scope=col class="num">대상 링크</th><th scope=col class="num">신규 URL</th>'
                     '<th scope=col>진행/종료 이유</th></tr></thead>')
        for q in queries:
            error = f"<br><small>{_e(q.get('error'))}</small>" if q.get("error") else ""
            detail = (f"<details><summary>자세히</summary><small>"
                      f"검색 ID {_e(q.get('search_id', ''))} · 제공자 상태 {_e(q.get('provider_status', ''))} · 대기 {_e(q.get('elapsed_seconds', ''))}초<br>"
                      f"수신 링크 {_e(q.get('returned_links', '미확인'))} · 하위 링크 {_e(q.get('sitelinks', '미집계'))} · "
                      f"설정 페이지 한도 {_e(q.get('requested_pages', '미기록'))} · 범위 밖·유효하지 않은 링크 {_e(q.get('excluded_links', '미집계'))} · "
                      f"중복·상한 제외 {_e(q.get('duplicate_or_limited_links', '미집계'))}<br>"
                      f"검색 질의: {_e(q.get('query'))}"
                      + (f"<br>제공자 안내: {_e(' / '.join(q.get('provider_notices', [])))}" if q.get("provider_notices") else "")
                      + (f"<br>응답 모양: {_e(q.get('error_detail'))}" if q.get("error_detail") else "")
                      + "</small></details>")
            state = STATE_NAMES.get(q.get("state"), q.get("state"))
            chip = f'<span class="chip{" open" if q.get("state") in PROBLEM_STATES else ""}">{_e(state)}</span>'
            parts.append(f'<tr><td>{_e(q.get("term"))}</td><td class="num">{_e(q.get("page"))}</td><td>{chip}</td>'
                         f'<td class="num">{_e(q.get("target_links", 0))}</td><td class="num">{_e(q.get("new_urls", "-"))}</td>'
                         f'<td>{_e(q.get("end_reason", q.get("state")))}{error}{detail}</td></tr>')
        parts.append("</table>")
    else:
        parts.append('<p class="empty">수행한 질의가 없습니다.</p>')

    parts.append("""<table class="sign"><tr><th scope=col>담당</th><th scope=col>검토</th><th scope=col>승인</th></tr>
<tr><td></td><td></td><td></td></tr></table>
<p class="foot">이 보고서는 훤히가 검색엔진 결과와 현재 페이지를 비교해 자동 작성했습니다. 검색 결과는 검색 시점에 따라 달라집니다.</p>
</main></body></html>""")
    return "\n".join(parts)
