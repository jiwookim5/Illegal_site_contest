"""Local-only, reproducible easy/medium/hard crawler fixtures and answer export.

Run: python testsite/scenario_suite.py --port 8100 --export out/scenario-suite
This server never fetches or proxies an institution's website.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from contextlib import contextmanager
import hashlib
import importlib
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DIFFICULTIES = ("easy", "medium", "hard")
LABELS = {"easy": "하", "medium": "중", "hard": "상"}
TECHNIQUES = {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"}

from testsite.scenarios.transitions import (
    TRANSITION_META,
    TRANSITION_TYPES,
    get_transition_meta,
    get_transition_type,
    list_transition_types,
)


def route_key(value: str) -> str:
    parts = urlsplit(value)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return parts.path + ("?" + query if query else "")


def load_cases(difficulty: str = "all") -> list[dict]:
    if difficulty != "all" and difficulty not in DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium, hard or all")
    cases = [case for name in DIFFICULTIES if difficulty in ("all", name)
             for case in importlib.import_module(f"testsite.scenarios.{name}").build_cases()]
    for case in cases:
        ttype = get_transition_type(case.get("family", ""), case)
        case["transition_type"] = ttype
        tags = case.setdefault("tags", [])
        if ttype not in tags:
            tags.append(ttype)
    validate_cases(cases)
    return cases


def validate_cases(cases: list[dict]) -> None:
    ids, route_ids = set(), set()
    for case in cases:
        cid = case["id"]
        if cid in ids or case["difficulty"] not in DIFFICULTIES:
            raise ValueError(f"duplicate case or invalid difficulty: {cid}")
        if "transition_type" in case and case["transition_type"] not in TRANSITION_TYPES:
            raise ValueError(f"invalid transition_type: {cid}")
        ids.add(cid)
        prefix = f"/cases/{cid}/"
        for value in [case["entry"]] + [cp["path"] for cp in case["checkpoints"]]:
            parts = urlsplit(value)
            if parts.scheme or parts.netloc or parts.fragment or not parts.path.startswith(prefix) or ".." in parts.path.split("/"):
                raise ValueError(f"entry/checkpoint outside case: {value}")
        if not case["family"] or not case["group_id"] or not case["description"]:
            raise ValueError(f"missing provenance/group: {cid}")
        routes = case["routes"]
        keys = {route_key(p) for p in routes}
        if len(keys) != len(routes) or route_key(case["entry"]) not in keys:
            raise ValueError(f"invalid routes/entry: {cid}")
        for path, response in routes.items():
            parts = urlsplit(path)
            if parts.scheme or parts.netloc or parts.fragment or not parts.path.startswith(prefix):
                raise ValueError(f"route outside case: {path}")
            if ".." in parts.path.split("/") or route_key(path) in route_ids:
                raise ValueError(f"invalid/duplicate route: {path}")
            route_ids.add(route_key(path))
            if not isinstance(response["body"], str) or not 100 <= response.get("status", 200) <= 599:
                raise ValueError(f"invalid response: {path}")
            for status in response.get("status_sequence", []):
                if not isinstance(status, int) or not 100 <= status <= 599:
                    raise ValueError(f"invalid status sequence: {path}")
        seen_targets = set()
        for checkpoint in case["checkpoints"]:
            key = route_key(checkpoint["path"])
            if key not in keys and urlsplit(key).path not in keys:
                raise ValueError(f"checkpoint route missing: {cid}")
            for step in checkpoint.get("steps", []):
                if step["action"] not in ("click", "wait", "scroll"):
                    raise ValueError(f"unsupported oracle step: {cid}")
                if step["action"] == "wait" and not 0 <= step["ms"] <= 3000:
                    raise ValueError(f"unbounded wait: {cid}")
            for target in checkpoint["targets"]:
                if not target["text"].strip() or not target["selector"]:
                    raise ValueError(f"empty target: {cid}")
                if not set(target["techniques"]) <= TECHNIQUES:
                    raise ValueError(f"invalid technique: {cid}")
                if len(target["techniques"]) != len(set(target["techniques"])):
                    raise ValueError(f"duplicate technique: {cid}")
                if target["role"] not in ("positive", "negative", "coverage"):
                    raise ValueError(f"invalid target role: {cid}")
                if bool(target["techniques"]) != (target["role"] == "positive"):
                    raise ValueError(f"role/answer mismatch: {cid}")
                identity = (key, tuple(target.get("frames", [])), target["selector"], target["text"])
                if identity in seen_targets:
                    raise ValueError(f"duplicate checkpoint target: {cid}")
                seen_targets.add(identity)
        for forbidden in case.get("forbidden_requests", []):
            if not forbidden.startswith(prefix):
                raise ValueError(f"forbidden request outside fixture: {cid}")


def trap_content_metrics(cases: list[dict]) -> dict:
    """Count authored pool pages separately from negative oracle checkpoints."""
    pages = [sum('data-negative-trap="true"' in r['body'] for r in c['routes'].values()) for c in cases]
    return {"negative_trap_cases": sum(n > 0 for n in pages), "negative_trap_pages": sum(pages)}


def inventory(cases: list[dict]) -> dict:
    counts = {}
    total_pages = sum(len(c["routes"]) for c in cases)
    total_traps = sum(
        1 for c in cases
        if any(t.get("role") == "negative" for cp in c.get("checkpoints", []) for t in cp.get("targets", []))
    )
    total_trap_targets = sum(
        1 for c in cases
        for cp in c.get("checkpoints", [])
        for t in cp.get("targets", [])
        if t.get("role") == "negative"
    )
    for difficulty in DIFFICULTIES:
        selected = [c for c in cases if c["difficulty"] == difficulty]
        targets = [t for c in selected for cp in c["checkpoints"] for t in cp["targets"]]
        diff_traps = sum(
            1 for c in selected
            if any(t.get("role") == "negative" for cp in c.get("checkpoints", []) for t in cp.get("targets", []))
        )
        diff_trap_targets = sum(
            1 for c in selected
            for cp in c.get("checkpoints", [])
            for t in cp.get("targets", [])
            if t.get("role") == "negative"
        )
        counts[difficulty] = {
            "cases": len(selected), "families": len({c["family"] for c in selected}),
            "routes": sum(len(c["routes"]) for c in selected), "targets": len(targets),
            "negative_traps": diff_traps,
            "negative_trap_targets": diff_trap_targets,
            **trap_content_metrics(selected),
            "roles": dict(Counter(t["role"] for t in targets)),
            "required_findings": sum(len(t["techniques"]) for t in targets),
            "techniques": dict(Counter(tech for t in targets for tech in t["techniques"])),
        }
    trans_counts = dict(Counter(c.get("transition_type") or get_transition_type(c.get("family", ""), c) for c in cases))
    return {"format_version": 1, "cases": len(cases),
            "total_pages": total_pages,
            "total_routes": total_pages,
            "negative_traps": total_traps,
            "negative_trap_targets": total_trap_targets,
            **trap_content_metrics(cases),
            "negative_traps_definition": "cases with negative oracle checkpoints; negative_trap_cases counts authored pool content",
            "difficulty": counts,
            "transition_counts": trans_counts,
            "origin": "synthetic_templates_informed_by_user_supplied_structure_reports",
            "real_institution_data": False, "independent_benchmark_verified": False,
            "split_policy": "single regression/challenge pool; keep group_id together if later splitting",
            "label_policy": "authored expectations; never generated from detector predictions",
            "scope": "UI collection, required technique/evidence/location, negatives, failure reporting",
            "source_statistics_verified": False,
            "limits": "Template variants are correlated; counts are not independent institutions or accuracy claims."}



def export_cases(cases: list[dict], directory: Path) -> dict:
    """Write new exports exclusively so a prior answer version cannot be overwritten."""
    directory.mkdir(parents=True, exist_ok=True)
    summary = inventory(cases)
    raw = (json.dumps(cases, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    summary["cases_sha256"] = hashlib.sha256(raw).hexdigest()
    answers = [{"case_id": c["id"], "difficulty": c["difficulty"], "family": c["family"],
                "transition_type": c.get("transition_type") or get_transition_type(c.get("family", ""), c),
                "group_id": c["group_id"], "path": cp["path"], "steps": cp.get("steps", []), **t}
               for c in cases for cp in c["checkpoints"] for t in cp["targets"]]
    answer_bytes = ''.join(json.dumps(a, ensure_ascii=False) + "\n" for a in answers).encode("utf-8")
    summary["answers_sha256"] = hashlib.sha256(answer_bytes).hexdigest()
    artifacts = {"cases.json": raw,
                 "answers.jsonl": answer_bytes,
                 "inventory.json": (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")}
    for name in artifacts:
        if (directory / name).exists():
            raise FileExistsError(f"export already exists: {directory / name}")
    for name, content in artifacts.items():
        with (directory / name).open("xb") as stream:
            stream.write(content)
    return summary


class SuiteServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, cases: list[dict], port: int = 0):
        validate_cases(cases)
        self.cases = cases
        self.routes = {route_key(path): response for case in cases for path, response in case["routes"].items()}
        self.requests = deque(maxlen=100000)
        self.hits = Counter()
        self.get_hits = Counter()
        self.state_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), SuiteHandler)

    @property
    def base(self):
        return f"http://127.0.0.1:{self.server_port}"

    def reset_observations(self):
        with self.state_lock:
            self.hits.clear()
            self.get_hits.clear()
            self.requests.clear()

    def record_request(self, method: str, key: str) -> int:
        with self.state_lock:
            self.requests.append({"method": method, "path": key})
            self.hits[key] += 1
            if method == "GET":
                self.get_hits[key] += 1
            # HEAD observes the next GET status and never consumes its sequence.
            return max(1, self.get_hits[key] + (method == "HEAD"))


def index_html(cases, difficulty=None, transition_type=None):
    # A difficulty entry must not lead the crawler into the other levels.
    all_active = "active" if difficulty is None else ""
    suffix = "?" + urlencode({"transition": transition_type}) if transition_type in TRANSITION_TYPES else ""
    links = f'<li><a class="{all_active}" href="/{suffix}">전체 난이도</a></li>' if difficulty else ''
    links += ''.join(f'<li><a class="{"active" if difficulty == d else ""}" href="/{d}/{suffix}">{LABELS[d]} 난이도</a></li>' for d in DIFFICULTIES)
    selected_cases = [c for c in cases if difficulty is None or c["difficulty"] == difficulty]
    total_count = len(selected_cases)

    # Route & Negative Trap metrics
    all_routes_count = sum(len(c["routes"]) for c in cases)
    selected_routes_count = sum(len(c["routes"]) for c in selected_cases)
    all_traps_count = sum(
        1 for c in cases
        if any(t.get("role") == "negative" for cp in c.get("checkpoints", []) for t in cp.get("targets", []))
    )
    selected_traps_count = sum(
        1 for c in selected_cases
        if any(t.get("role") == "negative" for cp in c.get("checkpoints", []) for t in cp.get("targets", []))
    )
    all_trap_targets = sum(
        1 for c in cases
        for cp in c.get("checkpoints", [])
        for t in cp.get("targets", [])
        if t.get("role") == "negative"
    )
    selected_trap_targets = sum(
        1 for c in selected_cases
        for cp in c.get("checkpoints", [])
        for t in cp.get("targets", [])
        if t.get("role") == "negative"
    )
    all_negative_cases = all_traps_count
    all_traps_count = trap_content_metrics(cases)["negative_trap_cases"]
    selected_traps_count = trap_content_metrics(selected_cases)["negative_trap_cases"]

    easy_cases = [c for c in cases if c["difficulty"] == "easy"]
    medium_cases = [c for c in cases if c["difficulty"] == "medium"]
    hard_cases = [c for c in cases if c["difficulty"] == "hard"]

    # Transition counts for pills
    trans_counts = Counter(c.get("transition_type") or get_transition_type(c.get("family", ""), c) for c in selected_cases)
    pills = [f'<button class="pill-btn {"active" if not transition_type else ""}" data-val="" onclick="filterTable(\'\')">전체 ({total_count})</button>']
    options = [f'<option value="">전체 이동 방식 ({len(TRANSITION_TYPES)}종 / {total_count}건)</option>']
    for t in TRANSITION_TYPES:
        meta = get_transition_meta(t)
        cnt = trans_counts.get(t, 0)
        is_selected = "selected" if transition_type == t else ""
        options.append(f'<option value="{t}" {is_selected}>{meta["short_name"]} - {meta["name"]} ({cnt}건)</option>')
        if cnt > 0:
            pills.append(f'<button class="pill-btn {"active" if transition_type == t else ""}" data-val="{t}" onclick="filterTable(\'{t}\')">{meta["short_name"]} <span class="pill-cnt">{cnt}</span></button>')
    pill_bar_html = "".join(pills)
    options_html = "".join(options)

    rows = []
    for c in selected_cases:
        diff_label = LABELS[c["difficulty"]]
        diff_class = f"badge-{c['difficulty']}"
        ttype = c.get("transition_type") or get_transition_type(c.get("family", ""), c)
        tmeta = get_transition_meta(ttype)
        tbadge = f'<span class="badge" style="background:{tmeta["badge_color"]}18; color:{tmeta["badge_color"]}; border:1px solid {tmeta["badge_color"]}55;" title="{escape(tmeta["name"])}: {escape(tmeta["crawling_focus"])}">{escape(tmeta["short_name"])}</span>'

        targets = [t for cp in c.get("checkpoints", []) for t in cp.get("targets", [])]
        tech_list = sorted({tech for t in targets for tech in t.get("techniques", [])})
        tech_badges = " ".join(f'<span class="badge badge-tech">{t}</span>' for t in tech_list) if tech_list else '<span class="badge badge-none">-</span>'
        has_pos = any(t.get("role") == "positive" for t in targets)
        has_neg = any(t.get("role") == "negative" for t in targets)
        if has_pos and has_neg:
            role_badge = '<span class="badge badge-pos">양성</span> <span class="badge badge-trap">미끼</span>'
        elif has_pos:
            role_badge = '<span class="badge badge-pos">양성</span>'
        else:
            role_badge = '<span class="badge badge-trap" title="오탐 방지 미끼 (Negative Trap)">오탐미끼</span>'

        pages_cnt = len(c.get("routes", {}))
        page_badge = f'<span class="badge badge-page" title="해당 시나리오 가상 라우트/페이지 수: {pages_cnt}개">{pages_cnt}p</span>'

        rows.append(
            f'<tr data-transition="{ttype}">'
            f'<td><span class="badge {diff_class}">{diff_label}</span></td>'
            f'<td><a class="case-link" href="{escape(c["entry"], quote=True)}">{escape(c["id"])}</a></td>'
            f'<td>{page_badge}</td>'
            f'<td>{tbadge}</td>'
            f'<td><code>{escape(c["family"])}</code></td>'
            f'<td>{escape(c["description"])}</td>'
            f'<td>{role_badge}</td>'
            f'<td>{tech_badges}</td>'
            f'</tr>'
        )
    table_rows = "".join(rows)

    title = f"{LABELS[difficulty]} 난이도 합성 테스트셋" if difficulty else "난이도별 합성 테스트셋"
    header_title = f"{LABELS[difficulty]} 난이도 시나리오 목록 ({total_count}건)" if difficulty else f"공공 게시판 합성 테스트셋 (총 {total_count}건)"

    css = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", sans-serif; margin: 0; background: #f8fafc; color: #1e293b; line-height: 1.5; }
.header-bar { background: #1e3a8a; color: #fff; padding: 20px 32px; border-bottom: 4px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.header-bar h1 { margin: 0 0 6px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
.header-bar p { margin: 0; font-size: 14px; color: #bfdbfe; }
.container { max-width: 1360px; margin: 24px auto; padding: 0 24px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: #fff; padding: 18px 20px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.card-label { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.card-value { font-size: 28px; font-weight: 800; color: #0f172a; margin-top: 4px; }
.card-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }
.nav-wrap { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
nav ul { list-style: none; display: flex; gap: 8px; margin: 0; padding: 0; }
nav a { display: inline-block; padding: 8px 16px; background: #fff; border: 1px solid #cbd5e1; border-radius: 6px; text-decoration: none; color: #334155; font-size: 14px; font-weight: 600; transition: all 0.2s; }
nav a:hover, nav a.active { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.trans-select-wrap { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #334155; }
.trans-select-wrap select { padding: 9px 12px; font-size: 14px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; color: #1e293b; outline: none; }
.trans-select-wrap select:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }
.pill-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.pill-btn { border: 1px solid #e2e8f0; background: #fff; color: #475569; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.pill-btn:hover { background: #f1f5f9; border-color: #94a3b8; color: #0f172a; }
.pill-btn.active { background: #2563eb; border-color: #1d4ed8; color: #fff; }
.pill-btn.active .pill-cnt { background: rgba(255,255,255,0.25); color: #fff; }
.pill-cnt { display: inline-block; background: #f1f5f9; color: #64748b; padding: 1px 6px; border-radius: 10px; font-size: 11px; margin-left: 2px; }
.search-box { position: relative; flex: 1; min-width: 260px; }
.search-box input { width: 100%; box-sizing: border-box; padding: 9px 14px; font-size: 14px; border: 1px solid #cbd5e1; border-radius: 6px; outline: none; background: #fff; }
.search-box input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }
.table-wrap { background: #fff; border-radius: 10px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }
thead { background: #f1f5f9; border-bottom: 2px solid #e2e8f0; }
th { padding: 12px 14px; font-weight: 700; color: #475569; }
td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
tr:hover td { background: #f8fafc; }
.case-link { font-family: monospace; font-size: 13px; font-weight: 700; color: #2563eb; text-decoration: none; background: #eff6ff; padding: 4px 8px; border-radius: 4px; border: 1px solid #dbeafe; }
.case-link:hover { background: #dbeafe; text-decoration: underline; }
code { font-family: monospace; font-size: 12px; color: #0f766e; background: #f0fdfa; padding: 2px 6px; border-radius: 4px; }
.badge { display: inline-block; padding: 3px 8px; font-size: 11px; font-weight: 700; border-radius: 9999px; text-transform: uppercase; white-space: nowrap; }
.badge-easy { background: #dcfce7; color: #15803d; }
.badge-medium { background: #dbeafe; color: #1d4ed8; }
.badge-hard { background: #fee2e2; color: #b91c1c; }
.badge-pos { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.badge-neg { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
.badge-trap { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; font-weight: 700; }
.badge-page { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; font-weight: 700; }
.badge-tech { background: #f3e8ff; color: #7e22ce; border: 1px solid #e9d5ff; margin-right: 4px; }
.badge-none { color: #94a3b8; font-weight: 400; }
.footer { margin-top: 32px; padding: 20px 0; text-align: center; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0; }
"""

    js = """
<script>
function filterTable(transOverride) {
  var searchInput = document.getElementById("suite-search");
  var transSelect = document.getElementById("suite-trans");
  if (typeof transOverride === "string") {
    if (transSelect) transSelect.value = transOverride;
  }
  var textFilter = searchInput ? searchInput.value.toLowerCase() : "";
  var transFilter = transSelect ? transSelect.value : "";
  var rows = document.querySelectorAll("#scenario-table tbody tr");
  var matched = 0;
  rows.forEach(function(row) {
    var text = row.textContent.toLowerCase();
    var rowTrans = row.getAttribute("data-transition") || "";
    var matchText = !textFilter || text.indexOf(textFilter) > -1;
    var matchTrans = !transFilter || rowTrans === transFilter;
    if (matchText && matchTrans) {
      row.style.display = "";
      matched++;
    } else {
      row.style.display = "none";
    }
  });
  var counter = document.getElementById("matched-counter");
  if (counter) counter.innerText = matched + "건 표시 중";

  document.querySelectorAll(".pill-btn").forEach(function(btn) {
    if (btn.getAttribute("data-val") === transFilter) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  var url = new URL(location.href);
  if (transFilter) url.searchParams.set("transition", transFilter);
  else url.searchParams.delete("transition");
  if (textFilter) url.searchParams.set("search", searchInput.value);
  else url.searchParams.delete("search");
  history.replaceState(null, "", url);
  document.querySelectorAll(".nav-wrap nav a").forEach(function(link) {
    var destination = new URL(link.href);
    destination.search = url.search;
    link.href = destination.href;
  });
}
document.addEventListener("DOMContentLoaded", function() {
  document.getElementById("suite-search").value = new URL(location.href).searchParams.get("search") || "";
  filterTable();
});
</script>
"""

    nav_bar = f'<nav><ul>{links}</ul></nav>' if links else '<nav></nav>'

    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f'<title>{title}</title><style>{css}</style></head><body>'
        f'<header class="header-bar"><h1>{header_title}</h1>'
        f'<p>로컬 기능 검증용이며 실제 기관 사이트·독립 정확도 자료가 아닙니다 · 수집 데이터셋(outputs/google_dataset_20260930) 실측 어휘 반영</p></header>'
        f'<main class="container">'
        f'<div class="stats-grid">'
        f'<div class="card"><div class="card-label">표시 시나리오</div><div class="card-value">{total_count}건</div><div class="card-sub">로컬 고도화 합성 테스트셋 (전체 {len(cases)}건)</div></div>'
        f'<div class="card"><div class="card-label">총 가상 게시글/페이지</div><div class="card-value">{selected_routes_count}개</div><div class="card-sub">총 가상 게시글/페이지: {all_routes_count}개</div></div>'
        f'<div class="card"><div class="card-label">오탐 방지 미끼 (Negative Trap)</div><div class="card-value">{selected_traps_count}건</div><div class="card-sub">미끼 게시글 탑재: 전체 {all_traps_count}개 시나리오 · 음성 정답 체크포인트: {all_trap_targets}개</div></div>'
        f'<div class="card"><div class="card-label">하 (Easy)</div><div class="card-value">{len(easy_cases)}건</div><div class="card-sub">게시글/페이지 {sum(len(c["routes"]) for c in easy_cases)}개 · 표형·카드·상세 GET</div></div>'
        f'<div class="card"><div class="card-label">중 (Medium)</div><div class="card-value">{len(medium_cases)}건</div><div class="card-sub">게시글/페이지 {sum(len(c["routes"]) for c in medium_cases)}개 · iframe·동적교체·폼</div></div>'
        f'<div class="card"><div class="card-label">상 (Hard)</div><div class="card-value">{len(hard_cases)}건</div><div class="card-sub">게시글/페이지 {sum(len(c["routes"]) for c in hard_cases)}개 · 복합위장·비동기·스크롤</div></div>'
        f'</div>'
        f'<div class="nav-wrap">'
        f'{nav_bar}'
        f'</div>'
        f'<div class="pill-bar">{pill_bar_html}</div>'
        f'<div class="filter-row">'
        f'<div class="trans-select-wrap">'
        f'<label for="suite-trans">페이지 이동 방식:</label>'
        f'<select id="suite-trans" onchange="filterTable()">{options_html}</select>'
        f'</div>'
        f'<div class="search-box">'
        f'<input type="search" id="suite-search" placeholder="🔍 사례 ID, 이동방식, 패턴, 기법, 설명 검색..." oninput="filterTable()">'
        f'</div>'
        f'</div>'
        f'<div class="table-wrap"><table id="scenario-table"><thead><tr>'
        f'<th style="width:65px">난이도</th><th style="width:105px">사례</th><th style="width:55px">페이지</th><th style="width:125px">이동 방식</th><th style="width:160px">패턴</th><th>설명</th><th style="width:75px">구분</th><th style="width:160px">은닉기법</th>'
        f'</tr></thead><tbody>{table_rows}</tbody></table></div>'
        f'<footer class="footer"><p>공공 웹사이트 불법광고 탐지 도구 합성 테스트 스위트 (포트 8100) · <span id="matched-counter">{total_count}건 표시 중</span> · 총 가상 게시글/페이지: {all_routes_count}개 · 오탐 미끼 탑재: {all_traps_count}건 · 음성 정답 시나리오: {all_negative_cases}건 · <a href="/api/inventory" target="_blank">API 명세(/api/inventory)</a> · <a href="/api/stats" target="_blank">서버 통계(/api/stats)</a> · <a href="/api/cases" target="_blank">시나리오 목록(/api/cases)</a></p></footer>'
        f'</main>{js}</body></html>'
    )



class SuiteHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _serve(self, head=False):
        key = route_key(self.path)
        count = self.server.record_request(self.command, key)
        path = urlsplit(key).path
        if path == "/api/inventory":
            summary = inventory(self.server.cases)
            raw = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return
        if path == "/api/cases":
            params = dict(parse_qsl(urlsplit(key).query))
            filtered = self.server.cases
            if "difficulty" in params and params["difficulty"] in DIFFICULTIES:
                filtered = [c for c in filtered if c["difficulty"] == params["difficulty"]]
            if "transition" in params and params["transition"]:
                target_trans = params["transition"]
                filtered = [c for c in filtered if (c.get("transition_type") or get_transition_type(c.get("family", ""), c)) == target_trans]
            if "q" in params or "search" in params:
                query_str = (params.get("q") or params.get("search", "")).lower()
                filtered = [c for c in filtered if query_str in c["id"].lower() or query_str in c["family"].lower() or query_str in c.get("description", "").lower()]
            data = [{
                "id": c["id"],
                "difficulty": c["difficulty"],
                "family": c["family"],
                "transition_type": c.get("transition_type") or get_transition_type(c.get("family", ""), c),
                "transition_name": get_transition_meta(c.get("transition_type") or get_transition_type(c.get("family", ""), c))["name"],
                "transition_short_name": get_transition_meta(c.get("transition_type") or get_transition_type(c.get("family", ""), c))["short_name"],
                "description": c.get("description", ""),
                "entry": c["entry"],
                "routes_count": len(c.get("routes", {})),
                "is_negative_trap": any(t.get("role") == "negative" for cp in c.get("checkpoints", []) for t in cp.get("targets", [])),
                **trap_content_metrics([c]),
                "tags": c.get("tags", []),
                "target_count": sum(len(cp.get("targets", [])) for cp in c.get("checkpoints", [])),
            } for c in filtered]
            raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return
        if path == "/api/stats":
            total_pages = sum(len(c["routes"]) for c in self.server.cases)
            trap_cases = sum(
                1 for c in self.server.cases
                if any(t.get("role") == "negative" for cp in c.get("checkpoints", []) for t in cp.get("targets", []))
            )
            trap_targets = sum(
                1 for c in self.server.cases
                for cp in c.get("checkpoints", [])
                for t in cp.get("targets", [])
                if t.get("role") == "negative"
            )
            with self.server.state_lock:
                stats = {
                    "total_cases": len(self.server.cases),
                    "total_pages": total_pages,
                    "total_routes": total_pages,
                    "negative_traps": trap_cases,
                    "negative_trap_targets": trap_targets,
                    **trap_content_metrics(self.server.cases),
                    "total_requests": len(self.server.requests),
                    "unique_routes_hit": len(self.server.hits),
                    "top_hits": self.server.hits.most_common(10),
                }
            raw = (json.dumps(stats, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return
        if path == "/" or path in {f"/{d}/" for d in DIFFICULTIES}:
            query_params = dict(parse_qsl(urlsplit(key).query))
            body = index_html(self.server.cases, path.strip("/") or None, transition_type=query_params.get("transition"))
            response = {"body": body}
        else:
            response = self.server.routes.get(key)
            paging_query = any(name.lower() in {"page", "pageindex", "pageno", "pagenum"}
                               for name, _ in parse_qsl(urlsplit(key).query))
            if response is None and not paging_query:
                response = self.server.routes.get(path)
            if response is None:
                response = {"status": 404, "body": "fixture not found"}
        sequence = response.get("status_sequence", [])
        status = sequence[min(count - 1, len(sequence) - 1)] if sequence else response.get("status", 200)
        raw = response["body"].encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", response.get("content_type", "text/html; charset=utf-8"))
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for name, value in response.get("headers", {}).items():
            self.send_header(name, str(value))
        self.end_headers()
        if not head:
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        self._serve()

    def do_HEAD(self):
        self._serve(head=True)

    def do_POST(self):
        self.server.record_request("POST", route_key(self.path))
        self.send_error(405, "Synthetic fixture does not accept writes")


@contextmanager
def running_server(cases, port=0):
    server = SuiteServer(cases, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--difficulty", choices=("all",) + DIFFICULTIES, default="all")
    parser.add_argument("--export", type=Path, help="new directory for cases.json and inventory.json")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    cases = load_cases(args.difficulty)
    summary = export_cases(cases, args.export) if args.export else inventory(cases)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.export_only:
        return
    with running_server(cases, args.port) as server:
        print(f"목업 서버: {server.base}/ (Ctrl+C 종료)", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
