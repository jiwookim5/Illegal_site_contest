"""Page transition mechanism classification system for crawler evaluation.

Categorizes scenario families and cases by how pages and posts are navigated:
- static_link: standard static href / REST detail navigation
- pagination_bar: numbered pager bar click and page traversal
- get_form: GET form submission with hidden inputs (eGovFrame pattern)
- js_location: JavaScript location.href / location.assign navigation
- dom_replacement: in-page async DOM node replacement / expansion
- async_fetch: fetch/XHR dynamic data loading
- scroll_loading: infinite scroll and container scroll loading
- tabs_modal: tab panels, details/summary, dialog/modal overlays
- iframe_frame: frameset, iframe, nested iframe document exploration
- network_resilience: HTTP 429/503 retry and 404/500 fault tolerance
- ui_structure: complex UI structures (filters, breadcrumbs, semantic lists, comments)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

TRANSITION_TYPES = (
    "static_link",
    "pagination_bar",
    "get_form",
    "js_location",
    "dom_replacement",
    "async_fetch",
    "scroll_loading",
    "tabs_modal",
    "iframe_frame",
    "network_resilience",
    "ui_structure",
)

TRANSITION_META: Dict[str, Dict[str, Any]] = {
    "static_link": {
        "id": "static_link",
        "name": "정적 링크 및 REST 상세 이동",
        "short_name": "정적 링크",
        "badge_color": "#2563eb",
        "description": "<a> 태그의 href 쿼리 파라미터(?id=123) 또는 RESTful 계층 경로(/detail/1)를 통한 표준 하이퍼링크 탐색",
        "crawling_focus": "표준 a[href] 추출, 상대 경로(base href) 정규화, URL 중복 방문 방지(Deduplication), 정적 HTML 파서의 링크 수집 완전성",
        "families": (
            "table_get",
            "asp_numeric",
            "jsp_mode",
            "do_multiquery",
            "card_rest",
            "relative_path",
            "unordered_board",
            "jsp-query-table",
            "asp-query-cards",
        ),
    },
    "pagination_bar": {
        "id": "pagination_bar",
        "name": "번호형 페이지네이션 바",
        "short_name": "번호 페이징",
        "badge_color": "#0891b2",
        "description": "하단 번호 목록(1, 2, 3...) 및 다음/이전 링크를 통한 분할 페이지 순차 이동",
        "crawling_focus": "페이징 번호 링크 패턴 식별, 마지막 페이지 도달 감지, 순환 탐색 방지, 전체 페이지 순회 성공률",
        "families": (
            "numbered_pager",
            "finite-number-pages",
            "finite-pagination",
        ),
    },
    "get_form": {
        "id": "get_form",
        "name": "GET 폼 제출 및 숨은 필드",
        "short_name": "GET 폼 전송",
        "badge_color": "#059669",
        "description": "<form method='GET'> 양식 제출 및 hidden input(pageIndex, bbsId 등 전자정부 프레임워크 패턴) 전송을 통한 페이지 전환",
        "crawling_focus": "폼 컨트롤 추출, 기본/숨은 필드 값 직렬화, form action URL 조립 및 쿼리 파라미터 변환 수집",
        "families": (
            "egov-hidden-get",
            "get-page-index",
            "get-hidden-form",
        ),
    },
    "js_location": {
        "id": "js_location",
        "name": "자바스크립트 location 이동",
        "short_name": "JS Location",
        "badge_color": "#7c3aed",
        "description": "onclick/이벤트 내 location.href, location.assign() 호출 또는 <select onchange> 기반 동적 URL 이동",
        "crawling_focus": "JS 실행 컨텍스트 내 내비게이션 감지, 인라인 이벤트 핸들러(onclick) 분석 또는 헤드리스 브라우저 액션 실행",
        "families": (
            "js-go-function",
            "inline-location",
            "select-navigation",
            "listener-next-page",
        ),
    },
    "dom_replacement": {
        "id": "dom_replacement",
        "name": "동일 URL 비동기 / DOM 치환",
        "short_name": "DOM 치환",
        "badge_color": "#d97706",
        "description": "URL 변경 없이 버튼 클릭('더보기', '내용보기')으로 컨테이너 DOM 노드를 교체하거나 추가하는 방식",
        "crawling_focus": "동일 URL 내 상태 변화(State mutation) 감지, 클릭 인터랙션 후 DOM 뮤테이션 대기, 중복/기존 콘텐츠와의 차분 추출",
        "families": (
            "same-url-replacement",
            "delayed-more",
            "accessible-name",
        ),
    },
    "async_fetch": {
        "id": "async_fetch",
        "name": "비동기 Fetch / XHR 로딩",
        "short_name": "비동기 Fetch",
        "badge_color": "#ea580c",
        "description": "페이지 로드 후 fetch() 또는 XMLHttpRequest 비동기 호출을 통해 HTML/JSON 조각을 가져와 동적 렌더링",
        "crawling_focus": "네트워크 요청 인터셉트, XHR/Fetch 응답 대기(Network idle), 비동기 렌더링 완료 타이밍 동기화",
        "families": (
            "async-html-comments",
            "async-json-comments",
        ),
    },
    "scroll_loading": {
        "id": "scroll_loading",
        "name": "스크롤 트리거 / 지연 로딩",
        "short_name": "스크롤 로딩",
        "badge_color": "#4f46e5",
        "description": "윈도우 또는 내부 스크롤 컨테이너의 스크롤 이벤트(scroll down)에 따라 추가 콘텐츠를 동적으로 삽입",
        "crawling_focus": "브라우저 뷰포트 및 내부 스크롤 엘리먼트 가상 스크롤 트리거, 스크롤 후 DOM 안정화 대기, 무한 루프 감지",
        "families": (
            "window-scroll",
            "container-scroll",
            "scroll-insertion",
        ),
    },
    "tabs_modal": {
        "id": "tabs_modal",
        "name": "탭 패널 및 모달 / 다이얼로그",
        "short_name": "탭/모달 전환",
        "badge_color": "#db2777",
        "description": "ARIA 탭, <details>/<summary>, <dialog> 팝업, 모달 창 오버레이를 열어 내부 콘텐츠를 노출하는 UI 전환",
        "crawling_focus": "은닉된 탭/모달 트리거 클릭, aria-expanded/open 속성 조작, 오버레이 내부 DOM 접근성 트리 탐색",
        "families": (
            "aria-tabs",
            "dynamic-tabs",
            "native-details",
            "dialog-comments",
            "dialog-transition",
        ),
    },
    "iframe_frame": {
        "id": "iframe_frame",
        "name": "프레임 및 중첩 iframe 탐색",
        "short_name": "프레임 탐색",
        "badge_color": "#0284c7",
        "description": "레거시 <frameset>/<frame>, 인라인 <iframe>, 중첩 iframe(nested) 내부 문서로의 프레임 전환 탐색",
        "crawling_focus": "Page.frames 계층 순회, 프레임 내 DOM 트랙킹, iframe srcdoc/cross-origin 처리, 프레임 교체 시 동기화",
        "families": (
            "iframe-document",
            "iframe-srcdoc",
            "nested-iframes",
            "legacy-frame",
            "same-source-frames",
            "frame-replacement",
            "nested-frames",
        ),
    },
    "network_resilience": {
        "id": "network_resilience",
        "name": "네트워크 재시도 및 오류 극복",
        "short_name": "네트워크 탄력성",
        "badge_color": "#dc2626",
        "description": "HTTP 429(Rate Limit), 503(Service Unavailable) 일시 오류 시 재시도(Retry-After) 및 404/500 오류 복구",
        "crawling_focus": "지수 백오프/재시도(Retry-After 준수), 일시적 장애 극복, 치명적 에러 격리, 안전한 예외 처리 및 크롤러 생존성",
        "families": (
            "retry-429",
            "retry-503",
            "http-404",
            "http-500",
            "blocked-post",
            "blocked-delete",
        ),
    },
    "ui_structure": {
        "id": "ui_structure",
        "name": "특수 UI 구조 및 복합 탐색",
        "short_name": "특수 UI 구조",
        "badge_color": "#475569",
        "description": "분류 필터, 검색 폼, 공지 고정글, 브레드크럼, 계층형 댓글, 복합 위장 기법 등 복잡한 게시판 UI 패턴",
        "crawling_focus": "다양한 시맨틱 구조(dl, ol, table, card) 파싱, 복합 은닉 기법 탐지 대응, 특수 레이아웃 및 심층 탐색",
        "families": (
            "category_filter",
            "search_results",
            "notice_pinned",
            "nested_breadcrumb",
            "definition_list",
            "ordered_list",
            "calendar_list",
            "faq_public",
            "comment_list",
            "document_view",
            "related_links",
            "semantic_landmarks",
            "duplicate-dom-ids",
            "ancestor-style",
            "two-stage-replies",
            "short-title-detail",
            "composite-two",
            "composite-many",
            "negative-obfuscation",
            "inherited-transparency",
            "repeated-structure",
            "delegated-listener",
        ),
    },
}

# Inverted family-to-transition map
FAMILY_TO_TRANSITION: Dict[str, str] = {}
for _trans_type, _meta in TRANSITION_META.items():
    for _fam in _meta["families"]:
        FAMILY_TO_TRANSITION[_fam] = _trans_type


def get_transition_type(family: str, case: Optional[Dict[str, Any]] = None) -> str:
    """Return the transition mechanism type for a scenario family or case dict."""
    if case:
        explicit = case.get("transition_type")
        if explicit and explicit in TRANSITION_TYPES:
            return explicit
        tags = case.get("tags") or []
        for tag in tags:
            if tag in TRANSITION_TYPES:
                return tag

    if family in FAMILY_TO_TRANSITION:
        return FAMILY_TO_TRANSITION[family]

    # Partial match heuristics if needed
    lower_fam = family.lower()
    if any(k in lower_fam for k in ("page", "pager", "paging")):
        return "pagination_bar"
    if any(k in lower_fam for k in ("scroll",)):
        return "scroll_loading"
    if any(k in lower_fam for k in ("frame", "iframe")):
        return "iframe_frame"
    if any(k in lower_fam for k in ("form", "get-")):
        return "get_form"
    if any(k in lower_fam for k in ("retry", "404", "500", "429", "503", "blocked")):
        return "network_resilience"
    if any(k in lower_fam for k in ("tab", "dialog", "modal", "detail")):
        return "tabs_modal"
    if any(k in lower_fam for k in ("fetch", "xhr", "ajax")):
        return "async_fetch"
    if any(k in lower_fam for k in ("replace", "delayed")):
        return "dom_replacement"
    if any(k in lower_fam for k in ("location", "listener", "select")):
        return "js_location"

    return "static_link"


def get_transition_meta(trans_type: str) -> Dict[str, Any]:
    """Return metadata dict for the given transition type."""
    if trans_type in TRANSITION_META:
        return TRANSITION_META[trans_type]
    return {
        "id": trans_type,
        "name": trans_type,
        "short_name": trans_type,
        "badge_color": "#64748b",
        "description": "기타 이동 방식",
        "crawling_focus": "일반 웹 탐색 및 수집",
        "families": (),
    }


def list_transition_types() -> List[Dict[str, Any]]:
    """Return all transition types with full metadata."""
    return [TRANSITION_META[t] for t in TRANSITION_TYPES]


def classify_cases(cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group cases by their transition mechanism type."""
    grouped: Dict[str, List[Dict[str, Any]]] = {t: [] for t in TRANSITION_TYPES}
    for case in cases:
        ttype = get_transition_type(case.get("family", ""), case)
        grouped.setdefault(ttype, []).append(case)
    return grouped


def summarize_transitions(cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Summarize cases, routes, and negative traps grouped by transition mechanism."""
    result = {}
    for t in TRANSITION_TYPES:
        meta = get_transition_meta(t)
        t_cases = [c for c in cases if (c.get("transition_type") or get_transition_type(c.get("family", ""), c)) == t]
        routes_cnt = sum(len(c.get("routes", {})) for c in t_cases)
        trap_cnt = sum(
            1 for c in t_cases
            if any(t_target.get("role") == "negative" for cp in c.get("checkpoints", []) for t_target in cp.get("targets", []))
        )
        result[t] = {
            "name": meta["name"],
            "short_name": meta["short_name"],
            "cases": len(t_cases),
            "routes": routes_cnt,
            "negative_traps": trap_cnt,
        }
    return result

