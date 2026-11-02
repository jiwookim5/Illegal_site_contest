"""120 synthetic, manually labelled static UI fixtures; no production-site claims.

Labels follow the competition's four concealment categories. This module does not
import or consult the scanner, classifier, detector, or production signature bundle.
Families are grouping units: generated siblings must stay in the same evaluation split.
"""
from html import escape
from testsite.scenarios.ui import finish_routes
from urllib.parse import quote

from testsite.scenarios.benign_pool import (
    BENIGN_PUBLIC_POSTS,
    FALSE_POSITIVE_TRAPS,
    render_benign_detail_page,
)


# Family, independent navigation/layout feature, title element, target container,
# URL convention, optional intermediate list. Each family has six different labels.
FAMILIES = (
    ("table_get", "표형 게시판의 GET 상세 링크", "h1", "td", "do", False),
    ("unordered_board", "비정렬 목록의 ASP 글 링크", "h2", "div", "asp", False),
    ("card_rest", "카드 목록과 REST 게시글 경로", "h3", "section", "rest", False),
    ("jsp_mode", "JSP mode 파라미터 상세 보기", "span", "article", "jsp", False),
    ("asp_numeric", "ASP 숫자 ID와 게시판 코드", "h1", "p", "asp", False),
    ("do_multiquery", ".do 게시판·메뉴·글 번호 다중 쿼리", "h2", "section", "do", False),
    ("relative_path", "상대 경로를 사용하는 목록과 상세", "h3", "div", "relative", False),
    ("numbered_pager", "번호 페이지 링크 뒤의 글 목록", "span", "td", "jsp", True),
    ("category_filter", "분야별 목록을 거치는 글 탐색", "h1", "article", "rest", True),
    ("search_results", "GET 검색 결과의 제목·설명 구조", "h2", "div", "search", False),
    ("notice_pinned", "상단 고정 공지와 일반 글의 구분", "h3", "section", "do", False),
    ("nested_breadcrumb", "경로 안내와 중첩 메뉴 뒤 상세", "span", "p", "rest", True),
    ("definition_list", "정의 목록으로 표시한 자료 목록", "h1", "div", "jsp", False),
    ("ordered_list", "순서 목록과 글 번호가 있는 게시판", "h2", "article", "asp", False),
    ("calendar_list", "날짜별 일정 목록의 상세 안내", "h3", "section", "calendar", False),
    ("faq_public", "질문 목록에서 정적 답변 문서로 이동", "span", "div", "jsp", False),
    ("comment_list", "게시글의 공개 댓글 구획", "h1", "p", "rest", False),
    ("document_view", "문서 설명과 그림 설명 구획", "h2", "section", "unicode", False),
    ("related_links", "관련 자료 영역의 상세 링크", "h3", "article", "do", False),
    ("semantic_landmarks", "header·nav·main·aside의 문서 구조", "span", "div", "rest", False),
)

VARIANTS = (
    ("transparent", "TRANSPARENT", "투명한 광고 문구"),
    ("offscreen", "OFFSCREEN", "화면 왼쪽 바깥의 광고 문구"),
    ("homoglyph", "HOMOGLYPH", "전각 영문으로 위장한 광고 단어"),
    ("jamo", "JAMO", "호환 자모로 분해한 광고 단어"),
    ("normal", None, "정상 안내 또는 예방 문맥 반례"),
    ("visible_ad", None, "숨김과 위장이 없는 보이는 광고"),
)


ADMIN_TITLES = (
    "2026년 하반기 공공시설물 정기 안전점검 및 주민 협조 안내",
    "불법 현수막·광고물 일제 정비 및 쾌적한 도시환경 조성 계획 공표",
    "주민자치센터 하반기 문화강좌 수강생 모집 및 시설 이용 안내",
    "동절기 취약계층 에너지 바우처 지원 신청 및 접수 안내",
    "보행자 안심 귀갓길 조성 사업 추진 경과 및 주민 의견 수렴",
    "지역 주민 건강증진 프로그램 및 보건소 정기 검진 안내",
    "공공 데이터 개방 및 디지털 행정서비스 이용 활성화 계획",
    "스마트 자원순환 및 생활폐기물·재활용품 분리배출 요령 안내",
    "소상공인 경영안정자금 특별보증 및 이자차액 보전 지원 공고",
    "어린이보호구역 교통안전 시설 개선 및 불법주정차 특별단속 안내",
    "2026년도 주민참여예산 제안사업 공모 및 온라인 시민투표 안내",
    "청년 취업역량 강화 아카데미 및 1:1 맞춤형 멘토링 프로그램",
    "공공도서관 야간 개관 연장 및 독서문화 축제 개최 안내",
    "지진·풍수해 대비 주민 대피소 지정 현황 및 행동요령 공표",
    "공공 체육시설 정기 대관 신청 및 사용료 감면 대상자 안내",
    "노후 경유차 조기폐차 및 배출가스 저감장치 부착 지원 공고",
    "주민등록 사실조사 및 비대면 사실조사 참여 방법 안내",
    "반려동물 광견병 예방접종 및 동물등록제 의무화 홍보",
    "전통시장 활성화 및 온누리상품권 특별 할인 판매 안내",
    "공공 와이파이(Public WiFi) 확대 구축 지역 및 이용 방법 공표",
)

DEPARTMENTS = (
    ("생활안전과", "안전점검팀", "02-120 (내선 101)"),
    ("도시정비과", "광고물정비팀", "02-120 (내선 102)"),
    ("자치행정과", "주민자치팀", "02-120 (내선 103)"),
    ("복지정책과", "기초보장팀", "02-120 (내선 104)"),
    ("스마트행정과", "디지털소통팀", "02-120 (내선 105)"),
    ("보건행정과", "건강증진팀", "02-120 (내선 106)"),
    ("정보통신과", "데이터운영팀", "02-120 (내선 107)"),
    ("자원순환과", "청소행정팀", "02-120 (내선 108)"),
    ("지역경제과", "소상공인지원팀", "02-120 (내선 109)"),
    ("교통행정과", "교통지도팀", "02-120 (내선 110)"),
    ("기획예산과", "참여예산팀", "02-120 (내선 111)"),
    ("일자리청년과", "청년지원팀", "02-120 (내선 112)"),
    ("교육문화과", "도서관운영팀", "02-120 (내선 113)"),
    ("치수방재과", "재난대응팀", "02-120 (내선 114)"),
    ("체육진흥과", "시설관리팀", "02-120 (내선 115)"),
    ("기후환경과", "대기관리팀", "02-120 (내선 116)"),
    ("민원여권과", "가족등록팀", "02-120 (내선 117)"),
    ("반려동물과", "동물보호팀", "02-120 (내선 118)"),
    ("시장경제과", "상권활성화팀", "02-120 (내선 119)"),
    ("스마트도시과", "통신망관리팀", "02-120 (내선 120)"),
)

FAMILIES_DICT = {fam[0]: idx for idx, fam in enumerate(FAMILIES)}

