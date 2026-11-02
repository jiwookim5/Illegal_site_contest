"""검색 화면에서 발견한 원본 URL과 현재 페이지의 상태를 대조한다.

기존 탐지기를 변경하지 않는 선택 기능. 검색 화면 구조가 달라지거나 차단되면
성공 0건과 구별한다. 색인 삭제 요청은 수행하지 않는다.
"""
import csv
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit
from uuid import uuid4

from csv_safe import csv_text
from fileio import write_json
from urls import is_state_change_url

ENGINES = {"google": "구글"}
KST = timezone(timedelta(hours=9))
MAX_URLS = 300


def now():
    return datetime.now(KST).isoformat(timespec="seconds")


def target_host(value):
    value = value.strip()
    p = urlsplit(value if "://" in value else "https://" + value)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("올바른 타깃 도메인 또는 http(s) URL을 입력하세요.")
    host = p.hostname.rstrip(".").encode("idna").decode().lower()
    if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
        raise ValueError("도메인 형식을 확인하세요.")
    return host


# 등록 도메인이 끝 3개 라벨인 .kr 하위 영역(예: yangyang.go.kr). 목록에 없는 .kr 은 끝 2개 라벨로 본다.
KR_SECOND_LEVEL = {"go", "ac", "or", "co", "re", "mil", "hs", "ms", "es", "sc", "ne", "pe", "kg"}
# .kr 이외 국가 코드 도메인의 흔한 2단계 영역(co.uk, com.au 등). 2개 라벨로 줄이면 co.uk 전체를 검색하게 된다.
CC_SECOND_LEVEL = {"co", "com", "or", "org", "ne", "net", "ac", "go", "gov", "edu"}


def registrable_domain(host):
    """검색 범위를 넓힐 때 쓰는 등록 도메인. 공개 접미사 목록 없이 단순 규칙만 쓴다."""
    host = (host or "").strip().rstrip(".").lower()
    labels = host.split(".")
    if len(labels) < 3 or ":" in host or all(l.isdigit() for l in labels):
        return host          # 점이 없는 이름, 등록 도메인 자체, IP 는 그대로
    if labels[-1] == "kr":
        keep = 3 if labels[-2] in KR_SECOND_LEVEL else 2
    elif len(labels[-1]) == 2 and labels[-2] in CC_SECOND_LEVEL:
        keep = 3
    else:
        keep = 2
    return ".".join(labels[-keep:])


def in_scope(url, host, subdomains=False):
    try:
        p = urlsplit(url)
        name = (p.hostname or "").rstrip(".").encode("idna").decode().lower()
        return (p.scheme in ("http", "https") and not p.username and not p.password
                and (name == host or (subdomains and name.endswith("." + host))))
    except (ValueError, UnicodeError):
        return False


def search_url(engine, query, page=1, include_omitted=False):
    if engine == "google":
        params = {"q": query, "start": (page - 1) * 10, "hl": "ko", "gl": "kr"}
        if include_omitted:
            params['filter'] = 0
        return "https://www.google.com/search?" + urlencode(params)
    raise ValueError("지원하지 않는 검색엔진")


def result_url(href, base):
    """알려진 검색 리다이렉트만 해제. 목적지 쿼리의 순서·중복·인코딩은 유지한다."""
    url = urljoin(base, href)
    p = urlsplit(url)
    if (p.hostname or "") in ("www.google.com", "www.google.co.kr") and p.path == "/url":
        q = parse_qs(p.query)
        return (q.get("q") or q.get("url") or [url])[0]
    return url


# 후보 링크만 읽으며 클릭하지 않는다. 원본 화면은 질의별로 별도 보존한다.
EXTRACT_JS = r"""() => Array.from(document.querySelectorAll('a[href]')).filter(a =>
  a.getClientRects().length && (a.querySelector('h3') || a.innerText.trim())).map(a => {
    const box = a.closest('.g, .MjjYud')
      || a.parentElement;
    return {href:a.getAttribute('href'), title:(a.querySelector('h3') || a).innerText.trim().slice(0,1000),
      snippet:(box ? box.innerText : '').trim().slice(0,3000)};
  })"""


