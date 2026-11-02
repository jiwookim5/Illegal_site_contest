"""진입 URL에서 시작해 하위 페이지를 돌며 은닉 불법광고를 탐지한다.

점검 흐름(대기열·상한·실패 처리·중간 저장)만 여기 두고, 주소 다루기는 urls, 브라우저 세션은 session,
판정과 검출은 findings 에 있다.
"""
import hashlib
import os
import re
import time
from frontier import FairQueue
import resume_state as resume_mod
from collections import deque
from datetime import datetime, timezone, timedelta
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.sync_api import sync_playwright

import attachments as attach_mod
import cloaking as cloaking_mod
import image_text as image_text_mod
import index_check as index_mod
import js_links as js_mod
import link_check as link_mod
import search_reflect as reflect_mod
from politeness import DEFAULT_DELAY, Politeness
from findings import EvidenceMap, classify, walk_frame
from browser import script_frames
from session import BrowserSession, fail_entry, fail_reason
from scan_control import ScanControl, ScanStopped, check_cancelled, detail
from scan_exclusions import ExcludedNavigation, ScanExclusions
from urls import invalid_discovery_candidate
from urls import SKIP_EXT, SiteScope, clean_url, is_state_change_url, low_priority, page_key, trap_pattern

KST = timezone(timedelta(hours=9))

# <a href> 말고도 이미지 맵 <area href>, SVG 안의 <a href|xlink:href> 로만 이어지는 글이 있다.
# SVG 링크의 href 는 문자열이 아니라 SVGAnimatedString 이라 따로 푼다
LINK_JS = ("() => Array.from(document.querySelectorAll('a[href], area[href], a[*|href]')).map(a => {"
           " let h = a.href; if (h && typeof h === 'object') h = h.baseVal;"
           " h = h || a.getAttribute('href') || a.getAttributeNS('http://www.w3.org/1999/xlink', 'href');"
           " try { return new URL(h, document.baseURI).href; } catch (e) { return ''; } })"
           ".filter(h => /^https?:/i.test(h))")
DEFAULT_MAX_PAGES = 5000  # 큰 게시판도 끝까지 보도록. 페이지가 적으면 대기열이 먼저 비고, 많아도 시간 상한이 지킨다
TIME_LIMIT_SEC = 25 * 60  # 평가 상한(30분) 안에 결과 파일을 쓰도록 탐색을 멈추는 시점
BLOCK_STREAK = 8        # 이만큼 잇달아 열리지 않으면 차단·장애로 보고 멈춘다 (계속 두드리면 공격처럼 보인다)
# 서버 오류(5xx)는 세지 않는다. 전자정부 프레임워크 누리집은 값이 빠진 주소에 404 대신 500 을 흔히 돌려주어,
# 스크립트·폼에서 추정한 주소가 몇 개 이어지면 정상 페이지가 많이 남았는데도 점검이 끝나 버린다.
STREAK_REASONS = ("timeout", "network", "blocked", "error")
# 열지 못한 페이지를 다시 열기까지 둘 최소 간격. 다른 대기 주소가 없으면 재시도가 곧바로 와서,
# 잠시 막는 서버(gen.go.kr 은 robots.txt 요청 뒤 약 50초 동안 접속을 막는다)에서 첫 페이지조차 열지 못했다
RETRY_GAP_SEC = 60
SAMPLE_MAX = 200        # 열리지 않은 주소·못 본 주소를 이만큼까지 적어 둔다
# 달력·정렬·검색 조건 주소(urls.low_priority)는 같은 꼴마다 이만큼만 연다. 끝없는 달력은 뒤로 미뤄도
# 남은 페이지 예산을 다 먹어 검출 시간만 늘린다. 앞뒤 1년치 달력은 넉넉히 본다
TRAP_PATTERN_MAX = 30


# 본문 글(숨긴 글 포함) 전체의 지문. 글을 통째로 넘기지 않고 페이지 안에서 해시 두 개와 길이로 줄인다.
CONTENT_SIG = ("(() => { const t = (document.body ? document.body.textContent : '').replace(/\\s+/g, ' ');"
               " let a = 0x811c9dc5, b = 5381; for (let i = 0; i < t.length; i++) { const c = t.charCodeAt(i);"
               " a = Math.imul(a ^ c, 16777619); b = (Math.imul(b, 33) + c) | 0; }"
               " return t.length + ':' + (a >>> 0) + ':' + (b >>> 0); })()")

# 판정을 마친 페이지에서 링크·화면 바꾸기 단추·눌러 볼 요소·본문 지문을 한 번의 왕복으로 모은다 (왕복 한 번이 수 ms 다).
# 화면을 바꿀 단추가 있으면 바꾼 뒤 페이지를 다시 열므로, 눌러 볼 요소는 그때 다시 찾는다(cand 는 null).
PAGE_TAIL = ("([swLimit, candArgs]) => { const links = (" + LINK_JS + ")(); const sw = ("
             + js_mod.SWITCH_CANDIDATES + ")(swLimit); return { links, sw, cand: sw.length ? null : ("
             + js_mod.JS_CANDIDATES + ")(candArgs), sig: " + CONTENT_SIG + " }; }")


# 탭을 바꾸면 앞 탭이 숨겨진다. 처음 화면에서 이미 보이던 글이 숨겨졌다고 광고로 세지 않도록,
# 바꾼 화면에서는 처음 화면에 보이지 않던 글만 검출로 남긴다.
VISIBLE_TEXT = "() => (document.body ? document.body.innerText : '').replace(/\\s+/g, '')"