EGOV_CSS = (
    "* { box-sizing: border-box; }"
    "body { margin: 0; padding: 0; background: #f4f6f9; color: #222; font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', '맑은 고딕', helvetica, sans-serif; font-size: 15px; line-height: 1.6; }"
    ".gov-top-banner { background: #1a3c6e; color: #fff; padding: 7px 20px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }"
    ".gov-top-banner .gov-badge { background: #0c254b; padding: 2px 8px; border-radius: 3px; font-weight: bold; margin-right: 8px; }"
    ".gov-top-banner .gov-util { display: flex; gap: 12px; font-size: 12px; opacity: 0.9; }"
    ".gov-header { background: #fff; border-bottom: 2px solid #1a3c6e; padding: 14px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }"
    ".gov-header-inner { max-width: 1000px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }"
    ".gov-logo { font-size: 20px; font-weight: bold; color: #1a3c6e; }"
    ".gov-gnb { display: flex; gap: 20px; font-size: 14px; font-weight: 500; color: #475569; }"
    ".gov-container { max-width: 1000px; margin: 20px auto; padding: 0 16px 40px; }"
    ".gov-breadcrumb { font-size: 13px; color: #64748b; margin-bottom: 16px; padding: 10px 14px; background: #fff; border: 1px solid #e2e8f0; border-radius: 4px; display: flex; align-items: center; gap: 6px; }"
    ".gov-breadcrumb .sep { color: #94a3b8; }"
    ".gov-breadcrumb .current { font-weight: 600; color: #1a3c6e; }"
    ".board-detail-wrap { background: #fff; border: 1px solid #d9e2ec; border-radius: 6px; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 24px; }"
    ".board-view-header { border-bottom: 2px solid #1a3c6e; padding-bottom: 16px; margin-bottom: 20px; }"
    ".board-view-title { font-size: 21px; font-weight: 700; color: #0f172a; margin: 0 0 16px 0; line-height: 1.4; }"
    ".board-meta-table { width: 100%; border-collapse: collapse; font-size: 13px; border-top: 1px solid #cbd5e1; }"
    ".board-meta-table th { background: #f8fafc; color: #334155; font-weight: 600; padding: 9px 14px; text-align: left; width: 14%; border-bottom: 1px solid #e2e8f0; }"
    ".board-meta-table td { padding: 9px 14px; color: #475569; width: 36%; border-bottom: 1px solid #e2e8f0; }"
    ".board-view-table { width: 100%; border-collapse: collapse; font-size: 14px; margin: 12px 0; border: 1px solid #e2e8f0; }"
    ".board-view-table th { background: #f1f5f9; padding: 10px 14px; width: 15%; text-align: left; border: 1px solid #e2e8f0; }"
    ".board-view-table td { padding: 10px 14px; border: 1px solid #e2e8f0; }"
    ".attach-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 14px 18px; margin: 20px 0; }"
    ".attach-head { font-weight: 700; font-size: 14px; color: #1e293b; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }"
    ".attach-count { font-size: 12px; color: #64748b; font-weight: normal; }"
    ".attach-list { list-style: none; padding: 0; margin: 0; }"
    ".attach-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px dashed #e2e8f0; }"
    ".attach-item:last-child { border-bottom: none; }"
    ".badge-file { display: inline-block; padding: 2px 6px; font-size: 11px; font-weight: 700; border-radius: 3px; color: #fff; }"
    ".badge-hwp { background: #2563eb; }"
    ".badge-pdf { background: #dc2626; }"
    ".file-name { font-weight: 500; color: #334155; }"
    ".file-size { color: #94a3b8; font-size: 12px; }"
    ".btn-file-action { font-size: 12px; padding: 2px 8px; border: 1px solid #cbd5e1; background: #fff; border-radius: 3px; cursor: pointer; color: #334155; margin-left: 4px; }"
    ".board-content { padding: 20px 4px; min-height: 180px; color: #1e293b; font-size: 15px; line-height: 1.8; word-break: break-word; }"
    ".gov-intro, .gov-outro { color: #475569; margin: 14px 0; line-height: 1.7; }"
    ".gov-sign { margin-top: 28px; text-align: right; color: #334155; font-weight: 600; }"
    ".comment-section { margin-top: 30px; border-top: 2px solid #e2e8f0; padding-top: 20px; }"
    ".comment-header { font-size: 15px; font-weight: 700; color: #1e293b; margin-bottom: 12px; }"
    ".comment-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 12px 16px; margin-bottom: 10px; }"
    ".comment-meta { font-size: 12px; color: #64748b; margin-bottom: 4px; display: flex; gap: 12px; }"
    ".comment-author { font-weight: 600; color: #334155; }"
    ".btn-area { display: flex; justify-content: center; gap: 8px; margin-top: 24px; padding-top: 18px; border-top: 1px solid #e2e8f0; }"
    ".btn { padding: 8px 18px; font-size: 14px; font-weight: 500; border-radius: 4px; border: 1px solid #cbd5e1; background: #fff; color: #334155; cursor: pointer; text-decoration: none; }"
    ".btn-primary { background: #1a3c6e; color: #fff; border-color: #1a3c6e; }"
    ".board-list-wrap { background: #fff; padding: 20px; border: 1px solid #e2e8f0; border-radius: 6px; }"
    ".board-search-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; font-size: 13px; }"
    ".board-total strong { color: #1a3c6e; }"
    ".search-form { display: flex; gap: 6px; }"
    ".input-search { padding: 5px 10px; border: 1px solid #cbd5e1; border-radius: 3px; font-size: 13px; }"
    ".btn-search { padding: 5px 12px; background: #1a3c6e; color: #fff; border: 1px solid #1a3c6e; border-radius: 3px; cursor: pointer; font-size: 13px; }"
    "table.board-list { width: 100%; border-collapse: collapse; margin-top: 8px; background: #fff; border-top: 2px solid #1a3c6e; }"
    "table.board-list th { background: #f8fafc; padding: 11px 8px; border-bottom: 1px solid #cbd5e1; font-weight: 600; font-size: 13px; color: #334155; }"
    "table.board-list td { padding: 10px 8px; border-bottom: 1px solid #e2e8f0; text-align: center; font-size: 13px; color: #475569; }"
    "table.board-list td.title-col { text-align: left; }"
    "table.board-list td.title-col a { color: #1e293b; text-decoration: none; font-weight: 500; }"
    "table.board-list td.title-col a:hover { text-decoration: underline; color: #1a3c6e; }"
    ".badge-pinned { background: #fee2e2; color: #b91c1c; font-weight: 600; padding: 2px 6px; border-radius: 3px; font-size: 11px; }"
    ".badge-normal { background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 3px; font-size: 11px; }"
    ".pagination { display: flex; justify-content: center; align-items: center; gap: 4px; margin-top: 18px; }"
    ".pagination a { display: inline-block; padding: 4px 10px; border: 1px solid #1a3c6e; background: #1a3c6e; color: #fff; border-radius: 3px; font-size: 13px; font-weight: bold; text-decoration: none; }"
    ".page-current { display: inline-block; padding: 4px 10px; background: #1a3c6e; color: #fff; border-radius: 3px; font-size: 13px; font-weight: bold; }"
    ".page-link { padding: 4px 10px; border: 1px solid #cbd5e1; background: #fff; color: #475569; border-radius: 3px; font-size: 13px; cursor: pointer; }"
    ".page-btn { padding: 4px 10px; border: 1px solid #cbd5e1; background: #f8fafc; color: #475569; border-radius: 3px; font-size: 13px; cursor: pointer; }"
    ".cards { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }"
    ".cards > a { display: block; padding: 18px; border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; text-decoration: none; color: inherit; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }"
    ".cards > a:hover { border-color: #1a3c6e; }"
    ".card-desc { font-size: 13px; color: #64748b; margin: 8px 0; }"
    ".card-meta { font-size: 12px; color: #94a3b8; display: flex; justify-content: space-between; }"
    ".gov-badge { display: inline-block; padding: 2px 8px; font-size: 12px; border-radius: 3px; margin-right: 6px; }"
    ".gov-badge-alert { background: #d9534f; color: #fff; }"
    ".gov-badge-info { background: #0275d8; color: #fff; }"
    "iframe { width: 100%; max-width: 600px; height: 200px; border: 1px solid #cbd5e1; border-radius: 4px; }"
    "#target { font-size: 15px; }"
)


