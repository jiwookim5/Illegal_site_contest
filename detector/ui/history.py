"""저장된 실행·조치 기록을 읽기 전용으로 표시한다."""
from html import escape
from datetime import datetime
import json
from pathlib import Path


def local_time(value):
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(value)


def review_text(row):
    if row is None:
        return "기록 없음"
    if row.get("kind") == "exclusion":
        return f"점검 제외: {row['url']} · 확인 사유: {row['reason']}"
    status = {"open": "미확인", "done": "확인", "fp": "오탐 처리"}.get(row.get("status"), "상태 미지정")
    parts = [status]
    if row.get("memo"):
        parts.append("메모: " + str(row["memo"]))
    if row.get("carried"):
        parts.append("이전 오탐 처리에서 이어받음")
    if row.get("checked_at"):
        parts.append("조치 확인: " + local_time(row["checked_at"]))
    return " · ".join(parts)


STATE_TONE = {"completed": "ok", "partial": "warn", "running": "warn", "failed": "bad", "cancelled": "warn"}

# 화면(C안)·보고서와 같은 범정부 디자인 시스템(KRDS) 값. 스크립트 없이 그린다 (기록 내용은 모두 이스케이프한다).
CSS = """
@font-face{font-family:"Pretendard";src:url("/fonts/PretendardVariable.woff2") format("woff2");font-weight:45 920}
:root{--ink:#1e2124;--ink-2:#464c53;--ink-3:#5f6870;--line:#b1b8be;--line-2:#d6dade;--gray:#f4f5f6;
  --red:#d7141e;--red-dark:#a80f16;--primary:#256ef4;--ok:#16703d}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:17px/1.6 "Pretendard","Malgun Gothic",system-ui,sans-serif;
  word-break:keep-all;overflow-wrap:anywhere;-webkit-font-smoothing:antialiased}
:focus-visible{outline:2px solid #fff;outline-offset:0;box-shadow:0 0 0 4px var(--primary)}
.top{border-bottom:2px solid var(--ink);padding:16px 24px;font-weight:800;font-size:19px}
.wrap{max-width:1000px;margin:0 auto;padding:32px 24px 56px}
h1{font-size:32px;font-weight:800;letter-spacing:-.025em;margin:0 0 8px;line-height:1.35}
.lead{color:var(--ink-2);margin:0 0 4px}
.lead.small{font-size:15px;color:var(--ink-3)}
h2{font-size:24px;font-weight:800;letter-spacing:-.02em;margin:40px 0 4px;padding-bottom:10px;border-bottom:2px solid var(--ink);
  display:flex;align-items:baseline;gap:8px}
h2 small{font-size:15px;font-weight:500;color:var(--ink-3)}
.hint{color:var(--ink-3);font-size:15px;margin:8px 0 8px}
.card{margin-top:0}
.day{font-size:15px;font-weight:700;color:var(--ink-2);background:var(--gray);padding:8px 14px;border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:64px 1fr auto;gap:2px 14px;padding:12px 14px;border-bottom:1px solid var(--line-2);align-items:start}
.time{color:var(--ink-3);font-size:15px;font-variant-numeric:tabular-nums;padding-top:1px}
.title{font-weight:700;word-break:break-all}
.meta{grid-column:2/4;color:var(--ink-3);font-size:15px;word-break:break-all}
.meta code{font-family:Consolas,"D2Coding",monospace;font-size:13px;color:var(--ink-2);background:var(--gray);border:1px solid var(--line-2);border-radius:2px;padding:0 5px}
.chip{white-space:nowrap;border:1px solid var(--ink-3);border-radius:4px;padding:0 8px;font-size:13px;font-weight:700;color:var(--ink-2)}
.chip.ok{border-color:var(--ok);color:var(--ok)}
.chip.warn,.chip.bad{border-color:var(--red);color:var(--red-dark)}
.change{grid-column:2/4;display:grid;grid-template-columns:auto 1fr;gap:2px 12px;font-size:15px;margin:6px 0 0;
  border-left:3px solid var(--line-2);padding-left:12px}
.change dt{color:var(--ink-3);white-space:nowrap}
.change dd{margin:0}
.change dd.after{font-weight:700}
.empty{color:var(--ink-2);padding:24px 0;text-align:center;border-bottom:1px solid var(--line-2)}
"""


def _rows_by_day(items):
    """[(local_time 문자열, 줄 HTML)] 를 날짜 머리말로 나눈다. 시각을 읽지 못한 기록은 '날짜 미상'으로 모은다."""
    out, day = [], None
    for when, row in items:
        d = when[:10] if len(when) >= 16 and when[4] == "-" else "날짜 미상"
        if d != day:
            out.append(f'<div class="day">{escape(d)}</div>')
            day = d
        out.append(row)
    return "".join(out)


def _clock(when):
    return when[11:16] if len(when) >= 16 and when[4] == "-" else ""