def _folder(url):
    """주소의 폴더 (호스트 + 마지막 / 앞까지의 경로)."""
    p = urlparse(url)
    return p.netloc.lower(), p.path.rsplit("/", 1)[0]


# 폴더 이름이 회원 영역일 때만 같은 폴더를 미룬다. '/www/' 처럼 누리집 전체가 든 폴더는 미루지 않는다
_MEMBER_DIR = {"member", "members", "mem", "mypage", "my", "myinfo", "user", "users", "usr", "account",
               "login", "auth", "uat", "uia", "회원"}


def _member_folder(url):
    return bool(set(re.split(r"[^\w]+|_", _folder(url)[1].lower())) & _MEMBER_DIR)


def frame_links(page, frames=None):
    """페이지와 그 안 모든 프레임(frames 를 주면 그 프레임들)의 <a href> 주소.
    frameset·iframe 누리집은 메뉴·게시판 링크가 프레임 안에 있다."""
    hrefs = []
    for fr in script_frames(page.frames if frames is None else frames):
        try:
            hrefs += fr.evaluate(LINK_JS)
        except Exception:
            pass
    return hrefs


def switch_views_and_walk(ses, url, results, iframe_urls, evidence_dir, evid_map, hrefs, ids=None, primary_only=False):
    """같은 주소에서 바뀌는 화면을 하나씩 훑는다. 화면을 바꿨으면 True."""
    page = ses.page
    shown = []                 # 바꾸기 전 화면 글 (누를 단추가 있을 때만 읽는다)

    def remember():
        shown.append(page.evaluate(VISIBLE_TEXT))

    switched = False
    try:
        for _ in ses.switch_views(before=remember, ids=ids):
            switched = True
            rows = []
            try:
                walk_frame(page.main_frame, "", url, rows, iframe_urls, evidence_dir, evid_map, primary_only=primary_only)
            except Exception:
                pass
            results.extend(r for r in rows
                           if re.sub(r"\s+", "", r.get("evidence_text") or "") not in shown[0])
            hrefs += frame_links(page)
    except Exception:
        pass
    return switched


SHARED_MIN = 3   # 화면의 SHARED_MIN 과 같다. 이만큼 여러 페이지에 같은 글이 있으면 공통 서식 하나로 센다


def count_entries(rows):
    """화면의 결과 목록과 같은 단위(광고 하나 = 한 줄)로 센다. 점검 중 진행 화면의 '찾은 의심 항목'에 쓴다."""
    uniq = {(page_key(r["url"]), r["location"], r["technique"]): r for r in rows}.values()
    groups = {}
    for r in uniq:
        groups.setdefault((r["technique"], r["location"], r.get("evidence_text")), set()).add(r["url"])
    shared = {k for k, urls in groups.items() if len(urls) >= SHARED_MIN}
    rest = {(r["url"], r["location"]) for r in uniq if (r["technique"], r["location"], r.get("evidence_text")) not in shared}
    return len(shared) + len(rest)


