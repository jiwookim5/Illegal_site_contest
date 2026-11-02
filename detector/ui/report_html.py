"""결재·보고에 붙일 수 있는 인쇄용 점검 결과 보고서.

화면의 결과를 한 장짜리 HTML 로 만든다. 앱 창에서 열어 [인쇄]를 누르면
PDF 로 저장하거나 종이로 출력할 수 있다. 증거 사진은 같은 서버에서 불러온다.
"""
import html
from collections import Counter
from datetime import datetime

from report import FAIL_NAMES
from judgement import label_of

TECH_NAMES = {
    "HOMOGLYPH": "닮은꼴 글자 위장", "JAMO": "자모 분해",
    "TRANSPARENT": "투명 텍스트", "OFFSCREEN": "화면 밖 은닉", "ETC": "추가 유형",
}
STATUS_NAMES = {"open": "미확인", "done": "확인", "fp": "오탐 처리"}
CHECK_NAMES = {"gone": "사라짐", "deleted": "페이지 삭제됨", "present": "아직 있음",
               "unknown": "확인 못 함", "skipped": "다시 점검으로 확인"}


def check_text(f):
    """'10/02 14:03 확인: 사라짐' 처럼 조치 확인 결과를 한 줄로. 확인한 적 없으면 빈 문자열."""
    if not f.get("check"):
        return ""
    when = (f.get("checked_at") or "").replace("T", " ")[5:16].replace("-", "/")
    return f"{when} 확인: {CHECK_NAMES.get(f['check'], f['check'])}"
STOP_NOTE = {
    "interrupted": "완료가 확인되지 않은 실행의 중간 저장 기록입니다.",
    "stalled": "진행이 정체되어 종료했습니다. 마지막 저장까지의 부분 결과입니다.",
    "user": "담당자가 점검을 중지해 일부 페이지만 점검한 결과입니다.",
    "time": "점검 시간 상한에 닿아 일부 페이지만 점검한 결과입니다.",
    "blocked": "페이지가 잇달아 열리지 않아 점검을 멈췄습니다. 서버가 요청을 막았거나 접속 장애가 의심됩니다.",
}
FAIL_SHOW = 100     # 보고서에 적는 열지 못한 페이지 수 (나머지는 scan_coverage.json)


def _e(v):
    return html.escape("" if v is None else str(v))


def _kind(f):
    if f["technique"] == "ETC" and f.get("extra_finding"):
        return f["extra_finding"].split("(", 1)[-1].rstrip(")")
    return TECH_NAMES.get(f["technique"], f["technique"])


def level_chip(f):
    """판정 등급(확실·의심·경계) 표시. 색만으로 구분하지 않도록 글자를 함께 쓴다."""
    level = f.get("judgement") or {}
    if level.get("level") not in ("high", "mid", "low", "review"):
        return ""
    return f' <span class="lv {level["level"]}">{_e(label_of(level))}</span>'


def duration(sec):
    """걸린 시간: 60초 미만은 '12.3초', 그 뒤로는 '1분 05초' (화면과 같은 표기)."""
    try:
        n = round(float(sec or 0), 1)     # 59.96초가 '60초'로 보이지 않게 먼저 반올림한다
    except (TypeError, ValueError):
        return "-"
    if n < 60:
        return f"{n:g}초"
    whole = int(n)
    return f"{whole // 60}분 {whole % 60:02d}초"


def _when(iso):
    """기록 시각을 이 PC 의 현지 시각으로. 결과 파일에는 UTC(+00:00)와 현지 시각이 섞여 있다."""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return (iso or "").replace("T", " ")[:16]


def _manner(p):
    """요청 간격·robots.txt 준수 여부. 대상 기관에 점검 방식을 설명할 때 쓴다."""
    if not p or not p.get("enabled"):
        return "빠른 점검 (요청 간격 없음)"
    text = f"천천히 점검 (페이지 사이 {p.get('delay', 0):g}초 간격"
    if p.get("respect_robots"):
        text += ", robots.txt 준수"
        if p.get("skipped_by_robots"):
            text += f" — 막힌 주소 {p['skipped_by_robots']}건 건너뜀"
    return text + ")"