def _render_post_view(title_tag, title_text, target_content, dept_info, date_str, views):
    dept_name, team_name, phone = dept_info
    files = [
        ("HWP", "2026_주민안내_세부시행계획서.hwp", "2.8 MB"),
        ("PDF", "붙임1_시설별_점검일정표_및_서식.pdf", "1.4 MB"),
    ]
    file_items = "".join(
        f'<li class="attach-item">'
        f'<span class="badge-file badge-{ftype.lower()}">{ftype}</span>'
        f'<span class="file-name">{fname}</span>'
        f'<span class="file-size">({fsize})</span>'
        f'<span class="btn-file-action">미리보기</span>'
        f'<span class="btn-file-action">다운로드</span>'
        f'</li>'
        for ftype, fname, fsize in files
    )
    return (
        f'<article class="board-detail-wrap">'
        f'<header class="board-view-header">'
        f'<{title_tag} class="board-view-title">{escape(title_text)}</{title_tag}>'
        f'<table class="board-meta-table" summary="게시글 메타 정보표">'
        f'<caption>게시글 상세 정보</caption><tbody>'
        f'<tr><th scope="row">담당부서</th><td>{dept_name} ({team_name})</td>'
        f'<th scope="row">문의전화</th><td>{phone}</td></tr>'
        f'<tr><th scope="row">작성일자</th><td>{date_str}</td>'
        f'<th scope="row">조회수</th><td>{views:,}회</td></tr>'
        f'</tbody></table>'
        f'</header>'
        f'<section class="attach-box" aria-label="첨부파일">'
        f'<div class="attach-head"><strong>첨부파일</strong><span class="attach-count">총 {len(files)}건</span></div>'
        f'<ul class="attach-list">{file_items}</ul>'
        f'</section>'
        f'<section class="board-content">'
        f'<div class="gov-intro">'
        f'<p>안녕하십니까. 주민 여러분의 생활 안전과 편익 증진을 위해 협조해 주셔서 감사드립니다.</p>'
        f'<p>「행정절차법」 및 관련 행정안전부 지침에 따라 아래와 같이 안내드리오니 관련 업무 및 시설 이용에 참고하시기 바랍니다.</p>'
        f'</div>'
        f'{target_content}'
        f'<div class="gov-outro">'
        f'<p>본 공지 및 행정 사항과 관련하여 궁금하신 점은 상단 기재된 담당 부서로 문의하여 주시기 바랍니다.</p>'
        f'<p class="gov-sign">2026년 10월<br><strong>스마트행정안전구청 열린민원실</strong></p>'
        f'</div>'
        f'</section>'
        f'<footer class="btn-area">'
        f'<span class="btn btn-primary">목록</span>'
        f'<span class="btn">인쇄</span>'
        f'<span class="btn">공유</span>'
        f'</footer>'
        f'</article>'
    )


def _document(title, content):
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            f"<title>{escape(title)} - 스마트행정안전포털</title>"
            f"<style>{EGOV_CSS}</style>"
            "</head><body>"
            "<header class=\"gov-top-banner\">"
            "<div class=\"gov-badge\">대한민국 공식 전자정부 포털</div>"
            "<div class=\"gov-util\"><span class=\"gov-util-item\">공식 인증 서비스</span><span class=\"gov-util-item\">보안 접속 중</span></div>"
            "</header>"
            "<header class=\"gov-header\">"
            "<div class=\"gov-header-inner\">"
            "<div class=\"gov-logo\">🏛️ 스마트행정안전포털</div>"
            "<div class=\"gov-gnb\"><span>정보공개</span><span>민원서비스</span><span>참여소통</span><span>기관소개</span></div>"
            "</div>"
            "</header>"
            "<main class=\"gov-container\">"
            "<nav class=\"gov-breadcrumb\" aria-label=\"현재 위치\">"
            "<span class=\"bc-home\">홈</span><span class=\"sep\">&gt;</span>"
            "<span>정보공개</span><span class=\"sep\">&gt;</span>"
            "<span>사전정보공표</span><span class=\"sep\">&gt;</span>"
            "<span class=\"current\">공지사항</span>"
            "</nav>"
            f"{content}"
            "</main>"
            "</body></html>")


def _route(html):
    return {"body": html, "status": 200, "content_type": "text/html; charset=utf-8"}


def _detail_path(root, convention, variant, family_index):
    # Query names and shapes vary as well as values; these are synthetic conventions.
    if convention == "do":
        return f"{root}selectArticle.do?boardId=community&nttId={100 + variant}&menuNo={20 + family_index}"
    if convention == "asp":
        return f"{root}Read.asp?BoardCode=public&IDX={300 + variant}&Page={variant + 1}"
    if convention == "jsp":
        return f"{root}board.jsp?mode=view&bid=notice&seq={500 + variant}"
    if convention == "relative":
        return f"{root}archive/2026/{variant + 1:02d}/article.html"
    if convention == "search":
        query = quote(("이용 안내", "교육 일정", "공개 자료", "문화 행사", "예방 교육", "새 소식")[variant])
        return f"{root}search/view.do?searchTerm={query}&record={variant + 1}"
    if convention == "calendar":
        return f"{root}calendar/view?year=2026&month={variant + 1:02d}&day=15&event=public"
    if convention == "unicode":
        return f"{root}{quote('공개자료')}/{quote('안내문')}-{variant + 1}.html"
    return f"{root}boards/community/posts/{700 + variant}"


def _link(path, label="안내 자료 자세히 보기"):
    return f'<a href="{escape(path, quote=True)}">{escape(label)}</a>'


def _pagination_bar() -> str:
    return '<div class="pagination"><span class="page-current">1</span></div>'


def _select_benign_and_trap_posts(family_index: int, variant: int):
    """Deterministically select 3 benign public posts and 2 false-positive traps."""
    b_len = len(BENIGN_PUBLIC_POSTS)
    b_start = (family_index * 3 + variant) % b_len
    benigns = [BENIGN_PUBLIC_POSTS[(b_start + i) % b_len] for i in range(3)]

    t_len = len(FALSE_POSITIVE_TRAPS)
    t_start = (family_index * 2 + variant) % t_len
    traps = [FALSE_POSITIVE_TRAPS[(t_start + i) % t_len] for i in range(2)]

    return benigns, traps