def search_state(url, body, status):
    low = body.lower()
    if status in (401, 403, 429) or "/sorry/" in url or any(t in low for t in (
        "unusual traffic", "로봇이 아닙니다", "보안 확인", "verify you are human")):
        return "blocked"
    if "consent.google." in url:
        return "consent_required"
    if status and status >= 400:
        return "error"
    if any(t in low for t in ("검색결과가 없습니다", "검색 결과가 없습니다", "검색결과를 찾을 수 없습니다",
                              "did not match any documents", "no results found")):
        return "no_results"
    return "needs_review"


def merge_hits(run, hits, query, host, subdomains):
    indexed = {r["url"]: r for r in run["results"]}
    count = 0
    for hit in hits:
        try:
            url = result_url(hit["href"], query["search_url"])
        except (ValueError, KeyError):
            continue
        if not in_scope(url, host, subdomains):
            continue
        count += 1
        row = indexed.get(url)
        if row is None:
            if len(indexed) >= MAX_URLS:
                run["limit_reached"] = True
                continue
            row = {"url": url, "sources": [], "status": "미검사", "checked_at": "", "findings": []}
            run["results"].append(row)
            indexed[url] = row
        source = {k: query[k] for k in ("engine", "query", "term", "page", "searched_at", "search_url", "evidence")}
        source.update(title=hit.get("title", ""), snippet=hit.get("snippet", ""))
        source.update(link_kind=hit.get('link_kind', 'main'), parent_url=hit.get('parent_url', ''))
        if source not in row["sources"]:
            row["sources"].append(source)
    return count