SHARED_MIN = 3     # 이만큼 많은 페이지에 같은 광고가 있으면 공통 서식에 든 것으로 보고 한 줄로 묶는다


def shared_groups(rows):
    """(같은 위치·기법·문구로 여러 페이지에 든 광고 묶음들, 그 밖의 항목들)."""
    groups = {}
    for f in rows:
        groups.setdefault((f["technique"], f["location"], f["evidence_text"]), []).append(f)
    shared = [g for g in groups.values() if len({f["url"] for f in g}) >= SHARED_MIN]
    inside = {id(f) for g in shared for f in g}
    return shared, [f for f in rows if id(f) not in inside]


def ad_groups(rows):
    """화면의 entries와 같은 광고 단위: 공통 서식 묶음, 나머지는 페이지·위치별 묶음."""
    shared, rest = shared_groups(rows)
    groups = {}
    for f in rest:
        groups.setdefault((f["url"], f["location"]), []).append(f)
    return shared + list(groups.values())


def ad_count(rows):
    return len(ad_groups(rows))


def ad_status(rows):
    """한 광고의 상태가 섞였으면 화면과 같이 미조치, 조치완료, 오탐 순으로 집계한다."""
    states = {f["status"] for f in rows}
    return "open" if "open" in states else "done" if "done" in states else "fp"