def _extra_post_path(root: str, convention: str, post_idx: int, family_index: int, post: dict) -> str:
    """Generate deterministic, collision-free URL paths for benign public posts and bait traps."""
    if convention == "do":
        return f"{root}selectArticle.do?boardId=community&nttId={200 + post_idx}&menuNo={20 + family_index}"
    if convention == "asp":
        return f"{root}Read.asp?BoardCode=public&IDX={400 + post_idx}&Page=1"
    if convention == "jsp":
        return f"{root}board.jsp?mode=view&bid=notice&seq={600 + post_idx}"
    if convention == "relative":
        return f"{root}archive/2026/notice/{post_idx:02d}.html"
    if convention == "search":
        query = quote(post["title"][:4])
        return f"{root}search/view.do?searchTerm={query}&record={10 + post_idx}"
    if convention == "calendar":
        return f"{root}calendar/view?year=2026&month=10&day={16 + post_idx:02d}&event=public"
    if convention == "unicode":
        return f"{root}{quote('공개자료')}/{quote(post['id'])}.html"
    return f"{root}boards/community/posts/{800 + post_idx}"


def _listing(family: str, items, variant: int):
    family_index = FAMILIES_DICT.get(family, 0)

    if isinstance(items, str):
        # Backwards compatibility fallback for single-string path
        items = [{
            "href": items,
            "title": ADMIN_TITLES[family_index % len(ADMIN_TITLES)],
            "dept": DEPARTMENTS[family_index % len(DEPARTMENTS)][0],
            "date": f"2026-10-{variant + 1:02d}",
            "summary": "주민 안내 자료의 상세 페이지입니다.",
            "is_pinned": (family == "notice_pinned"),
        }]

    if family in {"table_get", "do_multiquery", "asp_numeric", "notice_pinned"}:
        rows = []
        for idx, item in enumerate(items, 1):
            badge = '<span class="badge-pinned">고정공지</span>' if item.get("is_pinned") else '<span class="badge-normal">일반</span>'
            link = _link(item["href"], item["title"])
            rows.append(
                f'<tr>'
                f'<td>{idx}</td>'
                f'<td>{badge}</td>'
                f'<td class="title-col">{link}</td>'
                f'<td>{escape(item["dept"])}</td>'
                f'<td>{escape(item["date"])}</td>'
                f'</tr>'
            )
        tbody = "".join(rows)
        return (
            '<div class="board-list-wrap">'
            '<div class="board-search-bar">'
            '<div class="board-total">총 <strong>120</strong>건 (1/12 페이지)</div>'
            '<div class="search-form"><input type="text" class="input-search" placeholder="제목, 담당부서 검색" disabled>'
            '<span class="btn-search">검색</span></div>'
            '</div>'
            '<table class="board-list"><caption>공개 게시판 목록</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead><tbody>'
            f'{tbody}'
            '</tbody></table>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "card_rest":
        cards = []
        for item in items:
            cards.append(
                f'<a href="{escape(item["href"], quote=True)}">'
                f'<h4 style="margin:0 0 6px 0;font-size:15px;color:#1e293b;font-weight:600;">{escape(item["title"])}</h4>'
                f'<p class="card-desc">{escape(item["summary"])}</p>'
                f'<div class="card-meta"><span>담당: {escape(item["dept"])}</span> <span>작성일: {escape(item["date"])}</span></div>'
                f'</a>'
            )
        cards_html = "".join(cards)
        return (
            '<div class="board-list-wrap">'
            f'<section class="cards" aria-label="자료 카드">{cards_html}</section>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "definition_list":
        dl_items = []
        for idx, item in enumerate(items, 1):
            link = _link(item["href"], item["title"])
            dl_items.append(
                f'<dt style="font-weight:600;color:#1a3c6e;margin-top:12px;">[{idx}] {escape(item["dept"])}</dt>'
                f'<dd style="margin:4px 0 2px 16px;font-size:15px;">{link}</dd>'
                f'<dd style="margin:0 0 8px 16px;font-size:13px;color:#64748b;">{escape(item["summary"])} ({escape(item["date"])})</dd>'
            )
        dl_html = "".join(dl_items)
        return (
            '<div class="board-list-wrap">'
            f'<dl class="board-dl">{dl_html}</dl>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family in {"ordered_list", "numbered_pager"}:
        li_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            li_items.append(
                f'<li style="padding:6px 0;border-bottom:1px dashed #e2e8f0;">'
                f'{link} <span style="font-size:12px;color:#64748b;">[{escape(item["dept"])} | {escape(item["date"])}]</span>'
                f'</li>'
            )
        ol_html = "".join(li_items)
        return (
            '<div class="board-list-wrap">'
            f'<ol class="board-ol" start="1">{ol_html}</ol>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "search_results":
        res_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            res_items.append(
                f'<article class="search-result-item" style="padding:12px 0;border-bottom:1px solid #e2e8f0;">'
                f'<h3 style="margin:0 0 6px 0;font-size:16px;">{link}</h3>'
                f'<p style="margin:0;font-size:13px;color:#475569;">{escape(item["summary"])}</p>'
                f'<div style="font-size:12px;color:#94a3b8;margin-top:4px;">담당부서: {escape(item["dept"])} | 등록일: {escape(item["date"])}</div>'
                f'</article>'
            )
        res_html = "".join(res_items)
        return (
            '<div class="board-list-wrap">'
            f'<section class="search-res-wrap" aria-label="검색 결과">'
            f'<h2 style="font-size:18px;margin:0 0 14px 0;color:#0f172a;">검색 결과 (총 {len(items)}건)</h2>'
            f'{res_html}'
            f'</section>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "calendar_list":
        cal_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            day_str = item["date"].split("-")[-1] if "-" in item["date"] else "15"
            cal_items.append(
                f'<li style="padding:8px 0;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;gap:12px;">'
                f'<time datetime="{escape(item["date"])}" style="background:#1a3c6e;color:#fff;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:600;">{day_str}일</time>'
                f'<div style="flex:1;">{link}</div>'
                f'<span class="cal-dept" style="font-size:12px;color:#64748b;">({escape(item["dept"])})</span>'
                f'</li>'
            )
        cal_html = "".join(cal_items)
        return (
            '<div class="board-list-wrap">'
            f'<ul class="calendar-list" aria-label="일정" style="list-style:none;padding:0;margin:0;">{cal_html}</ul>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "faq_public":
        faq_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            faq_items.append(
                f'<li style="padding:10px 0;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;gap:10px;">'
                f'<span style="background:#2563eb;color:#fff;padding:2px 7px;border-radius:50%;font-size:12px;font-weight:bold;">Q</span>'
                f'<div style="flex:1;">{link}</div>'
                f'<span style="font-size:12px;color:#64748b;">[{escape(item["dept"])}]</span>'
                f'</li>'
            )
        faq_html = "".join(faq_items)
        return (
            '<div class="board-list-wrap">'
            f'<section class="faq-list" aria-label="자주 묻는 질문">'
            f'<h2 style="font-size:18px;margin:0 0 14px 0;color:#0f172a;">주민들이 자주 묻는 주요 질문 안내</h2>'
            f'<ul style="list-style:none;padding:0;margin:0;">{faq_html}</ul>'
            f'</section>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "related_links":
        rel_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            rel_items.append(
                f'<li style="padding:6px 0;border-bottom:1px dashed #e2e8f0;">'
                f'{link} <span style="font-size:12px;color:#64748b;">({escape(item["dept"])})</span>'
                f'</li>'
            )
        rel_html = "".join(rel_items)
        return (
            '<div class="board-list-wrap">'
            '<article class="related-intro" style="margin-bottom:16px;">'
            '<h2 style="font-size:18px;margin:0 0 8px 0;color:#0f172a;">관련 정책 자료 소개</h2>'
            '<p style="font-size:14px;color:#475569;margin:0;">주민 생활 안전 및 행정 복지 관련 안내 지침과 세부 계획을 확인하세요.</p>'
            '</article>'
            f'<aside aria-label="관련 자료"><ul style="list-style:none;padding:0;margin:0;">{rel_html}</ul></aside>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "nested_breadcrumb":
        li_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            li_items.append(
                f'<li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">'
                f'{link} <span style="font-size:12px;color:#64748b;">[{escape(item["dept"])} | {escape(item["date"])}]</span>'
                f'</li>'
            )
        li_html = "".join(li_items)
        return (
            f'<nav class="sub-nav" aria-label="현재 위치"><ol style="display:flex;gap:6px;list-style:none;padding:0;margin-bottom:14px;font-size:13px;color:#64748b;"><li>자료실</li><li>&gt;</li><li>공개 정보</li></ol></nav>'
            f'<main><section class="board-list-wrap">'
            f'<ul class="board-ul" style="list-style:none;padding:0;margin:0;">{li_html}</ul>'
            f'{_pagination_bar()}'
            f'</section></main>'
        )

    if family == "semantic_landmarks":
        li_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            li_items.append(
                f'<li style="padding:6px 0;border-bottom:1px dashed #e2e8f0;">'
                f'{link} <span style="font-size:12px;color:#64748b;">({escape(item["dept"])})</span>'
                f'</li>'
            )
        li_html = "".join(li_items)
        return (
            '<div class="board-list-wrap">'
            '<header style="margin-bottom:12px;"><p style="font-weight:600;color:#1a3c6e;margin:0;">스마트행정안전구청 열린마당</p></header>'
            f'<nav aria-label="자료"><ul style="list-style:none;padding:0;margin:0;">{li_html}</ul></nav>'
            '<main style="margin:16px 0;"><p style="font-size:13px;color:#64748b;">열린 시정 주요 안내 자료 목록입니다.</p></main>'
            '<aside style="font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:8px;">민원실 운영 시간 안내: 평일 09:00~18:00</aside>'
            f'{_pagination_bar()}'
            '</div>'
        )

    if family == "document_view":
        fig_items = []
        for item in items:
            link = _link(item["href"], item["title"])
            fig_items.append(
                f'<figure class="doc-cover-figure" style="margin:0;padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:4px;">'
                f'<div aria-label="문서 표지" style="height:70px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:12px;color:#64748b;margin-bottom:8px;border-radius:3px;">공공 안내문 표지</div>'
                f'<figcaption style="font-size:14px;">{link}<div style="font-size:12px;color:#94a3b8;margin-top:4px;">{escape(item["dept"])} | {escape(item["date"])}</div></figcaption>'
                f'</figure>'
            )
        fig_html = "".join(fig_items)
        return (
            '<div class="board-list-wrap">'
            f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-bottom:16px;">'
            f'{fig_html}'
            f'</div>'
            f'{_pagination_bar()}'
            '</div>'
        )

    # Default (unordered_board, comment_list, etc.)
    li_items = []
    for item in items:
        link = _link(item["href"], item["title"])
        li_items.append(
            f'<li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">'
            f'{link} <span style="font-size:12px;color:#64748b;">[{escape(item["dept"])} | {escape(item["date"])}]</span>'
            f'</li>'
        )
    li_html = "".join(li_items)
    return (
        '<div class="board-list-wrap">'
        f'<ul class="board-ul" aria-label="공개 글 목록" style="list-style:none;padding:0;margin:0;">{li_html}</ul>'
        f'{_pagination_bar()}'
        '</div>'
    )


# Real-world inspired phrases from google_dataset_20260930
TRANSPARENT_PHRASES = (
    "먹튀검증 | 구글검색 꽁타 먹튀 피하는 법, 안전 보증업체 꽁머니 첫충 30% 지급. 텔레그램 @deal_alpha",
    "바카라 실시간 라이브 게임 참여, 신규 첫 충전 20% 지급. 텔레그램 @deal_bravo",
    "메이저-놀이터 : 스포츠 베팅, 실시간 파워볼 홀덤 안전 보증업체 가입 문의 텔레그램 @deal_charlie",
    "성인방송 19금 라이브 영상 유료 스트리밍, 구매 문의 텔레그램 @deal_delta",
    "추천하는 토토 사이트, 먹튀 검증 완료, 첫충 매충 입플 혜택 안내 텔그: @deal_echo",
    "로투스 바카라 사이트 안전 보증업체 카지노 토토 TOP 6 신규 가입머니 즉시 지급 telegram @deal_foxtrot",
    "온라인 슬롯 머신 게임 안전 보증업체 카지노 토토 무료체험 충전 보너스 30% 지급 @deal_golf",
    "카지노입플 핵심 보안 지표 정밀 리포트 첫충 30% 매충 10% 지급 텔레그램 @deal_hotel",
    "골드피시카지노 공식인증업체, 롤링 0% 무제한 환전 미러 도메인 safe-bet.top",
    "출장마사지 예약 안내, 자택 호텔 모텔 24시간 방문 케어 상담 텔레그램 @deal_india",
    "사설토토 메이저사이트 추천 배당률 1위 단폴 크로스 무제한 배팅 tg:@deal_juliet",
    "한국야동 무료보기 고화질 성인동영상 최신 스트리밍 바로가기 adult-tube.vip",
    "에볼루션 바카라 라이브 카지노 실시간 게임 참여 첫충 20% 보너스 지급 @deal_kilo",
    "성인방송 19금 라이브 BJ 소통 방송 무료 쿠폰 즉시 지급 hot-live.online",
    "슬롯사이트 추천, 무료체험 프라그마틱 슬롯 머신 게임 환전 보장 코드 WIN77",
    "조건만남 실시간 1:1 매칭 24시간 비밀 보장 프로필 안내 텔레그램 @deal_mike",
    "안전놀이터 추천 먹튀검증 완료 사설토토 첫충 30% 지급 텔레그램 @deal_november",
    "스웨디시 힐링 마사지 출장안마 20대 관리사 대기 예약 상담 텔레그램 @deal_oscar",
    "토토 입플 사이트 추천, 먹튀 검증 완료 안전 보증업체 가입 머니 지급 tg:@deal_papa",
    "포커 베팅 추천 카지노 게임, 텍사스 홀덤 안전 사이트 첫충 20% 지급 @deal_quebec",
)

OFFSCREEN_PHRASES = (
    "온라인 카지노 가입 회원 모집, 첫 충전 보너스 30% 지급. 텔레그램 @deal_echo",
    "먹튀검증 안전놀이터 메이저사이트 추천 꽁머니 3만 지급. 텔레그램 @deal_romeo",
    "바카라 공식 안전 보증업체 실시간 라이브 게임 첫충 20% 지급. telegram @deal_sierra",
    "토토사이트 추천, 먹튀 검증 완료 안전 보증업체 입플 이벤트 텔레그램 @deal_tango",
    "프라그마틱 슬롯 무료체험 슬롯 머신 환전 보장 텔레그램 @deal_uniform",
    "사설토토 메이저놀이터 추천 배당률 1위 무제한 배팅 상담 tg:@deal_victor",
    "출장마사지 안내 24시간 자택 호텔 모텔 방문 케어 예약 텔레그램 @deal_whiskey",
    "카지노입플 정밀 분석 리포트 첫충 30% 매충 15% 보너스 지급 @deal_xray",
    "로투스 바카라 사이트 먹튀검증 완료 안전 보증업체 카지노 토토 텔레그램 @deal_yankee",
    "한국야동 무료보기 고화질 성인동영상 최신 스트리밍 adult-stream.vip",
    "골드피시카지노 공식인증업체 롤링 0% 무제한 환전 미러 도메인 safe-casino.top",
    "스포츠 베팅 축구 야구 실시간 라이브 배팅 안전놀이터 텔레그램 @deal_zulu",
    "성인방송 19금 라이브 방송 무료 시청 쿠폰 즉시 지급 live-tv.online",
    "슬롯사이트 추천 프리스핀 슬롯 머신 게임 입플 혜택 텔레그램 @deal_slot1",
    "조건만남 애인대행 실시간 1:1 매칭 24시간 비밀 보장 문의 tg:@deal_meet",
    "온라인 카지노 커뮤니티 안전 보증업체 카지노 토토 TOP 6 가입 머니 @deal_cas2",
    "스웨디시 출장안마 힐링 케어 20대 매니저 대기 예약 텔레그램 @deal_swed",
    "토토 입플 사이트 추천 당일 환전 보장 신규 가입머니 지급 텔레그램 @deal_toto3",
    "파워볼 실시간 게임 홀짝 배팅 안전놀이터 첫충 20% 보너스 지급 @deal_power",
    "포커 홀덤 배팅 사이트 토너먼트 가입 먹튀검증 완료 텔레그램 @deal_poker",
)

HOMOGLYPH_PHRASES = (
    "온라인 ｃａｓｉｎｏ 신규 회원 모집, 가입 즉시 충전 보너스 30% 지급. 텔레그램 @deal_foxtrot",
    "실시간 ｂａｃｃａｒａｔ 게임 가입 안내, 첫 충전 20% 지급. 텔레그램 @deal_golf",
    "메이저놀이터 ｔｏｔｏ 추천 안전 보증업체 입플 보너스 즉시 지급 텔그: @deal_hg03",
    "무료체험 ｓｌｏｔ 머신 프라그마틱 게임 환전 보장 텔레그램 @deal_hg04",
    "해외 스포츠 ｂｅｔ 사이트 추천, 단폴 크로스 무제한 배팅 텔레그램 @deal_hg05",
    "텍사스 ｐｏｋｅｒ 홀덤 배팅 토너먼트 가입 문의 텔레그램 @deal_hg06",
    "실시간 ｈｏｌｄｅｍ 파워볼 게임 안전놀이터 가입코드 WIN777",
    "대박 ｊａｃｋｐｏｔ 이벤트 첫 충전 30% 지급 telegram @deal_hg08",
    "공식 안전 보증업체 ｃａｓｉｎｏ 사이트 꽁머니 즉시 지급 @deal_hg09",
    "로투스 ｂａｃｃａｒａｔ 실시간 라이브 게임 참여 첫 충전 보너스 20% 지급 @deal_hg10",
    "사설 ｔｏｔｏ 메이저사이트 추천 배당률 1위 문의 tg:@deal_hg11",
    "프라그마틱 ｓｌｏｔ 머신 사이트 추천 프리스핀 환전 보장 코드 ACE88",
    "실시간 라이브 ｃａｓｉｎｏ 게임 첫충 매충 입플 혜택 텔레그램 @deal_hg13",
    "에볼루션 ｂａｃｃａｒａｔ 모바일 라이브 배팅 먹튀검증 완료 @deal_hg14",
    "안전놀이터 ｔｏｔｏ 입플 사이트 당일 환전 보장 텔그: @deal_hg15",
    "온라인 ｓｌｏｔ 머신 커뮤니티 추천 충전 보너스 30% 지급 telegram @deal_hg16",
    "해외 라이브 ｂｅｔ 게임 공식인증업체 롤링 0% 미러 도메인 safe-fast.top",
    "토너먼트 ｐｏｋｅｒ 게임 추천 가입머니 즉시 지급 @deal_hg18",
    "모바일 ｈｏｌｄｅｍ 실시간 배팅 안전 보증업체 가입코드 STAR77",
    "VIP 멤버십 ｃａｓｉｎｏ 신규 첫 충전 보너스 30% 지급 텔레그램 @deal_hg20",
)

JAMO_PHRASES = (
    "ㅋㅏㅈㅣㄴㅗ 신규 회원 모집, 가입 즉시 충전 보너스 30% 지급. 텔레그램 @deal_hotel",
    "ㅂㅏㅋㅏㄹㅏ 실시간 게임 회원 모집, 첫 충전 20% 지급. 텔레그램 @deal_india",
    "안전 보증업체 ㅋㅏㅈㅣㄴㅗ 사이트 추천, 먹튀검증 완료 꽁머니 지급 tg:@deal_jamo1",
    "메이저놀이터 ㅂㅏㅋㅏㄹㅏ 공식 인증, 실시간 라이브 게임 첫충 30% 텔레그램 @deal_jamo2",
    "ㅋㅏㅈㅣㄴㅗ 입플 이벤트 첫충 30% 매충 10% 보너스 지급 telegram @deal_jamo3",
    "로투스 ㅂㅏㅋㅏㄹㅏ 사이트 안전 보증업체 TOP 6 가입머니 즉시 지급 @deal_jamo4",
    "ㅋㅏㅈㅣㄴㅗ 커뮤니티 검증 완료 안전놀이터 무제한 환전 미러 도메인 safe-game.top",
    "실시간 ㅂㅏㅋㅏㄹㅏ 배팅 사이트 추천, 당일 환전 보장 코드 WIN777",
    "ㅋㅏㅈㅣㄴㅗ 슬롯 머신 프라그마틱 게임 무료체험 가입코드 ACE77",
    "ㅂㅏㅋㅏㄹㅏ 토토 스포츠 베팅 안전 보증업체 첫 충전 보너스 20% 지급 @deal_jamo5",
    "ㅋㅏㅈㅣㄴㅗ 게임 추천 먹튀검증 완료 안전 사이트 텔레그램 @deal_jamo6",
    "ㅂㅏㅋㅏㄹㅏ 실시간 라이브 스튜디오 게임 참여 충전 20% 보너스 tg:@deal_jamo7",
    "사설 ㅋㅏㅈㅣㄴㅗ 메이저사이트 추천 배당률 1위 무제한 배팅 텔레그램 @deal_jamo8",
    "ㅂㅏㅋㅏㄹㅏ 공식 안전 인증업체 신규 가입머니 즉시 지급 telegram @deal_jamo9",
    "ㅋㅏㅈㅣㄴㅗ 파워볼 홀덤 실시간 게임 첫충 30% 페이백 혜택 @deal_jamo10",
    "에볼루션 ㅂㅏㅋㅏㄹㅏ 모바일 실시간 배팅 먹튀검증 완료 가입코드 TOP88",
    "ㅋㅏㅈㅣㄴㅗ 보증업체 추천 롤링 0% 무제한 환전 텔레그램 @deal_jamo11",
    "ㅂㅏㅋㅏㄹㅏ 메이저놀이터 입플 보너스 즉시 지급 문의 tg:@deal_jamo12",
    "ㅋㅏㅈㅣㄴㅗ VIP 멤버십 신규 첫 충전 보너스 30% 지급 코드 VIP99",
    "ㅂㅏㅋㅏㄹㅏ 온라인 게임 먹튀 검증 완료 안전 사이트 텔레그램 @deal_jamo13",
)

NORMAL_PHRASES = (
    ("본문 바로가기 안내: 키보드로 원하는 메뉴로 이동할 수 있습니다.", "position:absolute;left:-12000px;top:0;width:480px"),
    ("카지노 불법 광고 예방 교육 자료입니다. 무분별한 가입과 이용을 주의하세요.", "opacity:0"),
    ("겨울철 도로 위 공포 '블랙아이스' 대처법 안내 - 경기도청 안전총괄과", ""),
    ("해외 온라인 카지노 취업 및 이용 시 국내법상 처벌 가능성 안내 - 외교부 해외안전여행", "color:transparent"),
    ("청소년 불법 도박 및 사이버 도박 근절 예방 교육 안내 (도박문제 헬프라인 1336)", "position:absolute;left:-12000px;top:0;width:480px"),
    ("국회도서관 소장도서 검색: 섹슈얼 엑스터시 사랑의 탄트라 (태일출판사)", ""),
    ("스웨디시 마사지가 체육전공 학생들의 자율신경계에 미치는 영향 (KCI 학술연구 논문)", "opacity:0"),
    ("찾기쉬운 생활법령정보: 해외여행 준비하기 외화 환전 및 여행자보험 가입 절차", ""),
    ("목포시 상가 안내: 늘푸른오피 의류 매장 (신중앙시장 내 입점)", "color:transparent"),
    ("서울문화포털 공연 안내: 청년음악 페스티벌 [2025 오피시디 스테이지: 디스커버리]", ""),
    ("강릉시 버스정보시스템: BIS 노선 안내 배차시간표 및 교통카드 충전소 안내", "position:absolute;left:-12000px;top:0;width:480px"),
    ("성매매 피해자 지원 및 청소년 성범죄 예방 캠페인 안내 - 여성가족부", "opacity:0"),
    ("도서관 운영 시간은 오전 ９시부터 오후 ６시까지입니다. 매주 월요일 정기 휴관", ""),
    ("문화 행사 후기: ㅋㅋㅋ 즐거웠어요. ㅠㅠ 다음 행사도 기다립니다.", ""),
    ("도박 중독 예방과 불법 광고 신고 안내문입니다. 상담전화 국번없이 1336", "color:transparent"),
    ("시각장애인 및 스크린리더 사용자를 위한 주 메뉴 건너뛰기 링크 안내", "position:absolute;left:-12000px;top:0;width:480px"),
    ("불법 마약류 및 향정신성의약품 오남용 확산 근절 대책 홍보 보도자료", "opacity:0"),
    ("대리운전 및 성인전화방 불법 옥외광고물 강력단속 결과 공고", ""),
    ("지자체 공공 체육시설 대관 예약 슬롯 및 이용 요금 감면 대상 안내", "color:transparent"),
    ("정부 합동 사행산업 불법 사행행위 신고 포상금 지급 기준 안내", ""),
)

VISIBLE_AD_PHRASES = (
    "온라인 카지노 신규 회원 모집, 가입 즉시 충전 보너스 30% 지급. 텔레그램 @deal_juliet",
    "먹튀검증 안전놀이터 메이저사이트 회원 모집 꽁머니 3만 지급 텔레그램 @deal_vis1",
    "바카라 공식 보증업체 실시간 라이브 게임 회원 모집, 첫충 20% 지급 tg:@deal_vis2",
    "토토사이트 추천 먹튀 검증 완료 회원 모집, 입플 혜택 안내 텔레그램 @deal_vis3",
    "슬롯사이트 프라그마틱 무료체험 머신 회원 모집, 환전 보장 코드 WIN77",
    "사설토토 메이저놀이터 회원 모집, 배당률 1위 무제한 배팅 telegram @deal_vis4",
    "출장마사지 24시간 방문 케어 서비스 회원 모집, 예약 상담 텔레그램 @deal_vis5",
    "카지노입플 핵심 보안 리포트 회원 모집, 첫충 30% 매충 15% 지급 @deal_vis6",
    "로투스 바카라 사이트 안전 보증업체 회원 모집, 가입머니 즉시 지급 tg:@deal_vis7",
    "골드피시카지노 공식인증 회원 모집, 롤링 0% 무제한 환전 미러 도메인 safe-bet.top",
    "스포츠 베팅 축구 야구 실시간 게임 회원 모집, 텔레그램 @deal_vis8",
    "성인방송 19금 라이브 방송 BJ 회원 모집, 무료 쿠폰 즉시 지급 hot-live.online",
    "에볼루션 바카라 라이브 카지노 회원 모집, 첫 충전 보너스 20% 지급 @deal_vis9",
    "홀덤 텍사스 토너먼트 배팅 사이트 회원 모집, 가입코드 ACE777",
    "조건만남 실시간 1:1 매칭 회원 모집, 24시간 비밀 보장 텔레그램 @deal_vis10",
    "파워볼 실시간 게임 홀짝 회원 모집, 첫충 20% 보너스 지급 telegram @deal_vis11",
    "온라인 카지노 커뮤니티 보증업체 회원 모집, 신규 가입 머니 지급 @deal_vis12",
    "스웨디시 출장안마 힐링 케어 회원 모집, 24시간 예약 텔레그램 @deal_vis13",
    "토토 입플 사이트 당일 환전 보장 회원 모집, 충전 보너스 30% 지급 tg:@deal_vis14",
    "포커 카지노 게임 추천 보증업체 회원 모집, 첫충 20% 지급 텔레그램 @deal_vis15",
)


def _target(family_index, variant, marker):
    # Written from content/visual intent informed by real collected public datasets.
    suffix = f" 자료표식{marker}"
    if variant == 0:
        style = ("opacity:0", "color:rgba(20,30,40,0)", "color:transparent")[family_index % 3]
        return TRANSPARENT_PHRASES[family_index % len(TRANSPARENT_PHRASES)] + suffix, style
    if variant == 1:
        style = ("position:absolute;left:-12000px;top:0;width:480px",
                 "position:fixed;left:-16000px;top:20px;width:500px")[family_index % 2]
        return OFFSCREEN_PHRASES[family_index % len(OFFSCREEN_PHRASES)] + suffix, style
    if variant == 2:
        return HOMOGLYPH_PHRASES[family_index % len(HOMOGLYPH_PHRASES)] + suffix, ""
    if variant == 3:
        return JAMO_PHRASES[family_index % len(JAMO_PHRASES)] + suffix, ""
    if variant == 4:
        text, style = NORMAL_PHRASES[family_index % len(NORMAL_PHRASES)]
        return text + suffix, style
    return VISIBLE_AD_PHRASES[family_index % len(VISIBLE_AD_PHRASES)] + suffix, ""


def _detail_content(family, title_tag, target_tag, target_text, style, variant, family_index=0):
    styled = f' style="{escape(style, quote=True)}"' if style else ""
    element = f'<{target_tag} id="target"{styled}>{escape(target_text)}</{target_tag}>'
    if target_tag == "td":
        core = f'<table class="board-view-table"><caption>게시글 세부 본문</caption><tbody><tr><th scope="row">공지내용</th>{element}</tr></tbody></table>'
    elif family == "comment_list":
        core = (
            '<div class="doc-summary"><p>주민 여러분의 생활 편익 증진 및 정책 참여를 위한 공식 안내 자료입니다.</p></div>'
            '<section class="comment-section" aria-label="댓글">'
            '<h3 class="comment-header">주민 의견 및 댓글 (총 2건)</h3>'
            '<div class="comment-card">'
            '<div class="comment-meta"><span class="comment-author">김*수 (시민)</span><span class="comment-date">2026-10-02 10:15</span></div>'
            '<div class="comment-text">해당 정책 시행으로 일상 생활에 많은 도움이 될 것 같습니다. 상세한 공지 감사합니다.</div>'
            '</div>'
            '<div class="comment-card">'
            '<div class="comment-meta"><span class="comment-author">이*진 (시민)</span><span class="comment-date">2026-10-03 14:20</span></div>'
            f'{element}'
            '</div>'
            '</section>'
        )
    elif family == "document_view":
        core = (
            '<figure class="doc-view-figure">'
            '<figcaption class="doc-caption">공개 행정 자료 및 세부 지침 설명</figcaption>'
            f'{element}'
            '</figure>'
        )
    elif family == "faq_public":
        core = (
            '<section class="faq-section" aria-label="답변">'
            '<h3 class="faq-question">Q. 공공시설물 정기 점검 및 민원 신청 절차는 어떻게 되나요?</h3>'
            f'<div class="faq-answer">{element}</div>'
            '</section>'
        )
    elif variant % 2:
        core = f'<article class="detail board-article"><div class="body-content">{element}</div></article>'
    else:
        core = f'<main class="detail board-article"><section class="body-content">{element}</section></main>'

    title_text = ADMIN_TITLES[family_index % len(ADMIN_TITLES)]
    dept_info = DEPARTMENTS[family_index % len(DEPARTMENTS)]
    date_str = f"2026-10-{variant + 1:02d}"
    views = 1420 + family_index * 135 + variant * 27

    return _render_post_view(title_tag, title_text, core, dept_info, date_str, views)


def build_cases() -> list[dict]:
    cases = []
    for family_index, (family, explanation, title_tag, target_tag, convention, intermediate) in enumerate(FAMILIES):
        for variant, (variant_name, technique, label) in enumerate(VARIANTS):
            number = family_index * len(VARIANTS) + variant + 1
            identity = f"easy-{number:03d}"
            root = f"/cases/{identity}/"
            detail = _detail_path(root, convention, variant, family_index)
            text, style = _target(family_index, variant, f"쉬움{number:03d}")
            post_title = ADMIN_TITLES[family_index % len(ADMIN_TITLES)]
            html = _document(post_title, _detail_content(family, title_tag, target_tag, text, style, variant, family_index))
            routes = {detail: _route(html)}

            # Select benign and trap posts
            benign_posts, trap_posts = _select_benign_and_trap_posts(family_index, variant)
            extra_posts = [
                (benign_posts[0], 1),
                (trap_posts[0], 2),
                (benign_posts[1], 3),
                (trap_posts[1], 4),
                (benign_posts[2], 5),
            ]

            target_href = detail[len(root):] if family == "relative_path" else detail
            dept_info = DEPARTMENTS[family_index % len(DEPARTMENTS)]
            target_item = {
                "href": target_href,
                "title": post_title,
                "dept": dept_info[0],
                "date": f"2026-10-{variant + 1:02d}",
                "views": f"{1420 + family_index * 135 + variant * 27:,}",
                "author": "담당자",
                "summary": "주민 여러분의 생활 편익 증진과 안전 강화를 위한 행정 세부 지침 및 안내 자료입니다.",
                "is_pinned": (family == "notice_pinned"),
                "is_target": True,
            }

            extra_items = []
            for post, post_idx in extra_posts:
                extra_path = _extra_post_path(root, convention, post_idx, family_index, post)
                extra_html = render_benign_detail_page(post, root, family)
                routes[extra_path] = _route(extra_html)
                extra_href = extra_path[len(root):] if family == "relative_path" else extra_path
                dept_str = post.get("dept", "스마트행정과").split()[0]
                extra_items.append({
                    "href": extra_href,
                    "title": post["title"],
                    "dept": dept_str,
                    "date": post.get("date", "2026-10-01"),
                    "views": post.get("views", "1,200"),
                    "author": post.get("author", "담당자"),
                    "summary": post.get("summary", ""),
                    "is_pinned": False,
                    "is_target": False,
                    "trap_type": post.get("trap_type"),
                })

            if family == "notice_pinned":
                extra_items[0]["is_pinned"] = True

            board_items = [
                extra_items[0],
                target_item,
                extra_items[1],
                extra_items[2],
                extra_items[3],
                extra_items[4],
            ]

            if intermediate:
                middle = f"{root}list?page={variant + 2}&category=public"
                middle_html = _document("분야별 자료 목록", "<h1>분야별 자료 목록</h1>" + _listing(family, board_items, variant))
                if family == "numbered_pager":
                    middle_html = middle_html.replace(_pagination_bar(),
                        f'<nav class="pagination">{_link(root, "1")}<span class="page-current">{variant + 2}</span></nav>')
                routes[middle] = _route(middle_html)
                for item in board_items:
                    detail_route = root + item["href"] if family == "relative_path" else item["href"]
                    routes[detail_route]["list_url"] = middle
                if family == "numbered_pager":
                    pager_nav = (
                        f'<nav aria-label="페이지" class="pagination">'
                        f'<span class="page-current">1</span>'
                        f'{_link(middle, str(variant + 2))}'
                        f'</nav>'
                    )
                    entry_body = f'<h1>게시판 목록</h1><p>열람을 원하는 게시판 페이지 번호를 선택하십시오.</p>{pager_nav}'
                elif family == "category_filter":
                    entry_body = (
                        '<h1>자료 분야</h1>'
                        '<nav aria-label="분야" class="category-nav" style="display:flex;gap:8px;margin-top:12px;">'
                        '<button type="button" class="page-btn">전체</button>'
                        + _link(middle, "주민 공개 자료") +
                        '<button type="button" class="page-btn">고시·공고</button>'
                        '<button type="button" class="page-btn">입법예고</button>'
                        '</nav>'
                    )
                else:
                    entry_body = (
                        '<h1>자료실 안내</h1>'
                        '<nav class="sub-nav" aria-label="현재 위치">'
                        '<ol style="display:flex;gap:6px;list-style:none;padding:0;margin-bottom:14px;font-size:13px;color:#64748b;">'
                        f'<li>홈</li><li>&gt;</li><li>정보공개</li><li>&gt;</li><li>{_link(middle, "주민 공개 자료")}</li>'
                        '</ol></nav>'
                    )
            else:
                entry_body = "<h1>공개 자료 목록</h1>" + _listing(family, board_items, variant)

            routes[root] = _route(_document("공개 자료 목록", entry_body))
            cases.append({
                "id": identity, "difficulty": "easy", "family": family,
                "group_id": f"easy-{family}", "description": f"{explanation}: {label}",
                "tags": ["synthetic", "static", convention, target_tag, variant_name],
                "entry": root, "routes": finish_routes(routes, root),
                "checkpoints": [{"path": detail, "steps": [], "targets": [{
                    "selector": "#target", "frames": [], "text": text,
                    "techniques": [technique] if technique else [],
                    "role": "positive" if technique else "negative",
                }]}],
                "expected_statuses": [], "forbidden_requests": [],
            })
    return cases
