"""조치 확인. 담당자가 광고를 지운 뒤, 광고가 나왔던 페이지만 다시 열어 정말 사라졌는지 본다.

전체 점검과 같은 브라우저 처리(BrowserSession)와 같은 판정(walk_frame)을 쓴다. 점검 때 잡힌 광고를
확인 때는 못 잡아 '사라짐'으로 잘못 알리는 일이 없게 하기 위함이다.
조회(GET)만 하고, 마지막 점검의 '천천히 점검' 설정(요청 간격·robots.txt)을 그대로 따른다.

결과 (항목마다)
  gone     페이지는 열리는데 그 광고가 없다                 -> 조치완료
  deleted  페이지가 404·410 으로 없어졌다 (글을 통째로 지움) -> 조치완료
  present  같은 광고가 다시 잡혔다                          -> 미조치 그대로
  unknown  접속 실패·서버 오류·시간 초과, 다른 페이지(로그인 화면 등)로 넘어감,
           광고가 있던 iframe 을 읽지 못함                  -> 이전 상태 그대로
  skipped  페이지를 다시 열어서는 확인할 수 없는 유형        -> 이전 상태 그대로
           (첨부파일·검색창·색인 목록·크롤러 위장·연계 링크. [다시 점검]으로 확인)
"""
from urllib.parse import urldefrag

from playwright.sync_api import sync_playwright

from politeness import DEFAULT_DELAY, Politeness
from findings import walk_frame
from session import BrowserSession
from urls import clean_url, page_key

# 페이지 화면에서 다시 찾을 수 있는 유형 (주요 4종 + 페이지 안에 든 추가 유형)
PAGE_TYPES = ("VISIBLE_AD", "OCCLUDED", "META_SPAM", "ATTR_SPAM", "LINK_SPAM")
GONE_STATUS = (404, 410)


def checkable(f):
    if f["technique"] != "ETC":
        return True
    return (f.get("extra_finding") or "").split("(")[0] in PAGE_TYPES


def _same(f, row):
    if row["technique"] != f["technique"]:
        return False
    if f["technique"] == "ETC" and (row.get("extra_finding") or "") != (f.get("extra_finding") or ""):
        return False
    return True


def still_there(f, rows):
    """다시 훑은 결과(rows)에 이 광고가 남아 있는가.

    같은 위치·같은 기법이면 남은 것이다. 게시판에 글이 더해져 순번(nth-of-type)이 밀리면 위치가
    달라지므로, 같은 기법으로 같은 문구가 다시 잡혀도 남은 것으로 본다.
    """
    text = (f.get("evidence_text") or "").strip()
    for r in rows:
        if not _same(f, r):
            continue
        if r["location"] == f["location"]:
            return True
        if text and (r.get("evidence_text") or "").strip() == text:
            return True
    return False


def recheck(findings, politeness=None, progress=None, should_stop=None, timeout_ms=20000, excluded_urls=()):
    """{항목 번호: 결과} 를 돌려준다. findings 는 점검 결과 항목 목록이다.

    politeness 는 마지막 점검의 요청 방식(Politeness.summary())이다.
    progress(지금 페이지 번호, 전체 페이지 수, 주소) 로 진행 상황을 알린다.
    """
    from scan_exclusions import ExcludedNavigation, ScanExclusions
    exclusions = ScanExclusions(excluded_urls)
    p = politeness or {}
    manners = Politeness(enabled=bool(p.get("enabled")), respect_robots=p.get("respect_robots", True),
                         delay=p.get("delay") or DEFAULT_DELAY)
    out = {i: "skipped" for i, f in enumerate(findings) if not checkable(f) or exclusions.skip(f["url"])}
    pages = {}
    for i, f in enumerate(findings):
        if i not in out:
            pages.setdefault(page_key(f["url"]), (f["url"], []))[1].append(i)
    if not pages:
        return out
    with sync_playwright() as pw:
        ses = BrowserSession(pw, timeout_ms)
        exclusions.attach(ses.ctx)
        try:
            for n, (url, idx) in enumerate(pages.values(), 1):
                if should_stop and should_stop():
                    break
                if progress:
                    progress(n, len(pages), url)
                if not manners.allowed(url):          # robots.txt 가 막은 주소는 열지 않는다
                    out.update({i: "unknown" for i in idx})
                    continue
                manners.wait()
                excluded_before = exclusions.hits
                try:
                    status = exclusions.open(ses, url)
                except ExcludedNavigation:
                    out.update({i: "skipped" for i in idx})
                    continue
                except Exception:
                    status = None
                if status is None or (status >= 400 and status not in GONE_STATUS):
                    out.update({i: "unknown" for i in idx})
                    continue
                if exclusions.skip(ses.page.url):
                    out.update({i: "skipped" for i in idx})
                    continue
                if status in GONE_STATUS:
                    out.update({i: "deleted" for i in idx})
                    continue
                # 로그인 화면·목록·안내 화면으로 넘겨졌으면 광고가 있던 글을 본 것이 아니다.
                # 광고가 남아 있는데 '사라짐'(조치완료)으로 적지 않도록 확인 불가로 둔다
                final = ses.page.url or ""
                if final.startswith(("http://", "https://")) and                         page_key(clean_url(urldefrag(final)[0])) != page_key(url):
                    out.update({i: "unknown" for i in idx})
                    continue
                ses.expand()
                rows, frame_failures = [], []
                try:
                    walk_frame(ses.page.main_frame, "", url, rows, set(), frame_failures=frame_failures)
                except Exception:
                    out.update({i: "unknown" for i in idx})
                    continue
                try:
                    for _ in ses.switch_views():
                        walk_frame(ses.page.main_frame, "", url, rows, set(), frame_failures=frame_failures)
                except Exception:
                    pass
                if exclusions.hits != excluded_before:
                    # 제외한 iframe 등이 보이지 않는 것을 광고 삭제로 확정하지 않는다.
                    out.update({i: "skipped" for i in idx})
                    continue
                for i in idx:
                    if still_there(findings[i], rows):
                        out[i] = "present"
                    elif any(findings[i]["location"].startswith(p) for p in frame_failures):
                        out[i] = "unknown"           # 그 광고가 있던 iframe 을 이번에는 읽지 못했다
                    else:
                        out[i] = "gone"
        finally:
            ses.close()
    # 멈춘 경우 확인하지 못한 페이지는 이전 상태 그대로 둔다
    for i in range(len(findings)):
        out.setdefault(i, "unknown")
    return out