# 화면(C안)과 같은 범정부 디자인 시스템(KRDS) 값: 회색 단계, 주조색 파랑, 위험 표시만 빨강.
# 인쇄할 때 바탕색이 빠져도 읽히도록 채운 색 위의 흰 글자는 쓰지 않는다(인쇄 단추 줄은 인쇄되지 않는다).
CSS = """
@font-face{font-family:"Pretendard";src:url("/fonts/PretendardVariable.woff2") format("woff2");font-weight:45 920}
:root{--ink:#1e2124;--ink-2:#464c53;--ink-3:#5f6870;--line:#b1b8be;--line-2:#d6dade;--gray:#f4f5f6;
  --red:#d7141e;--red-dark:#a80f16;--primary:#256ef4;--primary-60:#0b50d0}
*{box-sizing:border-box}
html{background:var(--gray)}
body{font-family:"Pretendard","Malgun Gothic",sans-serif;color:var(--ink);margin:0;padding:0 20px 48px;
  font-size:16px;line-height:1.6;word-break:keep-all;overflow-wrap:anywhere;-webkit-font-smoothing:antialiased;
  print-color-adjust:exact;-webkit-print-color-adjust:exact}
:focus-visible{outline:2px solid #fff;outline-offset:0;box-shadow:0 0 0 4px var(--primary)}
.bar{position:sticky;top:0;z-index:5;display:flex;justify-content:center;gap:8px;padding:14px 0;background:var(--gray)}
.bar button{font:inherit;font-size:17px;font-weight:700;height:48px;padding:0 24px;border-radius:6px;border:1px solid var(--primary);
  background:var(--primary);color:#fff;cursor:pointer}
.bar button:hover{background:var(--primary-60)}
.bar button.ghost{background:#fff;color:var(--ink);border-color:var(--ink-3);font-weight:600}
.sheet{max-width:960px;margin:0 auto;background:#fff;border:1px solid var(--line);border-top:3px solid var(--ink);padding:44px 48px 48px}
.eyebrow{color:var(--ink-3);font-weight:700;font-size:15px;margin:0 0 4px}
h1{font-size:32px;font-weight:800;letter-spacing:-.025em;margin:0 0 6px;line-height:1.35}
.sub{color:var(--ink-2);margin:0}
h2{font-size:24px;font-weight:800;letter-spacing:-.02em;margin:40px 0 12px}
h2 small{font-weight:500;color:var(--ink-3);font-size:15px;margin-left:6px}
p{margin:0 0 10px}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);margin:28px 0 0;border:1px solid var(--line);border-top:2px solid var(--ink)}
.tile{padding:12px 16px;border-right:1px solid var(--line-2)}
.tile:last-child{border-right:0}
.tile span{display:block;font-size:15px;color:var(--ink-2);font-weight:600}
.tile b{display:block;font-size:24px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.5}
.tile b small{font-size:15px;font-weight:600;margin-left:2px}
.tile.hot b{color:var(--red)}
.unit{margin:8px 0 0;color:var(--ink-3);font-size:15px}
dl.info{display:grid;grid-template-columns:170px 1fr;margin:0;border-top:2px solid var(--ink)}
dl.info dt,dl.info dd{margin:0;padding:11px 14px;border-bottom:1px solid var(--line-2)}
dl.info dt{background:var(--gray);font-weight:700}
dl.info dd{word-break:break-all}
table{border-collapse:collapse;width:100%;font-size:15px;border-top:2px solid var(--ink)}
thead{display:table-header-group}
th{text-align:left;font-weight:700;font-size:15px;padding:8px 12px;background:var(--gray);border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:12px;border-bottom:1px solid var(--line-2);vertical-align:top}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;width:90px}
.ev{word-break:break-all}
table.detail{table-layout:fixed}
table.detail th:nth-child(1){width:64px}
table.detail th:nth-child(2){width:25%}
table.detail th:nth-child(3){width:18%}
table.detail td:nth-child(4){word-break:keep-all}
table.detail th:nth-child(5){width:110px}
td small{color:var(--ink-2);font-size:13px}
code{font-family:Consolas,"D2Coding",monospace;font-size:13px;color:var(--ink-2);word-break:break-all}
.id{font-variant-numeric:tabular-nums;color:var(--ink-2);white-space:nowrap}
.chip{display:inline-block;white-space:nowrap;border:1px solid var(--ink-3);border-radius:4px;padding:0 7px;
  font-size:13px;font-weight:700;color:var(--ink-2);background:#fff}
.chip.open{border-color:var(--red);color:var(--red-dark)}
.lv{display:inline-block;white-space:nowrap;border:1px solid;border-radius:4px;padding:0 7px;margin-left:4px;font-size:13px;font-weight:700}
.lv::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;background:currentColor;vertical-align:1px}
.lv.high{color:var(--red-dark);border-color:var(--red);background:#fdeaea}
.lv.mid{color:#6b4e00;border-color:#d9a400;background:#fff6d6}
.lv.review,.lv.low{color:var(--ink-2);border-color:var(--line);background:var(--gray)}
.new{display:block;margin-top:4px;font-size:13px;font-weight:700;color:var(--red-dark)}
.note{border:1px solid var(--line);border-left:6px solid var(--red);padding:12px 16px;margin:18px 0 0;font-weight:600}
.shot img{max-width:100%;max-height:170px;border:1px solid var(--line-2);margin-top:6px}
.empty{color:var(--ink-2);padding:14px 0}
.sign{margin:44px 0 0 auto;width:auto;border-collapse:collapse;border-top:0}
.sign th,.sign td{border:1px solid var(--line);text-align:center;width:100px;padding:6px}
.sign th{background:var(--gray)}
.sign td{height:64px}
.foot{margin:28px 0 0;color:var(--ink-3);font-size:13px}
@page{size:A4;margin:15mm 12mm}
@media print{
  html,body{background:#fff}
  body{padding:0;font-size:12.5px}
  .bar{display:none}
  .sheet{max-width:none;padding:0;border:0}
  h1{font-size:24px}
  h2{font-size:17px;margin-top:28px}
  table,th,dl.info dt,dl.info dd,.tile span,.unit,.note{font-size:12px}
  .chip,td small,.new,.foot{font-size:11px}
  code{font-size:10.5px}
  .tile b{font-size:20px}
  tr,.tiles,dl.info{break-inside:avoid}
  h2{break-after:avoid}
}
@media(max-width:760px){.tiles{grid-template-columns:repeat(2,1fr)}.tile{border-bottom:1px solid var(--line-2)}.sheet{padding:28px 22px}}
"""