def scan(entry_url, max_pages=DEFAULT_MAX_PAGES, timeout_ms=20000, progress=None, evidence_dir=None,
         snapshot_dir=None, polite=False, delay=None, respect_robots=True,
         settle_ms=60, cloaking=False, cloaking_limit=40, attachments=False,
         search_reflect=False, index_urls=None, subdomains=False, check_links=False, ocr_images=False,
         time_limit=TIME_LIMIT_SEC, should_stop=None, checkpoint=None, status=None, primary_only=False, resume_state=None,
         stalled_url=None, excluded_urls=()):
    """누리집을 돌며 탐지한다.

    time_limit  이 시간(초)이 지나면 새 페이지를 열지 않고 지금까지의 결과로 마친다
    should_stop 참을 돌려주면 멈춘다 (화면의 '탐지 중지')
    checkpoint  페이지를 열 때마다 그 앞까지의 중간 결과를 받아 파일로 남긴다
                (도중에 프로그램이 죽어도 그때까지의 result.json 이 남는다)
    stalled_url 재개할 때, 응답이 없어 앞 작업을 끝내게 만든 페이지. 다시 열지 않고 실패로 남긴다
    """
    started = datetime.now(KST)
    t0 = time.perf_counter()
    scope = SiteScope(entry_url, subdomains)
    exclusions = ScanExclusions(excluded_urls)
    excluded_pages = set()
    exclusion_hits = None

    seen, queue, low_queue, results, visited_pages = set(), FairQueue([entry_url]), deque(), [], []
    queued = {page_key(entry_url)}   # 대기열에 이미 넣은 주소. 공통 메뉴 링크를 페이지마다 다시 넣지 않는다
    # 같은 경로에서 본문이 똑같은 페이지. 방문할 때마다 값이 바뀌는 링크(?sid=무작위)가 걸린 페이지는
    # 주소만 다른 같은 화면을 끝없이 만들어 페이지 예산을 다 먹으므로, 두 번째부터는 링크를 따라가지 않는다
    contents = set()
    trap_counts, trap_skipped = {}, 0    # 함정 주소 꼴마다 대기열에 넣은 수, 상한에 걸려 넣지 않은 수
    # 회원 메뉴(마이페이지 등)처럼 열면 로그인·로그아웃 화면으로 넘겨지는 주소. 그 화면은 분석하지 않고,
    # 같은 폴더의 다른 주소는 다른 페이지를 다 본 뒤로 미룬다 (대부분 같은 로그인 화면으로 넘어간다)
    login_redirects, login_dirs = [], set()
    # 열지 못한 페이지는 조용히 버리지 않고 사유와 함께 남긴다. '0건'이 '깨끗함'인지 '못 봄'인지 가려야 한다.
    # 잠깐의 장애(시간 초과·접속 오류·서버 오류)는 간격을 두고 한 번만 다시 연다.
    failed, gone, retry_queue, retried, retrying = [], [], deque(), set(), set()
    # 다시 열 주소 -> (열어도 되는 시각, 첫 실패 기록). 시각은 중간 저장에 넣지 않고 첫 실패 기록만 넣는다
    retry_after = {}
    # 페이지는 열었지만 글을 읽지 못한 하위 iframe. 표본(페이지 주소, iframe 위치)과 페이지 수
    frame_failed, frame_failed_pages = [], set()
    streak = 0
    iframe_urls = set()
    evid_map = EvidenceMap() if evidence_dir else None
    snapshots = {}
    cloaking_checked = 0
    stopped = None
    attach = prober = indexer = linkcheck = imgtext = None
    engine = "?"
    analyzed = 0
    invalid_candidates = 0
    rejected_candidates = []
    current_url = None
    completed_keys = set()
    deferred_pages = set()
    index_done = set()
    auxiliary = {}
    session_probed = set()
    page_baseline = None
    scan_settings = dict(timeout_ms=timeout_ms, polite=polite, delay=delay, respect_robots=respect_robots,
                         settle_ms=settle_ms, cloaking=cloaking, cloaking_limit=cloaking_limit,
                         attachments=attachments, search_reflect=search_reflect, index_urls=index_urls,
                         subdomains=subdomains, check_links=check_links, ocr_images=ocr_images,
                         primary_only=primary_only, excluded_urls=list(exclusions.rules.values()))
    resume_engine, resume_rules = resume_mod.engine_id(), resume_mod.rules_id()
    if resume_state:
        saved = resume_mod.validate(resume_state, entry_url)
        if saved.get('settings') != scan_settings:
            raise ValueError("이전 점검과 설정이 다릅니다. 같은 설정으로 재개하십시오.")
        if resume_state.get("rules") != resume_rules:
            raise ValueError("저장된 판정 규칙과 재개 규칙이 다릅니다.")
        seen = saved['seen']; queued = saved['queued']
        queue.content = deque(saved['queue_content']); queue.normal = deque(saved['queue_normal'])
        queue.streak = saved['queue_streak']
        low_queue = deque(saved['low_queue']); retry_queue = deque(saved['retry_queue'])
        results = saved['results']; visited_pages = saved['visited_pages']
        completed_keys = saved['completed_keys']; analyzed = saved['analyzed']
        contents = saved['contents']; trap_counts = saved['trap_counts']; trap_skipped = saved['trap_skipped']
        login_redirects = saved['login_redirects']; login_dirs = saved['login_dirs']
        failed = saved['failed']; gone = saved['gone']; retried = saved['retried']; retrying = saved['retrying']
        iframe_urls = saved['iframe_urls']; snapshots = saved['snapshots']
        excluded_pages = set(saved.get('excluded_pages', []))
        exclusions.skipped.update(saved.get('excluded', {}))
        frame_failed = saved.get('frame_failed', []); frame_failed_pages = saved.get('frame_failed_pages', set())
        # 다시 열기를 기다리던 주소의 첫 실패 사유. 재개까지 이미 시간이 지났으므로 바로 열어도 된다
        retry_after.update({u: (0, entry) for u, entry in saved.get('retry_first', {}).items() if u in retry_queue})
        if evid_map is not None:
            evid_map.update(saved['evidence'])
            evid_map.by_content.update(saved.get('evidence_content', {}))
        cloaking_checked = saved['cloaking_checked']; invalid_candidates = saved['invalid_candidates']
        rejected_candidates = saved['rejected_candidates']; index_done = saved['index_done']
        scope.hosts = saved['scope_hosts']; scope.bases = saved['scope_bases']
        auxiliary = saved['auxiliary']; session_probed = saved['session_probed']
        # Reopen interrupted/deferred pages, but never forget completed page identities.
        if stalled_url and saved['current_url'] == stalled_url:
            # scan_worker 가 정체로 끝낸 페이지. 다시 열면 또 멈추므로 실패로 적고 다음 주소로 간다
            failed.append(fail_entry(stalled_url, "stalled", None, "응답이 멈춰 이 페이지를 건너뛰고 이어서 점검함"))
            saved['current_url'] = None
        for unfinished in ([saved['current_url']] if saved['current_url'] else []) + sorted(saved['deferred_pages']):
            k = page_key(unfinished)
            seen.discard(k)
            visited_pages = [u for u in visited_pages if page_key(u) != k]
            if k in completed_keys:
                completed_keys.discard(k); analyzed = max(0, analyzed - 1)
            if unfinished not in list(queue) + list(low_queue) + list(retry_queue): queue.append(unfinished)
        # Each continuation gets a fresh page budget; repetition/retry limits stay cumulative.
    # Excluded work is completed by policy, not left as an endlessly resumable task.
    queue.content = deque(u for u in queue.content if not exclusions.skip(u))
    queue.normal = deque(u for u in queue.normal if not exclusions.skip(u))
    low_queue = deque(u for u in low_queue if not exclusions.skip(u))
    retry_queue = deque(u for u in retry_queue if not exclusions.skip(u))
    deferred_pages = {u for u in deferred_pages if not exclusions.skip(u)}
    index_done.update(u for u in (index_urls or []) if exclusions.skip(u))
    page_budget_start = len(visited_pages)
    status_callback = status
    found_cache = [None, 0]   # (결과 수, iframe 수) 가 같으면 다시 세지 않는다. 페이지마다 여러 번 알리므로
    def found_count():
        mark = (len(results), len(iframe_urls))
        if found_cache[0] != mark:
            found_cache[:] = [mark, count_entries([r for r in results if page_key(r["url"]) not in iframe_urls])]
        return found_cache[1]
    def notify(stage, url):
        if status_callback:
            status_callback(stage, url, pages_done=analyzed, visited=len(visited_pages),
                   failed_count=len(failed), pending=len(queue) + len(low_queue) + len(retry_queue),
                   found=found_count())
    control = ScanControl(should_stop, time_limit, notify)
    manners = Politeness(enabled=polite, respect_robots=respect_robots,
                         delay=DEFAULT_DELAY if delay is None else delay, exclusions=exclusions)

    def state_snapshot():
        state = dict(settings=scan_settings, seen=seen, queued=queued, queue_content=list(queue.content), queue_normal=list(queue.normal),
                     queue_streak=queue.streak, low_queue=list(low_queue), retry_queue=list(retry_queue),
                     results=results, visited_pages=visited_pages, completed_keys=completed_keys, analyzed=analyzed,
                     contents=contents, trap_counts=trap_counts, trap_skipped=trap_skipped,
                     login_redirects=login_redirects, login_dirs=login_dirs, failed=failed, gone=gone,
                     retried=retried, retrying=retrying, iframe_urls=iframe_urls, snapshots=snapshots,
                     frame_failed=frame_failed, frame_failed_pages=frame_failed_pages, retry_first={u: entry for u, (_, entry) in retry_after.items()},
                     evidence=dict(evid_map or {}), evidence_content=evid_map.by_content if evid_map is not None else {},
                     cloaking_checked=cloaking_checked,
                     invalid_candidates=invalid_candidates, rejected_candidates=rejected_candidates,
                     current_url=current_url, scope_hosts=scope.hosts, scope_bases=scope.bases,
                     excluded_pages=sorted(excluded_pages), excluded=dict(exclusions.skipped),
                     index_done=indexer.completed if indexer else index_done,
                     deferred_pages=deferred_pages, session_probed=session_probed,
                     auxiliary={
                         'attach': resume_mod.capture(attach, ['cache', 'unread']),
                         'image': resume_mod.capture(imgtext, ['cache']),
                         'reflect': resume_mod.capture(prober, ['seen', 'marker']),
                         'links': resume_mod.capture(linkcheck, ['links', 'completed', 'saved_rows', 'missing', 'reached']),
                         'index': resume_mod.capture(indexer, ['inspected', 'completed', 'later', 'saved_rows', 'checked']),
                     } if attach or imgtext or prober or linkcheck else auxiliary)
        pending_extra = (len(set(index_urls or []) - (indexer.completed if indexer else index_done))
                         + (len(set(linkcheck.links) - linkcheck.completed) if linkcheck else
                            len(set(auxiliary.get('links', {}).get('links', {})) - auxiliary.get('links', {}).get('completed', set()))))
        if linkcheck and linkcheck.reached and linkcheck.missing:
            pending_extra += 1  # Pending domain-warning publication is also resumable.
        if current_url and page_baseline:
            state['session_probed'] = page_baseline['session_probed']
            state['cloaking_checked'] = page_baseline['cloaking_checked']
            if prober: state['auxiliary']['reflect']['seen'] = page_baseline['reflect_seen']
        pending = len(queue) + len(low_queue) + len(retry_queue) + len(deferred_pages) + bool(current_url) + pending_extra
        return dict(version=resume_mod.VERSION, engine=resume_engine, rules=resume_rules, entry=entry_url,
                    pending=int(pending), pending_extra=pending_extra, data=resume_mod.pack(state))

    def save_checkpoint():
        if checkpoint:
            checkpoint(assemble())

    def assemble():
        # iframe 안에서 이미 본 내용을 독립 페이지로 다시 세지 않는다
        link_rows = linkcheck.saved_rows if linkcheck else auxiliary.get('links', {}).get('saved_rows', [])
        index_rows = indexer.saved_rows if indexer else auxiliary.get('index', {}).get('saved_rows', [])
        rows = [r for r in results + link_rows + index_rows if page_key(r["url"]) not in iframe_urls]
        # 요강: 쿼리 값이 다르면 내용이 같아도 별도 페이지로 제출한다.
        # (url + location + technique) 중복 제거
        uniq, seen_keys = [], {}
        for r in rows:
            k = (page_key(r["url"]), r["location"], r["technique"])
            if k in seen_keys:
                old = uniq[seen_keys[k]]
                if ((old.get("judgement") or {}).get("decision") == "review" and (
                        r.get("judgement") or {}).get("decision") != "review"):
                    uniq[seen_keys[k]] = r
                continue
            seen_keys[k] = len(uniq)
            uniq.append(r)
        return {
            "engine": engine,
            "politeness": manners.summary(),
            "evidence": dict(evid_map or {}),
            "attachments_fetched": attach.fetched if attach else 0,
            "attachments_unread": (attach.unread if attach else auxiliary.get('attach', {}).get('unread', []))[:SAMPLE_MAX],
            "search_probes": prober.probed if prober else 0,
            "index_checked": indexer.checked if indexer else 0,
            "index_other_site": indexer.skipped_other_site if indexer else 0,
            "links_checked": linkcheck.checked if linkcheck else 0,
            "ocr_images": ({"read": imgtext.read, "unavailable": imgtext.unavailable} if imgtext else None),
            "snapshots": dict(snapshots),
            "started": started,
            "finished": datetime.now(KST),
            "elapsed": time.perf_counter() - t0,
            "pages": list(visited_pages),
            "findings": uniq,
            "stopped": stopped,
            "coverage": coverage(),
            "timings": {k: dict(v) for k, v in control.timings.items()},
            "detail_timings": {k: dict(v) for k, v in control.details.items()},
            "counts": dict(control.counts),
            "primary_only": primary_only,
            "resume_state": state_snapshot(),
        }

    def coverage():
        """점검 범위. 몇 페이지를 봤고 무엇을 왜 못 봤는가."""
        # 대기열에 남은 주소 (페이지 수·시간 상한, 중지, 차단으로 열지 못한 곳)
        if current_url and exclusion_hits is not None and exclusions.hits != exclusion_hits:
            excluded_pages.add(current_url)
        left, left_keys = [], set()
        for u in (*queue, *low_queue, *retry_queue, *deferred_pages):
            if exclusions.skip(u):
                continue
            k = page_key(u)
            if (k in seen and k not in retrying and u not in deferred_pages) or k in left_keys:
                continue
            left_keys.add(k)
            left.append(u)
        return {
            "visited": len(visited_pages),
            "analyzed": analyzed,
            "in_progress": current_url if stopped else None,
            "failed": failed[:SAMPLE_MAX], "failed_count": len(failed),
            # 다시 열기를 기다리다 점검이 끝난 주소의 첫 실패. '열지 않은 주소'에도 들어 있다
            "retry_waiting": [entry for _, entry in retry_after.values()][:SAMPLE_MAX],
            "retry_waiting_count": len(retry_after),
            # 페이지는 열었지만 글을 읽지 못한 하위 iframe. 그 안의 광고는 '0건'이 아니라 '못 봄'이다
            "frame_failed": frame_failed[:SAMPLE_MAX], "frame_failed_pages": len(frame_failed_pages),
            "failed_kinds": {r: sum(1 for f in failed if f["reason"] == r)
                             for r in dict.fromkeys(f["reason"] for f in failed)},
            "gone": gone[:SAMPLE_MAX], "gone_count": len(gone),
            "left": left[:SAMPLE_MAX], "left_count": len(left),
            "trap_skipped": trap_skipped,
            "login_redirects": login_redirects[:SAMPLE_MAX], "login_redirect_count": len(login_redirects),
            "invalid_candidates": invalid_candidates,
            "rejected_candidates": list(rejected_candidates),
            "max_pages": max_pages,
            "robots": manners.summary().get("skipped_by_robots", 0),
            "excluded": list(exclusions.skipped.values()), "excluded_count": len(exclusions.skipped),
            "excluded_pages": sorted(excluded_pages), "excluded_page_count": len(excluded_pages),
            "exclusion_rule_count": exclusions.rules_within(scope.allows),
        }

    def give_up(url, key, reason, retry, status=None, detail=""):
        """열지 못한 페이지. 다시 열어 볼 만하면 한 번만 미루고, 아니면 실패로 남긴다."""
        nonlocal streak, current_url
        current_url = None
        if retry and key not in retried:
            retrying.add(key)            # 다시 열 때 이미 본 주소로 걸러지지 않게 표시한다
        if reason == "gone":
            gone.append(fail_entry(url, reason, status))
            return
        if reason in STREAK_REASONS:
            streak += 1
        if retry and key not in retried:
            retried.add(key)
            retry_queue.append(url)
            retry_after[url] = (time.monotonic() + RETRY_GAP_SEC, fail_entry(url, reason, status, detail))
            return
        failed.append(fail_entry(url, reason, status, detail))

    def out_of_time():
        return bool(time_limit) and time.perf_counter() - t0 > time_limit

    with control.activate():
        if checkpoint:
            checkpoint(assemble())
        try:
            with sync_playwright() as p:
                ses = BrowserSession(p, timeout_ms, settle_ms)
                engine, ctx, guard = ses.engine, ses.ctx, ses.guard
                exclusions.attach(ctx)
                request = exclusions.request(ctx.request)
                # 첨부파일은 페이지 이동 없이 같은 쿠키·UA 로 직접 받는다.
                attach = (attach_mod.AttachmentScanner(request, manners, classify, deadline=out_of_time)
                          if attachments else None)
                # 검색 폼마다 무해한 표식으로 한 번 조회해 검색어 반사 여부를 본다.
                # 색인 목록 점검도 같은 조회기를 써서, 이미 본 검색 경로를 다시 조회하지 않는다.
                prober = (reflect_mod.SearchReflectScanner(request, manners)
                          if search_reflect or index_urls else None)
                reflect = prober if search_reflect else None
                indexer = index_mod.IndexChecker(prober, classify) if index_urls else None
                # 누리집이 걸어 둔 바깥 링크를 모았다가 탐색이 끝난 뒤 목적지를 한 번씩 확인한다
                linkcheck = (link_mod.LinkChecker(request, manners, classify, scope.allows)
                             if check_links else None)
                # 본문 그림 속 글자를 글자 인식으로 읽는다 (선택 기능)
                imgtext = (image_text_mod.ImageTextScanner(request, manners, classify, deadline=out_of_time)
                           if ocr_images else None)

                resume_mod.restore(attach, auxiliary.get('attach', {}))
                resume_mod.restore(imgtext, auxiliary.get('image', {}))
                resume_mod.restore(prober, auxiliary.get('reflect', {}))
                resume_mod.restore(linkcheck, auxiliary.get('links', {}))
                resume_mod.restore(indexer, auxiliary.get('index', {}))
                if indexer: indexer.completed.update(index_done)
                ses.probed.update(session_probed)
                session_probed = ses.probed
                for task in (attach, imgtext):
                    if task: task.on_checkpoint = save_checkpoint
                if linkcheck: linkcheck.on_checkpoint = save_checkpoint
                if indexer: indexer.on_checkpoint = save_checkpoint

                while (queue or low_queue or retry_queue) and len(visited_pages) - page_budget_start < max_pages:
                    if should_stop and should_stop():
                        stopped = "user"
                        break
                    if out_of_time():
                        stopped = "time"
                        break
                    if streak >= BLOCK_STREAK:
                        stopped = "blocked"
                        break
                    # 다시 열 때가 된 주소는 대기열보다 먼저 연다. 큰 누리집은 대기열이 비지 않아,
                    # 맨 뒤에 두면 시간 상한까지 다시 열지 못한다 (2026-10-20 광주교육청 61쪽)
                    if retry_queue and retry_after.get(retry_queue[0], (0,))[0] <= time.monotonic():
                        url = retry_queue.popleft()
                    else:
                        url = queue.popleft() if queue else low_queue.popleft() if low_queue else retry_queue.popleft()
                    if exclusions.skip(url):
                        continue
                    exclusion_hits = exclusions.hits
                    due, first_failure = retry_after.pop(url, (0, None))
                    if first_failure and time_limit and due - time.monotonic() > time_limit - (time.perf_counter() - t0):
                        # 다시 열 때가 되기 전에 점검 시간이 끝난다. 기다리다 주소를 잃지 않게 첫 실패로 남긴다
                        failed.append(first_failure)
                        continue
                    while time.monotonic() < due and not out_of_time():
                        check_cancelled()
                        time.sleep(0.5)
                    key = page_key(url)
                    if key in seen and key not in retrying:
                        continue
                    if key in retried:
                        retrying.discard(key)       # 다시 여는 것은 한 번뿐
                    seen.add(key)
                    current_url = control.url = url
                    page_baseline = dict(session_probed=set(ses.probed), reflect_seen=set(prober.seen) if prober else set(),
                                         cloaking_checked=cloaking_checked)
                    # 저장은 페이지를 열기 전 여기서 한 번만 한다. 저장마다 결과와 대기열 전체를 다시 쓰므로
                    # (gb.go.kr 1278쪽에서 5MB, 한 번 0.15초) 페이지를 마칠 때도 쓰면 점검 시간의 1할이 저장에 든다.
                    # 앞 페이지의 결과·실패 기록이 여기서 모두 남으므로, 이 페이지에서 멈춰 강제 종료돼도 잃지 않는다
                    with detail("checkpoint.open"):
                        save_checkpoint()
                    check_cancelled()
                    notify("opening", url)
                    if not manners.allowed(url):
                        current_url = None
                        continue
                    with control.phase("opening"):
                        manners.wait()
                        try:
                            # 없는 주소(404)나 오류 응답은 점검할 페이지가 아니다.
                            # POST 폼을 GET 주소로 바꿔 본 후보가 GET 을 받지 않는 경우도 여기서 걸러진다.
                            # 페이지가 미뤄 둔 삽입(타이머)은 여기서 기다리지 않고, 펼치기·판정과 함께 기다린다
                            status = exclusions.open(ses, url, defer_timers=True)
                        except ExcludedNavigation:
                            current_url = None
                            continue
                        except Exception as exc:
                            reason, retry = fail_reason(exc=exc)
                            # https 로 적은 같은 누리집 링크가 열리지 않으면(인증서·https 를 받지 않는 서버) http 로 한 번 연다.
                            # 요강 채점도 http·https 를 가리지 않는다
                            status = None
                            alt = "http://" + url[len("https://"):] if url.startswith("https://") else None
                            if alt and reason in ("network", "error") and scope.allows(alt):
                                try:
                                    status, url = exclusions.open(ses, alt, defer_timers=True), alt
                                except ExcludedNavigation:
                                    current_url = None
                                    continue
                                except Exception:
                                    status = None
                            if status is None:
                                give_up(url, key, reason, retry, detail=f"{type(exc).__name__}: {exc}".splitlines()[0])
                                continue
                        if status >= 400:
                            reason, retry = fail_reason(status=status)
                            give_up(url, key, reason, retry, status=status)
                            continue
                    # 페이지 하나에서 난 예외(브라우저가 결과를 못 돌려줌 등)가 점검 전체를 멈추지 않게 한다.
                    # 그 페이지만 실패로 남기고 다음 페이지로 넘어간다. 이미 찾은 검출은 남긴다.
                    # 사용자 중단·시간 종료(ScanStopped)는 BaseException 이라 여기서 잡히지 않는다.
                    try:
                        streak = 0
                        page = ses.page
                        if exclusions.skip(page.url):
                            current_url = None
                            continue

                        if not visited_pages and page.url:
                            scope.add(page.url)      # 진입 주소가 넘겨진 곳(리다이렉트)도 같은 누리집이다
                        # 넘겨진(리다이렉트) 주소가 실제 페이지다. 옛 주소·짧은 주소로 같은 글을 다시 보고하지 않고,
                        # 보고하는 url 도 실제로 열린 주소로 적는다.
                        if (page.url or "").startswith(("http://", "https://")):
                            final = clean_url(urldefrag(page.url)[0])
                            fkey = page_key(final)
                            if fkey != key and visited_pages and is_state_change_url(final) and not is_state_change_url(url):
                                login_redirects.append({"url": url, "to": final})
                                if _member_folder(url):
                                    login_dirs.add(_folder(url))
                                seen.add(fkey)
                                current_url = None
                                continue
                            if fkey != key:
                                if fkey in seen or not scope.allows(final):
                                    current_url = None
                                    continue
                                seen.add(fkey)
                                url = final
                        elif page.url != "about:blank":
                            current_url = None
                            continue        # 바깥으로 넘어가다 오류 화면(chrome-error://)이 됐다. 이 누리집의 페이지가 아니다

                        current_url = control.url = url
                        with control.phase("expand"):
                            ses.expand()

                        visited_pages.append(url)
                        failures_before = len(failed)

                        # 1~2) 메인 프레임과 그 하위 iframe 전체를 재귀로 훑는다
                        before = len(results)
                        def analyze():
                            try:
                                frames_unread = []
                                walk_frame(page.main_frame, "", url, results, iframe_urls,
                                           evidence_dir, evid_map, attach, reflect, linkcheck, primary_only=primary_only,
                                           frame_failures=frames_unread)
                                # 늦게 뜨는 글을 보려고 다시 훑어도 한 번만 센다. 위젯 iframe 이 페이지마다 막히는
                                # 누리집에서 저장이 커지지 않게 표본만 남긴다
                                for f in dict.fromkeys(frames_unread):
                                    entry = {"url": url, "frame": f.rstrip(" >")}
                                    if len(frame_failed) < SAMPLE_MAX and entry not in frame_failed:
                                        frame_failed.append(entry)
                                if frames_unread:
                                    frame_failed_pages.add(page_key(url))
                            except Exception as exc:
                                # 열리기는 했지만 끝까지 훑지 못했다. 이 페이지에서 찾은 것만 남는다
                                failed.append(fail_entry(url, "partial", None,
                                                         f"{type(exc).__name__}: {exc}".splitlines()[0]))

                        skip = False
                        with control.phase("analyze"):
                            ses.watch_late()
                            analyze()
                            # 열 때 미룬 타이머를 마저 기다린다. 판정한 뒤에 화면이 바뀌었으면 바뀐 화면으로 다시 판정한다
                            late = ses.finish_timers()
                            if late == "navigated":
                                # 타이머가 다른 주소로 넘겼다. 예전처럼 넘어간 주소의 페이지로 본다
                                del results[before:]
                                del failed[failures_before:]
                                final = clean_url(urldefrag(page.url or "")[0])
                                fkey = page_key(final)
                                if (not final.startswith(("http://", "https://")) or not scope.allows(final)
                                        or (fkey != key and fkey in seen) or is_state_change_url(final)
                                        or exclusions.skip(final)):
                                    skip = True
                                else:
                                    seen.add(fkey)
                                    url = current_url = control.url = visited_pages[-1] = final
                                    with detail("analyze.again"):
                                        analyze()
                            elif late == "changed":
                                del results[before:]
                                del failed[failures_before:]
                                with detail("analyze.again"):
                                    analyze()
                        if skip:
                            visited_pages.pop()
                            current_url = None
                            continue
                        # meta refresh·location.href 로 훑는 사이에 바깥 주소로 넘어갔으면, 넘어간 뒤 화면
                        # (바깥 누리집이나 브라우저 오류 화면에 찍힌 도메인 이름)을 이 주소의 광고로 보고하지 않는다
                        now = page.url or ""
                        if exclusions.skip(now):
                            del results[before:]
                            visited_pages.pop()
                            current_url = None
                            continue
                        if not (now.startswith(("http://", "https://")) and scope.allows(now)):
                            del results[before:]
                            current_url = None
                            continue

                        with control.phase("extras"):
                            # 자바스크립트로 내려받는 첨부(fn_egov_downFile 등)는 <a href> 가 아니라 위에서 못 본다. 눌러 주소를 알아낸다
                            if attach is not None:
                                try:
                                    files = [f for f in js_mod.download_links(page, guard)
                                             if attach_mod.looks_like_attachment(f["href"], f["text"])]
                                    results.extend(attach.check(url, files))
                                except Exception:
                                    pass

                            if imgtext is not None:
                                try:
                                    results.extend(imgtext.check(page.main_frame, url))
                                except Exception:
                                    pass

                            # 페이지를 탐지한 시점 그대로 보관한다.
                            # 나중에 화면에서 '그때 그 페이지'를 열어 검출 위치를 짚어주기 위함이다.
                            if snapshot_dir is not None:
                                try:
                                    name = hashlib.sha1(page_key(url).encode("utf-8")).hexdigest()[:16] + ".html"
                                    os.makedirs(snapshot_dir, exist_ok=True)
                                    with open(os.path.join(snapshot_dir, name), "w",
                                              encoding="utf-8", errors="replace") as fp:
                                        fp.write(page.content())
                                    snapshots[page_key(url)] = name
                                except Exception:
                                    pass

                            # 크롤러 신원으로 한 번 더 조회해 응답이 달라지는지 본다.
                            # 요청이 늘어나므로 켰을 때만, 정해진 페이지 수까지만 수행한다.
                            if cloaking and cloaking_checked < cloaking_limit:
                                cloaking_checked += 1
                                try:
                                    results.extend(cloaking_mod.check(request, url))
                                except Exception:
                                    pass

                        with control.phase("discover"):
                            # 3) 링크 수집
                            try:
                                tail = page.evaluate(PAGE_TAIL, [js_mod.SWITCH_LIMIT, [js_mod.PROBE_LIMIT, list(ses.probed)]])
                                hrefs = tail["links"] + frame_links(page, page.frames[1:])
                            except Exception:
                                tail = {"sw": None, "cand": None, "sig": None}
                                hrefs = frame_links(page)
                            ckey = None
                            if tail.get("sig"):
                                # iframe 만 다르고 본문 글이 없는 틀 페이지(frameset 등)를 같은 화면으로 보지 않도록 프레임 주소도 넣는다
                                p = urlparse(url)
                                frames = tuple(sorted(page_key(f.url) for f in page.frames[1:]
                                                      if (f.url or "").startswith(("http://", "https://"))))
                                ckey = (p.netloc.lower(), p.path.rstrip("/") or "/", tail["sig"], frames)
                                if ckey in contents:
                                    tail, hrefs = {"sw": [], "cand": {}}, []    # 앞의 같은 화면에서 이미 모았다
                            # 탭·'다음 페이지'로 같은 주소에서 바뀌는 화면도 훑는다 (같은 검출은 assemble 이 한 건으로 합친다).
                            # 앞 화면의 링크를 모은 뒤에 바꾸고, 바꿨으면 눌러 보기(discover) 전에 페이지를 다시 연다.
                            with detail("discover.switch"):
                                switched = tail["sw"] != [] and switch_views_and_walk(
                                    ses, url, results, iframe_urls, evidence_dir, evid_map, hrefs, tail["sw"], primary_only)
                            if switched:
                                with detail("discover.reopen"):
                                    try:
                                        exclusions.open(ses, url)
                                    except Exception:
                                        pass
                            # 게시판 목록이 javascript:fn_view('1024') 나 onclick 으로만 이어지는 경우
                            with detail("discover.js"):
                                try:
                                    hrefs += js_mod.discover(page, ctx, guard, ses.probed, tail["cand"])
                                except Exception:
                                    pass
                        if exclusions.hits != exclusion_hits:
                            excluded_pages.add(url)
                        for h in hrefs:
                            check_cancelled()
                            h, _ = urldefrag(urljoin(page.url or url, h))
                            h = clean_url(h)
                            if invalid_discovery_candidate(h):
                                invalid_candidates += 1
                                if len(rejected_candidates) < SAMPLE_MAX:
                                    rejected_candidates.append({"source": url, "candidate": h, "reason": "invalid_or_repeated"})
                                continue
                            if is_state_change_url(h):
                                continue
                            if not scope.allows(h):
                                continue
                            if exclusions.skip(h):
                                continue
                            if h.lower().split("?")[0].endswith(SKIP_EXT):
                                continue
                            # 확장자 없는 내려받기 주소(FileDown.do 등)를 페이지로 열지 않는다
                            if attach_mod.DOWNLOAD_HINT.search(h):
                                continue
                            hkey = page_key(h)
                            if hkey not in seen and hkey not in queued:
                                queued.add(hkey)
                                if login_dirs and _folder(h) in login_dirs:
                                    low_queue.append(h)
                                    continue
                                if not low_priority(h):
                                    queue.append(h)
                                    continue
                                pat = trap_pattern(h)
                                if trap_counts.get(pat, 0) >= TRAP_PATTERN_MAX:
                                    trap_skipped += 1
                                    continue
                                trap_counts[pat] = trap_counts.get(pat, 0) + 1
                                low_queue.append(h)

                        if ckey: contents.add(ckey)
                        task_deferred = any(task and task.deferred for task in (attach, imgtext))
                        if task_deferred:
                            deferred_pages.add(url)
                            for task in (attach, imgtext):
                                if task: task.deferred.clear()
                        if len(failed) == failures_before and not task_deferred:
                            if page_key(url) not in completed_keys:
                                analyzed += 1
                                completed_keys.add(page_key(url))
                        current_url = None
                        if progress:
                            progress(analyzed, url)
                        notify("page_complete", url)
                    except Exception as exc:
                        reason, retry = fail_reason(exc=exc)
                        give_up(url, key, reason, retry, detail=f"{type(exc).__name__}: {exc}".splitlines()[0])
                        continue

                # Optional tasks commit their own results before advancing the cursor.
                if index_urls and not stopped and not out_of_time():
                    indexer.run([u for u in index_urls if not exclusions.skip(u)], entry_url)
                if linkcheck and not stopped and not out_of_time():
                    linkcheck.run(should_stop=should_stop,
                                  progress=(lambda h: progress(analyzed, f"연계 링크 확인: {h}")) if progress else None)
                if (deferred_pages or (indexer and set(index_urls or []) - indexer.completed)
                        or (linkcheck and set(linkcheck.links) - linkcheck.completed)) and not stopped:
                    stopped = "budget"
                with control.phase("closing"):
                    ses.close()

        except ScanStopped as exc:
            stopped = exc.reason
    if checkpoint:
        checkpoint(assemble())
    return assemble()