def collect(host, terms, engines, folder, pages=2, subdomains=False, progress=print,
            should_stop=lambda: False, headless=False, templates=None):
    from playwright.sync_api import sync_playwright
    if not terms or len(terms) > 30 or any(not t.strip() or len(t) > 100 for t in terms):
        raise ValueError("광고단어는 1~30건, 각 100자 이하로 입력하세요.")
    if not engines or any(e not in ENGINES for e in engines) or not 1 <= pages <= 10:
        raise ValueError("검색엔진과 페이지 수(1~10)를 확인하세요.")
    folder = Path(folder)
    (folder / "search_evidence").mkdir(parents=True, exist_ok=True)
    run = {"target": host, "subdomains": subdomains, "started_at": now(), "queries": [], "results": [],
           "stopped": False, "limit_reached": False,
           "notes": []}
    save(run, folder)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=headless)
        try:
            context = browser.new_context(locale="ko-KR", viewport={"width": 1280, "height": 900})
            page = context.new_page()
            for engine in engines:
                blocked = False
                from search_providers import query_plan
                for term, query in query_plan(engine, host, terms, templates):
                    if blocked or should_stop() or run["limit_reached"]:
                        break
                    previous = set()
                    for number in range(1, pages + 1):
                        if should_stop() or run["limit_reached"]:
                            break
                        record = {"engine": engine, "term": term, "query": query, "page": number,
                                  "search_url": search_url(engine, query, number), "searched_at": now(),
                                  "state": "error", "evidence": {}, "error": "", "target_links": 0}
                        run["queries"].append(record)
                        progress(f"{ENGINES[engine]} · {query} · {number}페이지")
                        try:
                            response = page.goto(record["search_url"], wait_until="domcontentloaded", timeout=25000)
                            page.wait_for_timeout(1800)
                            body = page.locator("body").inner_text(timeout=5000)
                            record["final_url"] = page.url
                            record["http_status"] = response.status if response else None
                            state = search_state(page.url, body, record["http_status"])
                            stem = f"search_evidence/{len(run['queries']):04d}"
                            try:
                                page.screenshot(path=str(folder / (stem + ".png")), full_page=True, timeout=10000)
                                record["evidence"]["screenshot"] = stem + ".png"
                                (folder / (stem + ".html.txt")).write_text(page.content(), encoding="utf-8")
                                record["evidence"]["html"] = stem + ".html.txt"
                            except Exception as exc:
                                record["evidence_error"] = type(exc).__name__
                            if state in ("blocked", "consent_required", "error", "no_results"):
                                record["state"] = state
                                blocked = state != "no_results"
                                break
                            hits = page.evaluate(EXTRACT_JS)
                            count = merge_hits(run, hits, record, host, subdomains)
                            current = {r["url"] for r in run["results"]}
                            record["target_links"] = count
                            record["state"] = "collected" if count else "needs_review"
                            if not count or current == previous:
                                break
                            previous = current
                        except Exception as exc:
                            record["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:250]}"
                            break
                        finally:
                            save(run, folder)
                        # 중지 요청을 최대 0.1초 간격으로 확인하면서 질의 사이 간격을 둔다.
                        for _ in range(20):
                            if should_stop():
                                break
                            time.sleep(.1)
        finally:
            browser.close()
    run["stopped"] = should_stop()
    run["finished_at"] = now()
    save(run, folder)
    return run


def inspect_current(row, session, folder, number, exclusions=None):
    from findings import EvidenceMap, classify, walk_frame
    from normalize import normalize
    from search_reflect import page_info
    url = row["url"]
    for key in ("http_status", "final_url", "current_title", "ad_parameters", "current_screenshot", "evidence_error"):
        row.pop(key, None)
    row.update(checked_at=now(), findings=[], status="확인 불가", detail="")
    if is_state_change_url(url):
        row["detail"] = "상태 변경 동작으로 보이는 URL은 조회하지 않았습니다."
        return
    status = exclusions.open(session, url) if exclusions else session.open(url)
    row.update(http_status=status, final_url=session.page.url)
    if status in (404, 410):
        row.update(status="삭제 응답", detail=f"현재 HTTP {status}. 검색 당시 노출 근거와 함께 검토하세요.")
        return
    if status is None or status < 200 or status >= 300:
        row["detail"] = f"HTTP {status}. 삭제로 판단하지 않습니다."
        return
    session.expand()
    page = session.page
    info = page_info(page.content(), {}, page.url)
    row["current_title"] = info["title"]
    params = []
    terms = {s["term"] for s in row.get("sources", [])}
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if value and (classify(value)["is_ad"] or any(normalize(t) in normalize(value) for t in terms if normalize(t))):
            params.append({"name": key, "value": value,
                           "reflected": normalize(value) in normalize(info["title"] + " " + info["text"])})
    row["ad_parameters"] = params
    evidence_dir = Path(folder) / "page_evidence" / f"{number:04d}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        walk_frame(page.main_frame, "", url, row["findings"], set(), str(evidence_dir), EvidenceMap())
    except Exception as exc:
        row["detail"] = f"부분 검사: {type(exc).__name__}: {str(exc)[:200]}"
        return
    if any(p["reflected"] for p in params):
        row["status"] = "파라미터 반영"
        row["detail"] = "검색 URL의 광고 후보 문구가 현재 페이지에도 나타납니다. 정상 검색 문맥인지 검토하세요."
    elif row["findings"]:
        row["status"] = "광고 탐지"
    elif any(t in info["text"] for t in ("삭제된 게시물", "삭제된 게시글", "존재하지 않는 게시물", "존재하지 않는 게시글")):
        row["status"] = "삭제 안내 의심"
        row["detail"] = "HTTP 200 페이지의 삭제 안내 문구입니다. 실제 삭제 여부는 담당자가 확인하세요."
    elif params:
        row["status"] = "파라미터 문구만 존재"
    else:
        row["status"] = "현재 광고 미탐지"
        row["detail"] = "정상 문맥·본문 변경·탐지 누락 가능성이 있어 검색 노출 근거와 대조해야 합니다."
    try:
        page.screenshot(path=str(evidence_dir / "current.png"), full_page=True, timeout=10000)
        row["current_screenshot"] = f"page_evidence/{number:04d}/current.png"
        (evidence_dir / "current.html.txt").write_text(page.content(), encoding="utf-8")
    except Exception as exc:
        row["evidence_error"] = type(exc).__name__


def recheck(run, folder, progress=print, should_stop=lambda: False, polite=True, excluded_urls=()):
    from playwright.sync_api import sync_playwright
    from session import BrowserSession
    from politeness import Politeness
    from scan_exclusions import ExcludedNavigation, ScanExclusions
    exclusions = ScanExclusions(excluded_urls)
    host = target_host(run["target"])
    if not isinstance(run.get("results"), list) or len(run["results"]) > MAX_URLS:
        raise ValueError("결과 목록 형식 또는 URL 상한을 확인하세요.")
    manners = Politeness(enabled=polite, respect_robots=True, delay=1)
    with sync_playwright() as pw:
        ses = BrowserSession(pw)
        exclusions.attach(ses.ctx)
        # 주 프레임의 외부 도메인 이동 및 상태 변경 요청은 검사 대상에서 제외한다.
        def guard(route):
            req = route.request
            if req.method not in ("GET", "HEAD", "OPTIONS") or is_state_change_url(req.url):
                route.abort()
            elif req.is_navigation_request() and req.frame == ses.page.main_frame and not in_scope(
                    req.url, host, run.get("subdomains", False)):
                route.abort()
            else:
                route.fallback()
        ses.ctx.route("**/*", guard)
        try:
            for n, row in enumerate(run["results"], 1):
                if should_stop():
                    run["stopped"] = True
                    break
                progress(f"재검사 {n}/{len(run['results'])} · {row['url']}")
                row.update(status="확인 불가", checked_at=now(), findings=[], detail="")
                for key in ("http_status", "final_url", "current_title", "ad_parameters", "current_screenshot", "evidence_error"):
                    row.pop(key, None)
                try:
                    if exclusions.skip(row["url"]):
                        row.update(status="점검 제외", checked_at=None, detail="담당자가 오탐 확인 후 제외한 주소")
                    elif not in_scope(row["url"], host, run.get("subdomains", False)):
                        row.update(status="확인 불가", detail="타깃 도메인 밖의 URL")
                    elif not manners.allowed(row["url"]):
                        row.update(status="확인 불가", detail="robots.txt에 의해 조회하지 않음")
                    else:
                        manners.wait()
                        inspect_current(row, ses, folder, n, exclusions=exclusions)
                except ExcludedNavigation:
                    row.update(status="점검 제외", checked_at=None, findings=[],
                               detail="이동 대상이 담당자의 제외 주소입니다.")
                except Exception as exc:
                    row.update(status="확인 불가", detail=f"{type(exc).__name__}: {str(exc).splitlines()[0][:250]}")
                save(run, folder)
        finally:
            ses.close()
    run["rechecked_at"] = now()
    save(run, folder)
    return run


def new_folder(root, host):
    folder = Path(root) / f"{host}_{datetime.now(KST):%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
    folder.mkdir(parents=True)
    return folder


def save(run, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(str(folder / "results.json"), run, indent=2)
    from search_submission import export
    export(run, folder)
    (folder / "urls.txt").write_text("".join(r["url"] + "\n" for r in run["results"]), encoding="utf-8")
    with (folder / "review.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["원본URL", "현재상태", "HTTP", "최종URL", "검사시각", "설명", "탐지근거", "검색엔진", "검색어", "검색시각", "검색제목", "검색요약", "검색URL", "검색화면"])
        for r in run["results"]:
            for s in r.get("sources", []) or [{}]:
                writer.writerow([csv_text(v) for v in [r["url"], r["status"], r.get("http_status"), r.get("final_url"),
                    r.get("checked_at"), r.get("detail"), json.dumps(r.get("findings", []), ensure_ascii=False),
                    s.get("engine"), s.get("query"), s.get("searched_at"), s.get("title"), s.get("snippet"),
                    s.get("search_url"), json.dumps(s.get("evidence", {}), ensure_ascii=False)]])
    from search_report import build
    (folder / "report.html").write_text(build(run), encoding="utf-8")