def build(payload, review=None):
    meta = payload.get("meta") or {}
    rows = payload.get("findings") or []
    if not meta:
        return "<!doctype html><meta charset=utf-8><p style='font:15px sans-serif;padding:24px'>" \
               "아직 점검 결과가 없습니다.</p>"
    kinds = Counter(_kind(f) for f in rows)
    groups = ad_groups(rows)
    states = Counter(ad_status(g) for g in groups)
    pages = len({f["url"] for f in rows if (f.get("judgement") or {}).get("decision") != "review"})
    hist = meta.get("history")

    finished = _when(meta.get("finished_at"))
    candidates = sum(all((f.get("judgement") or {}).get("decision") == "review" for f in g) for g in groups)
    ads = len(groups) - candidates
    left = states["open"]
    tiles = [("hot" if ads else "", "찾은 광고", ads, "건"), ("", "광고가 있는 페이지", pages, "곳"),
             ("hot" if left else "", "미확인", left, "건"),
             ("", "확인", states["done"], "건"),
             ("", "오탐 처리", states["fp"], "건")]
    if candidates:
        tiles.append(("", "경계 · 제출 제외", candidates, "건"))
    parts = [f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>불법광고 점검 결과 보고 {_e(finished[:10])}</title>
<style>{CSS}</style></head><body>
<div class="bar"><button onclick="print()">인쇄 · PDF로 저장</button>
<button class="ghost" onclick="window.close()">닫기</button></div>
<main class="sheet">
<p class="eyebrow">점검 결과 보고</p>
<h1>누리집 불법광고 점검 결과 보고</h1>
<p class="sub">{_e(meta.get("entry_url"))} · {_e(finished)} 점검</p>
<div class="tiles">""" + "".join(
        f'<div class="tile {c}"><span>{_e(k)}</span><b>{v}<small>{u}</small></b></div>' for c, k, v, u in tiles) + f"""</div>
<p class="unit">광고 판정 수는 같은 광고를 한 번만 세며 '경계 · 제출 제외' 항목은 빼고 셉니다. 이 항목은 광고 근거가 부족해 제출용 위반 항목에 포함하지 않습니다. 점검 항목은 {len(rows)}건입니다(한 광고에 숨긴 수법이 여럿이면 항목을 따로 셉니다).</p>
<h2>점검 정보</h2>
<dl class="info">
<dt>점검 대상</dt><dd>{_e(meta.get("entry_url"))}</dd>
<dt>점검 완료 시각</dt><dd>{_e(finished)}</dd>
<dt>확인한 페이지</dt><dd>{_e(meta.get("page_count"))}건 · 소요 {_e(duration(meta.get("elapsed_sec")))}</dd>
<dt>점검하지 못한 곳</dt><dd>{_e(" / ".join(meta.get("coverage_lines") or []) or "없음")}</dd>
<dt>점검 방식</dt><dd>{_e(_manner(meta.get("politeness")))}</dd>
<dt>점검 도구</dt><dd>훤히 — 공공 누리집 숨은 불법광고 점검 도구 (자동 점검)</dd>
</dl>"""]
    if meta.get("stopped"):
        parts.append(f'<p class="note">{_e(STOP_NOTE.get(meta["stopped"], ""))}</p>')

    cov = meta.get("coverage") or {}
    if cov.get("failed"):
        parts.append("<h2>열지 못한 페이지</h2><p>아래 페이지는 이번 점검에서 확인하지 못했습니다. "
                     "광고가 없다는 뜻이 아니므로 접속 상태를 확인한 뒤 다시 점검하십시오.</p>"
                     "<table><thead><tr><th scope=col>페이지</th><th scope=col>사유</th></tr></thead>")
        for f in cov["failed"][:FAIL_SHOW]:
            why = FAIL_NAMES.get(f["reason"], f["reason"]) + (f" ({f['status']})" if f.get("status") else "")
            parts.append(f'<tr><td class="ev">{_e(f["url"])}</td><td>{_e(why)}</td></tr>')
        if cov.get("failed_count", 0) > FAIL_SHOW:
            parts.append(f'<tr><td colspan="2">외 {cov["failed_count"] - FAIL_SHOW}건 (scan_coverage.json)</td></tr>')
        parts.append("</table>")

    parts.append('<h2>유형별 건수 <small>점검 항목 기준</small></h2>'
                 '<table><thead><tr><th scope=col>유형</th><th scope=col class="num">건수</th></tr></thead>')
    for k, n in kinds.most_common():
        parts.append(f'<tr><td>{_e(k)}</td><td class="num">{n}</td></tr>')
    if not kinds:
        parts.append('<tr><td colspan="2">찾은 광고가 없습니다.</td></tr>')
    parts.append("</table>")

    if hist:
        new = sum(1 for f in rows if f.get("is_new"))
        parts.append(f"""<h2>지난 점검과 비교</h2>
<dl class="info">
<dt>지난 점검</dt><dd>{_e(_when(hist.get("prev_finished")))} · {hist.get("prev_count", 0)}건</dd>
<dt>이번에 새로 생김</dt><dd>{new}건</dd>
<dt>이번에 사라짐</dt><dd>{hist.get("gone_count", 0)}건 (지워졌거나 조치된 것으로 보임)</dd>
</dl>""")
        if hist.get("gone"):
            parts.append("<table style='margin-top:14px'><thead><tr><th scope=col>페이지</th><th scope=col>유형</th>"
                         "<th scope=col>지난번 원문</th></tr></thead>")
            for g in hist["gone"]:
                parts.append(f'<tr><td class="ev">{_e(g.get("url"))}</td><td>{_e(_kind(g))}</td>'
                             f'<td class="ev">{_e((g.get("evidence_text") or "")[:160])}</td></tr>')
            parts.append("</table>")

    parts.append(f"<h2>상세 목록 <small>{len(rows)}건</small></h2>")
    if rows:
        parts.append("<table class=\"detail\"><thead><tr><th scope=col>번호</th><th scope=col>페이지 · 위치</th><th scope=col>유형 · 근거</th>"
                     "<th scope=col>광고 원문</th><th scope=col>조치</th></tr></thead>")
        shared, rest = shared_groups(rows)
        items = [(g[0], g) for g in shared] + [(f, None) for f in rest]
        for no, (f, same) in enumerate(items, 1):
            where = f'{_e(f["url"])}'
            if same:
                urls = sorted({r["url"] for r in same})
                more = f" 외 {len(urls) - 5}곳" if len(urls) > 5 else ""
                where = (f'<b>공통 서식 · 페이지 {len(urls)}곳</b><br>'
                         + "<br>".join(_e(u) for u in urls[:5]) + more)
                states_in = Counter(STATUS_NAMES.get(r["status"], r["status"]) for r in same)
            shot = (f'<div class="shot"><img src="{_e(f["evidence_image"])}" alt="증거 사진"></div>'
                    if f.get("evidence_image") else "")
            memo = f'<br><small>{_e(f["memo"])}</small>' if f.get("memo") else ""
            if check_text(f):
                memo = f'<br><small>{_e(check_text(f))}</small>' + memo
            if same:
                state = " ".join(f'<span class="chip">{_e(k)} {n}</span>' for k, n in states_in.items())
            else:
                state = (f'<span class="chip {_e(f["status"])}">'
                         f'{_e(STATUS_NAMES.get(f["status"], f["status"]))}</span>')
            new = '<span class="new">새로 생김</span>' if f.get("is_new") else ""
            parts.append(
                f'<tr><td class="id">{no}{new}</td>'
                f'<td class="ev">{where}<br><code>{_e(f["location"])}</code></td>'
                f'<td><b>{_e(_kind(f))}</b>{level_chip(f)}<br><small>{_e(f.get("reason"))}</small></td>'
                f'<td class="ev">{_e(f["evidence_text"][:300])}{shot}</td>'
                f'<td>{state}{memo}</td></tr>')
        parts.append("</table>")
    else:
        parts.append('<p class="empty">찾은 광고가 없습니다.</p>')

    parts.append("""<table class="sign"><tr><th scope=col>담당</th><th scope=col>검토</th><th scope=col>승인</th></tr>
<tr><td></td><td></td><td></td></tr></table>
<p class="foot">이 보고서는 훤히가 점검 당시 수집한 페이지 내용을 기준으로 자동 작성했습니다.</p>
</main></body></html>""")
    return "\n".join(parts)