AD_TEXT_MAX = 60     # 이력 줄 제목에 보이는 광고 문구 길이


def _ad_labels(out_dir, run_ids, key_fn):
    """{항목 키: (광고 문구, 페이지 주소)}.

    이력에는 항목 키만 남으므로, 그 실행의 탐지 결과에서 같은 방식(key_fn)으로 키를 다시 계산해 찾는다.
    키는 normalized 글자로 만들므로 normalized 가 있는 last_result.json 을 읽는다 (result.json 에는 없다).
    실행 번호가 없는 옛 기록은 최근 결과(출력 폴더의 last_result.json)에서 찾는다.
    """
    labels = {}
    if key_fn is None:
        return labels
    root = Path(out_dir)
    paths = [root / "last_result.json" if rid is None else root / "runs" / rid / "last_result.json"
             for rid in run_ids if rid is None or Path(rid).name == rid]
    for path in paths:
        try:
            findings = json.loads(path.read_text(encoding="utf-8")).get("findings") or []
        except (OSError, ValueError, AttributeError):
            continue
        for f in findings:
            try:
                labels.setdefault(key_fn(f), (str(f.get("evidence_text") or ""), str(f.get("url") or "")))
            except (KeyError, TypeError, AttributeError):
                continue
    return labels


def _event_title(key, label):
    if not label or not " ".join(label[0].split()):
        return f'항목 <code>{escape(key)}</code>'
    text = " ".join(label[0].split())
    short = text if len(text) <= AD_TEXT_MAX else text[:AD_TEXT_MAX] + "…"
    return f'<span title="{escape(text)}">{escape(short)}</span>'


def history_html(out_dir, store, key_fn=None):
    """key_fn 을 주면(화면 서버의 finding_key) 조치 변경 항목을 광고 문구로 보인다."""
    root = Path(out_dir) / "runs"
    paths = sorted(root.glob("*/run.json"), reverse=True)
    runs = []
    states = {"running": "진행 중 또는 비정상 종료", "completed": "완료", "partial": "일부 점검",
              "failed": "실패", "cancelled": "시작 전 중지", "imported": "이전 버전에서 보존"}
    for path in paths[:200]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            when, url, status = local_time(doc["created_at"]), doc["entry_url"], doc["status"]
            label = states.get(status, status)
        except (OSError, ValueError, KeyError):
            when, url, status, label = "", "기록을 읽지 못함", "failed", "확인 필요"
        runs.append((when, f'''<div class="row"><span class="time">{escape(_clock(when))}</span>
<span class="title">{escape(str(url))}</span><span class="chip {STATE_TONE.get(status, "")}">{escape(str(label))}</span>
<span class="meta">기록 폴더 <code>{escape(path.parent.name)}</code> · {escape(str(path.parent))}</span></div>'''))
    events = []
    history = store.history()
    labels = _ad_labels(out_dir, {row["run_id"] for row in history}, key_fn)
    for row in history:
        when, key = local_time(row["at"]), str(row["key"])
        label = labels.get(key)
        where = f'{escape(label[1])} · ' if label and label[1] else ""
        events.append((when, f'''<div class="row"><span class="time">{escape(_clock(when))}</span>
<span class="title">{_event_title(key, label)}</span><span></span>
<span class="meta">{where}실행 {escape(str(row["run_id"] or "이전 버전 결과"))} · 항목 <code>{escape(key)}</code></span>
<dl class="change"><dt>변경 전</dt><dd>{escape(review_text(row["before"]))}</dd>
<dt>변경 후</dt><dd class="after">{escape(review_text(row["after"]))}</dd></dl></div>'''))
    return ('''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>훤히 점검·조치 이력</title>
<style>''' + CSS + '''</style></head><body><div class="top">훤히</div><main class="wrap">
<h1>점검·조치 이력</h1>
<p class="lead">지금까지의 점검 실행과, 담당자가 바꾼 조치 상태·메모를 시간순으로 보여 줍니다.</p>
<p class="lead small">최근 기록을 각각 최대 200건 표시합니다. 시간은 이 PC의 시간대입니다.
기록 폴더에는 점검 결과, 증거 사진, 점검 설정, 점검 키워드와 체크섬이 있습니다. 저장 공간은 자동 정리하지 않습니다.</p>
<h2>점검 실행 <small>''' + str(len(runs)) + '''건</small></h2>
<div class="card">''' + (_rows_by_day(runs) or '<p class="empty">아직 실행 기록이 없습니다.</p>') + '''</div>
<h2>조치 변경 <small>''' + str(len(events)) + '''건</small></h2>
<p class="hint">항목별 상태와 담당자 메모가 어떻게 바뀌었는지 확인합니다.</p>
<div class="card">''' + (_rows_by_day(events) or '<p class="empty">아직 조치 변경이 없습니다.</p>') + '''</div>
</main></body></html>''')
