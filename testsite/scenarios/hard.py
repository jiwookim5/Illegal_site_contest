"""Authored local UI stress fixtures; labels never consult the detector or rules.

Five distinct content/concealment conditions per family exercise both collection
and negative controls. These synthetic fixtures are not an independent real-site
accuracy benchmark. Known limitations retain their authored expected observations.
"""
from __future__ import annotations

from html import escape
import json
from testsite.scenarios.ui import finish_routes

from testsite.scenarios.benign_pool import (
    BENIGN_PUBLIC_POSTS,
    FALSE_POSITIVE_TRAPS,
    render_benign_detail_page,
)

FAMILIES = (
    "composite-two", "composite-many", "negative-obfuscation", "inherited-transparency",
    "repeated-structure", "nested-frames", "same-source-frames", "frame-replacement",
    "same-url-replacement", "async-html-comments", "async-json-comments", "delegated-listener",
    "window-scroll", "container-scroll", "finite-pagination", "get-hidden-form",
    "blocked-post", "blocked-delete", "http-404", "http-500", "retry-429", "retry-503",
    "dialog-transition", "dynamic-tabs",
)
VARIANTS = ("jamo-offscreen", "homoglyph-transparent", "two-styles", "prevention", "visible-ad")
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
    "스마트 그늘막 및 폭염 저감시설 추가 설치 장소 안내",
    "노인 맞춤 돌봄서비스 신청 자격 및 집중 접수기간 안내",
    "친환경 전기차 충전시설 의무 설치 구역 및 이용 에티켓",
    "안전신문고 생활불편 신고 창구 및 포상금 지급 기준 공표",
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
    ("도로관리과", "도로시설팀", "02-120 (내선 121)"),
    ("어르신복지과", "노인돌봄팀", "02-120 (내선 122)"),
    ("녹색도시과", "친환경차량팀", "02-120 (내선 123)"),
    ("감사담당관", "안전감찰팀", "02-120 (내선 124)"),
)

EGOV_CSS = (
    "* { box-sizing: border-box; }"
    "body { margin: 0; padding: 0; background: #f4f6f9; color: #222; font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', '맑은 고딕', helvetica, sans-serif; font-size: 15px; line-height: 1.6; min-height: 320px; }"
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
    ".comment-meta { font-size: 12px; color: #64748b; margin-bottom: 4px; display: flex; gap: 12px; align-items: center; }"
    ".comment-author { font-weight: 600; color: #334155; }"
    ".comment-date { color: #94a3b8; font-size: 12px; }"
    ".comment-body { font-size: 14px; color: #334155; line-height: 1.6; margin-top: 4px; }"
    ".btn-area { display: flex; justify-content: center; gap: 8px; margin-top: 24px; padding-top: 18px; border-top: 1px solid #e2e8f0; }"
    ".btn { padding: 8px 18px; font-size: 14px; font-weight: 500; border-radius: 4px; border: 1px solid #cbd5e1; background: #fff; color: #334155; cursor: pointer; text-decoration: none; }"
    ".btn-primary { background: #1a3c6e; color: #fff; border-color: #1a3c6e; }"
    ".board-list-wrap { background: #fff; padding: 24px; border: 1px solid #d9e2ec; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 24px; }"
    ".board-search-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; font-size: 13px; }"
    ".board-total strong { color: #1a3c6e; font-weight: 700; }"
    ".search-form { display: flex; gap: 6px; }"
    ".input-search { padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 3px; font-size: 13px; outline: none; }"
    ".btn-search { padding: 6px 14px; background: #1a3c6e; color: #fff; border: 1px solid #1a3c6e; border-radius: 3px; cursor: pointer; font-size: 13px; }"
    "table.board-list { width: 100%; border-collapse: collapse; margin-top: 8px; background: #fff; border-top: 2px solid #1a3c6e; }"
    "table.board-list th { background: #f8fafc; padding: 11px 8px; border-bottom: 1px solid #cbd5e1; font-weight: 600; font-size: 13px; color: #334155; }"
    "table.board-list td { padding: 10px 8px; border-bottom: 1px solid #e2e8f0; text-align: center; font-size: 13px; color: #475569; }"
    "table.board-list td.title-col { text-align: left; }"
    "table.board-list td.title-col a { color: #1e293b; text-decoration: none; font-weight: 500; }"
    "table.board-list td.title-col a:hover { text-decoration: underline; color: #1a3c6e; }"
    ".badge-pinned { background: #fee2e2; color: #b91c1c; font-weight: 600; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }"
    ".badge-trap { background: #fef3c7; color: #92400e; font-weight: 600; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }"
    ".badge-normal { background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }"
    ".pagination { display: flex; justify-content: center; gap: 4px; margin-top: 20px; align-items: center; }"
    ".page-current { display: inline-block; padding: 5px 12px; background: #1a3c6e; color: #fff; border-radius: 3px; font-size: 13px; font-weight: bold; }"
    ".page-link { display: inline-block; padding: 5px 12px; border: 1px solid #cbd5e1; background: #fff; color: #475569; border-radius: 3px; font-size: 13px; cursor: pointer; text-decoration: none; }"
    ".page-link:hover { background: #f1f5f9; border-color: #94a3b8; }"
    ".cards-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); margin: 16px 0; }"
    ".card { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); transition: border-color .15s; }"
    ".card:hover { border-color: #1a3c6e; }"
    ".card-title { font-size: 15px; font-weight: 700; color: #1e293b; margin: 0 0 8px 0; line-height: 1.4; }"
    ".card-desc { font-size: 13px; color: #64748b; line-height: 1.6; margin: 0 0 12px 0; }"
    ".card-meta { font-size: 12px; color: #94a3b8; display: flex; justify-content: space-between; border-top: 1px dashed #e2e8f0; padding-top: 8px; }"
    ".related-posts-box { margin-top: 36px; padding-top: 24px; border-top: 1px solid #cbd5e1; }"
    ".related-posts-title { font-size: 16px; font-weight: 700; color: #1e293b; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }"
    ".gov-tabs { display: flex; gap: 4px; border-bottom: 2px solid #1a3c6e; margin-bottom: 20px; }"
    ".tab-btn { padding: 9px 20px; font-size: 14px; font-weight: 600; border: 1px solid #cbd5e1; border-bottom: none; background: #f8fafc; color: #475569; cursor: pointer; border-radius: 4px 4px 0 0; }"
    ".tab-btn[aria-selected='true'] { background: #1a3c6e; color: #fff; border-color: #1a3c6e; }"
    ".tab-panel { padding: 8px 0; }"
    ".info-callout { background: #f0f7ff; border-left: 4px solid #1a3c6e; padding: 14px 18px; margin: 16px 0; border-radius: 0 4px 4px 0; font-size: 14px; line-height: 1.7; color: #1e293b; }"
    ".info-callout-alert { background: #fff5f5; border-left-color: #dc2626; color: #7f1d1d; }"
    ".info-callout-warning { background: #fffbeb; border-left-color: #d97706; color: #78350f; }"
    "iframe { width: 100%; max-width: 600px; height: 200px; border: 1px solid #cbd5e1; border-radius: 4px; }"
    "#target { font-size: 15px; }"
)

DEFAULT_COMMENTS = [
    {
        "author": "김*호", "date": "2026-10-02", "tag": "시민의견",
        "content": "공공 안내문 세부 지침을 상세히 공유해 주셔서 감사합니다. 관내 주민센터에서도 동일 서식으로 신청 가능한가요?",
    },
    {
        "author": "박*정", "date": "2026-10-04", "tag": "예방홍보",
        "content": "최근 청소년 대상 사설 불법 도박과 사이버 토토 유혹이 심각하던데 도박문제 헬프라인 1336 번호도 함께 안내되어 유익하네요.",
    },
    {
        "author": "이*우", "date": "2026-10-06", "tag": "제도개선",
        "content": "모바일 신분증과 정부24 전자문서지갑으로 온라인 신청 시 제출 서류가 간소화되어 편리합니다.",
    },
    {
        "author": "정*선", "date": "2026-10-08", "tag": "사기주의",
        "content": "서민금융진흥원 사칭하는 작업대출 문자가 많이 오는데 절대 속지 마시고 1332로 신고하시기 바랍니다.",
    },
    {
        "author": "최*영", "date": "2026-10-10", "tag": "시스템점검",
        "content": "서버실 메인프레임 고속 PCIe 슬롯 증설 작업으로 서비스 응답 속도가 확실히 빨라졌네요.",
    },
    {
        "author": "윤*아", "date": "2026-10-12", "tag": "문화행사",
        "content": "구립 도서관 『창가의 토토』 독후감 대회 아이와 함께 읽고 꼭 참여하겠습니다.",
    },
    {
        "author": "홍*표", "date": "2026-10-14", "tag": "웹접근성",
        "content": "스크린리더 이용자를 위한 본문 바로가기 건너뛰기 링크 품질인증 갱신 소식 반갑습니다.",
    },
]


def _render_comments_list_html(comments=None):
    if comments is None:
        comments = DEFAULT_COMMENTS
    cards = []
    for c in comments:
        tag_badge = f'<span class="badge-normal">{escape(c.get("tag", "시민의견"))}</span>'
        cards.append(
            f'<div class="comment-card">'
            f'<div class="comment-meta">'
            f'<span class="comment-author">{escape(c["author"])}</span>'
            f'<span class="comment-date">{escape(c["date"])}</span>'
            f'{tag_badge}'
            f'</div>'
            f'<div class="comment-body">{escape(c["content"])}</div>'
            f'</div>'
        )
    return ''.join(cards)


def _make_board_table_rows(items, root, start_no=1, target_row_index=None, target_html=None, target_title=None, dept_info=None, date_str=None, views=None):
    rows = []
    for idx, item in enumerate(items):
        if target_row_index is not None and idx == target_row_index and target_html:
            dname = dept_info[0] if dept_info else "열린민원과"
            dstr = date_str or "2026-10-15"
            vcount = f"{views:,}" if views else "1,890"
            ttitle = target_title or "2026년 하반기 공공시설물 정기 안전점검 및 주민 협조 안내"
            rows.append(
                f'<tr>'
                f'<td>{start_no - idx}</td>'
                f'<td class="title-col">'
                f'<span class="badge-normal">안내</span> '
                f'<a href="javascript:void(0)">{escape(ttitle)}</a>'
                f'{target_html}'
                f'</td>'
                f'<td>{escape(dname)}</td>'
                f'<td>{escape(dstr)}</td>'
                f'<td>{escape(vcount)}</td>'
                f'</tr>'
            )
        no = start_no - (idx if (target_row_index is None or idx < target_row_index) else idx + 1)
        p_id = item["id"]
        title = item["title"]
        dept = item.get("dept", "스마트행정과")
        date = item.get("date", "2026-10-01")
        v = str(item.get("views", "1,200"))
        trap_type = item.get("trap_type")
        if trap_type == "prevention":
            badge = '<span class="badge-trap">[공공예방]</span> '
        elif trap_type == "homonym":
            badge = '<span class="badge-normal">[교양문화]</span> '
        elif trap_type == "accessibility":
            badge = '<span class="badge-normal">[웹표준]</span> '
        elif item.get("pinned"):
            badge = '<span class="badge-pinned">[필독]</span> '
        else:
            badge = '<span class="badge-normal">공지</span> '
        link = f'{root}post/{p_id}'
        rows.append(
            f'<tr>'
            f'<td>{no}</td>'
            f'<td class="title-col">{badge}<a href="{link}">{escape(title)}</a></td>'
            f'<td>{escape(dept)}</td>'
            f'<td>{escape(date)}</td>'
            f'<td>{escape(v)}</td>'
            f'</tr>'
        )
    return ''.join(rows)


def _render_board_list_view(rows_html, pagination_html, page_num=1, total_pages=3, total_count=24):
    return (
        f'<div class="board-list-wrap">'
        f'<div class="board-search-bar">'
        f'<div class="board-total">총 <strong>{total_count}</strong>건 ({page_num}/{total_pages} 페이지)</div>'
        f'<div class="search-form">'
        f'<input type="text" class="input-search" placeholder="공지 및 민원 검색" readonly value="">'
        f'<button type="button" class="btn-search">검색</button>'
        f'</div>'
        f'</div>'
        f'<table class="board-list" summary="스마트행정안전포털 공지사항 목록">'
        f'<thead><tr>'
        f'<th style="width:8%">번호</th>'
        f'<th style="width:52%">제목</th>'
        f'<th style="width:16%">담당부서</th>'
        f'<th style="width:14%">작성일</th>'
        f'<th style="width:10%">조회수</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'{pagination_html}'
        f'</div>'
    )


def _render_related_posts_section(posts, root):
    rows = []
    for p in posts[:5]:
        p_id = p["id"]
        title = p["title"]
        dept = p.get("dept", "스마트행정과")
        date = p.get("date", "2026-10-01")
        trap_type = p.get("trap_type")
        tag = "[공공예방]" if trap_type == "prevention" else ("[교양문화]" if trap_type == "homonym" else "일반공지")
        badge_cls = "badge-trap" if trap_type == "prevention" else "badge-normal"
        link = f'{root}post/{p_id}'
        rows.append(
            f'<tr>'
            f'<td><span class="{badge_cls}">{tag}</span></td>'
            f'<td class="title-col"><a href="{link}">{escape(title)}</a></td>'
            f'<td>{escape(dept)}</td>'
            f'<td>{escape(date)}</td>'
            f'</tr>'
        )
    return (
        f'<section class="related-posts-box" aria-label="관련 공지사항">'
        f'<h3 class="related-posts-title">관련 행정 공지 및 최신 소식</h3>'
        f'<table class="board-list" summary="관련 공지 목록">'
        f'<thead><tr>'
        f'<th style="width:14%">구분</th>'
        f'<th style="width:50%">제목</th>'
        f'<th style="width:20%">담당부서</th>'
        f'<th style="width:16%">작성일</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>'
        f'</section>'
    )


def _render_window_scroll_content(target_slot):
    return (
        '<div class="gov-scroll-document" style="min-height:2200px">'
        '<div class="info-callout">'
        '<strong>[행정안전부 종합 지침]</strong> 본 지침은 대한민국 전자정부 표준 프레임워크 및 행정절차법에 따라 주민 여러분의 생활 안전과 편익 증진을 위해 공표된 종합 안내문입니다.'
        '</div>'
        '<section style="margin:24px 0">'
        '<h3 style="font-size:18px;color:#1a3c6e;border-left:4px solid #1a3c6e;padding-left:10px;margin-bottom:12px">제1장 총칙 및 기본 방침</h3>'
        '<p style="line-height:1.8;color:#334155">지방자치단체 및 산하기관은 공공시설물의 주기적 점검과 쾌적한 도시환경 조성을 위해 상시 대응 체계를 유지해야 합니다. 주민 여러분께서는 시설물 파손이나 생활 불편 사항 발견 시 즉시 안전신문고 또는 관할 주민센터로 신고해 주시기 바랍니다.</p>'
        '<p style="line-height:1.8;color:#334155">특히 동절기 취약계층 보호를 위해 에너지 바우처 지급 및 한파 쉼터 운영이 집중 실시되며, 현장 점검반을 편성하여 안전 취약 구역을 집중 순찰합니다.</p>'
        '</section>'
        '<section style="margin:24px 0">'
        '<h3 style="font-size:18px;color:#1a3c6e;border-left:4px solid #1a3c6e;padding-left:10px;margin-bottom:12px">제2장 세부 시설별 안전관리 기준</h3>'
        '<table class="board-meta-table" style="margin:12px 0">'
        '<thead><tr><th>시설 구분</th><th>점검 주기</th><th>담당 부서</th><th>주요 점검 항목</th></tr></thead>'
        '<tbody>'
        '<tr><td>공공 체육시설</td><td>매월 1회</td><td>체육진흥과</td><td>소방·전기 설비 및 안전 난간</td></tr>'
        '<tr><td>어린이 놀이시설</td><td>매주 1회</td><td>생활안전과</td><td>바닥재 완충 상태 및 놀이기구 체결부</td></tr>'
        '<tr><td>보행자 안심귀갓길</td><td>상시 순찰</td><td>도시정비과</td><td>LED 바닥신호등 및 안심 비상벨 작동 여부</td></tr>'
        '<tr><td>공공 도서관</td><td>분기 1회</td><td>교육문화과</td><td>서가 고정 상태 및 비상 탈출로 확보</td></tr>'
        '</tbody></table>'
        '</section>'
        '<div class="info-callout info-callout-alert">'
        '<strong>[특별 공공예방 지침] 청소년 불법 사이버 도박 근절</strong><br>'
        '최근 인터넷 누리집 및 모바일 메신저를 통해 청소년을 유혹하는 온라인 불법 도박(바카라, 사설 스포츠토토, 파워볼 홀덤 등)이 급증하고 있습니다. '
        '이는 명백한 범죄 행위이며, 어려움을 겪고 계신 청소년 및 가족은 <strong>도박문제 헬프라인 (☎ 1336)</strong> 또는 넷라인을 통해 24시간 익명 무료 상담을 받으실 수 있습니다.'
        '</div>'
        '<div class="info-callout info-callout-warning">'
        '<strong>[민생침해 금융사기 주의보] 정책자금 사칭 작업대출 근절</strong><br>'
        '서민금융진흥원이나 지자체 정책자금을 사칭하여 "무직자 서류 위조 대출 승인", "작업대출 수수료 선입금"을 요구하거나 "통장 대여 시 월 300만원 지급"을 약속하는 행위는 100% 금융 사기입니다. '
        '불법 스팸 문자나 대포통장 요구는 경찰청(☎ 112) 또는 금융감독원(☎ 1332)으로 즉시 신고바랍니다.'
        '</div>'
        '<div class="info-callout">'
        '<strong>[전산 시스템 점검 안내] 메인프레임 PCIe 슬롯 확장</strong><br>'
        '행정정보시스템의 클라우드 대역폭 확장 및 패킷 처리 최적화를 위해 메인프레임 PCIe 확장 슬롯 카드 증설 작업이 실시됩니다. '
        '작업 시간 동안 일시적인 민원 열람 지연이 발생할 수 있으니 주민 여러분의 너른 양해를 부탁드립니다.'
        '</div>'
        '<section style="margin:24px 0">'
        '<h3 style="font-size:18px;color:#1a3c6e;border-left:4px solid #1a3c6e;padding-left:10px;margin-bottom:12px">자주 묻는 질문 (FAQ)</h3>'
        '<div style="background:#f8fafc;padding:12px 16px;border:1px solid #e2e8f0;border-radius:4px;margin-bottom:8px"><strong>Q. 등초본 온라인 무료 발급은 어디서 신청하나요?</strong><br>A. 정부24 누리집 및 무인민원발급기에서 본인 확인 후 즉시 무료 발급 가능합니다.</div>'
        '<div style="background:#f8fafc;padding:12px 16px;border:1px solid #e2e8f0;border-radius:4px;margin-bottom:8px"><strong>Q. 어린이보호구역 안심 승하차존 이용 시간은 어떻게 되나요?</strong><br>A. 등하교 시간대(08:00~09:00, 13:00~15:00)에 한하여 5분 이내 정차가 허용됩니다.</div>'
        '<div style="background:#f8fafc;padding:12px 16px;border:1px solid #e2e8f0;border-radius:4px;margin-bottom:8px"><strong>Q. 투명 페트병 라벨은 어떻게 배출해야 하나요?</strong><br>A. 내용물을 깨끗이 비우고 라벨을 완전히 떼어낸 후 압착하여 전용 봉투에 배출해 주시기 바랍니다.</div>'
        '</section>'
        '<section class="comment-section" style="margin-top:36px">'
        '<h3 class="comment-header">주민 참여 의견 및 질의응답 (총 7건)</h3>'
        f'{_render_comments_list_html()}'
        '</section>'
        '<div style="padding:16px;background:#f1f5f9;border-radius:4px;text-align:center;color:#64748b;margin-top:24px">'
        '아래로 스크롤하여 추가 행정 고시 및 확인 사항을 확인하세요.'
        '</div>'
        f'{target_slot}'
        '</div>'
    )


def _render_container_scroll_content(target_slot):
    extended_comments = DEFAULT_COMMENTS + [
        {
            "author": "강*우", "date": "2026-10-15", "tag": "자원순환",
            "content": "투명 페트병 분리배출 요일제가 동네에 잘 정착되고 있어서 깨끗해졌습니다. 수거함도 더 늘려주세요.",
        },
        {
            "author": "오*철", "date": "2026-10-16", "tag": "의약안전",
            "content": "인터넷으로 판매되는 가짜 비아그라나 발기부전약은 심혈관계 위험이 크다고 하니 정품 약국 처방만 받읍시다.",
        },
        {
            "author": "배*규", "date": "2026-10-17", "tag": "정보자원",
            "content": "메인프레임 고속 PCIe 슬롯 교체 작업 후 전자정부 증명서 발급 렉이 말끔히 사라졌네요. 고생 많으셨습니다.",
        },
    ]
    comments_html = _render_comments_list_html(extended_comments)
    return (
        f'<div id="scrollbox" style="height:220px;overflow-y:scroll;border:1px solid #cbd5e1;padding:14px;background:#fff;border-radius:4px">'
        f'<div style="font-weight:700;font-size:14px;color:#1e293b;margin-bottom:12px;border-bottom:2px solid #1a3c6e;padding-bottom:6px">'
        f'시민 참여 의견 및 정책 피드백 (총 10건 - 스크롤하여 전체 열람)'
        f'</div>'
        f'<div style="padding-bottom:12px">{comments_html}</div>'
        f'{target_slot}'
        f'</div>'
    )


def _render_post_view(title_tag, title_text, target_content, dept_info, date_str, views, related_posts_html=""):
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
        f'<button type="button" class="btn-file-action">미리보기</button>'
        f'<button type="button" class="btn-file-action">다운로드</button>'
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
        f'{related_posts_html}'
        f'<footer class="btn-area">'
        f'<button type="button" class="btn btn-primary">목록</button>'
        f'<button type="button" class="btn">인쇄</button>'
        f'<button type="button" class="btn">공유</button>'
        f'</footer>'
        f'</article>'
    )


def _async_comments_script(response, *, json_response=False):
    read = ("const data=await response.json(); if(typeof data.html!=='string')throw new Error('invalid comments'); const html=data.html;"
            if json_response else "const text=await response.text(); const html=new DOMParser().parseFromString(text,'text/html').body.innerHTML;")
    return (
        "document.querySelector('#more').onclick=async function(){"
        "if(this.disabled)return;this.disabled=true;const slot=document.querySelector('#slot');"
        "slot.setAttribute('aria-busy','true');try{"
        f"const response=await fetch({json.dumps(response)});"
        "if(!response.ok)throw new Error('HTTP '+response.status);"
        + read + "await new Promise(resolve=>setTimeout(resolve,120));slot.innerHTML=html;"
        "}catch(error){slot.textContent='댓글을 불러오지 못했습니다. 다시 시도해 주세요.';"
        "slot.setAttribute('role','status');}finally{slot.setAttribute('aria-busy','false');this.disabled=false;}};"
    )


def _page(body, script="", *, title="상급 합성 게시판"):
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<title>{escape(title)} - 스마트행정안전포털</title>'
            f'<style>{EGOV_CSS}</style>'
            '</head><body>'
            '<header class="gov-top-banner">'
            '<div class="gov-badge">대한민국 공식 전자정부 포털</div>'
            '<div class="gov-util"><span class="gov-util-item">공식 인증 서비스</span><span class="gov-util-item">보안 접속 중</span></div>'
            '</header>'
            '<header class="gov-header">'
            '<div class="gov-header-inner">'
            '<div class="gov-logo">🏛️ 스마트행정안전포털</div>'
            '<div class="gov-gnb"><span>정보공개</span><span>민원서비스</span><span>참여소통</span><span>기관소개</span></div>'
            '</div>'
            '</header>'
            '<main class="gov-container">'
            '<nav class="gov-breadcrumb" aria-label="현재 위치">'
            '<span class="bc-home">홈</span><span class="sep">&gt;</span>'
            '<span>정보공개</span><span class="sep">&gt;</span>'
            '<span>사전정보공표</span><span class="sep">&gt;</span>'
            '<span class="current">공지사항</span>'
            '</nav>'
            f'{body}'
            '</main>'
            + ('<script>' + script + '</script>' if script else '') + '</body></html>')


def _route(body, status=200, **extra):
    return {"body": body, "status": status, "content_type": "text/html; charset=utf-8", **extra}


def _click(selector, frames=None):
    return {"action": "click", "selector": selector, "frames": frames or []}


def _wait(ms=300):
    return {"action": "wait", "ms": ms}


def _case(number, family, variant):
    identity = f"hard-{number:03d}"
    root = f"/cases/{identity}/"
    mark = f"[HARD_{number:03d}]"
# Real-world inspired phrase pools from google_dataset_20260930
JAMO_OFFSCREEN_POOL = (
    "ㅂㅏㅋㅏㄹㅏ 실시간 배팅 회원 모집, 텔레그램 @deal_h01 가입코드 WIN77",
    "ㅋㅏㅈㅣㄴㅗ 실시간 라이브 게임 첫충 30% 지급, 텔레그램 @deal_h02 가입코드 ACE88",
    "안전 보증업체 ㅂㅏㅋㅏㄹㅏ 사이트 추천, 먹튀검증 완료 꽁머니 지급 tg:@deal_h03",
    "메이저놀이터 ㅋㅏㅈㅣㄴㅗ 공식 인증, 충전 보너스 30% 지급 텔레그램 @deal_h04",
    "로투스 ㅂㅏㅋㅏㄹㅏ 사이트 안전 보증업체 TOP 6 가입머니 즉시 지급 @deal_h05",
    "ㅋㅏㅈㅣㄴㅗ 입플 이벤트 첫충 30% 매충 10% 보너스 지급 telegram @deal_h06",
    "실시간 ㅂㅏㅋㅏㄹㅏ 배팅 사이트 추천, 당일 환전 보장 코드 TOP88",
    "사설 ㅋㅏㅈㅣㄴㅗ 메이저사이트 추천 배당률 1위 무제한 배팅 텔레그램 @deal_h08",
    "ㅂㅏㅋㅏㄹㅏ 토토 스포츠 베팅 안전 보증업체 첫 충전 보너스 20% 지급 @deal_h09",
    "ㅋㅏㅈㅣㄴㅗ 슬롯 머신 프라그마틱 게임 무료체험 가입코드 VIP77",
    "ㅂㅏㅋㅏㄹㅏ 공식 안전 인증업체 신규 가입머니 즉시 지급 telegram @deal_h11",
    "ㅋㅏㅈㅣㄴㅗ 보증업체 추천 롤링 0% 무제한 환전 텔레그램 @deal_h12",
    "에볼루션 ㅂㅏㅋㅏㄹㅏ 모바일 실시간 배팅 먹튀검증 완료 가입코드 WIN99",
    "ㅋㅏㅈㅣㄴㅗ 파워볼 홀덤 실시간 게임 첫충 30% 페이백 혜택 @deal_h14",
    "ㅂㅏㅋㅏㄹㅏ 메이저놀이터 입플 보너스 즉시 지급 문의 tg:@deal_h15",
    "ㅋㅏㅈㅣㄴㅗ 커뮤니티 검증 완료 안전놀이터 무제한 환전 @deal_h16",
    "ㅂㅏㅋㅏㄹㅏ 실시간 라이브 스튜디오 게임 참여 충전 20% 보너스 telegram @deal_h17",
    "ㅋㅏㅈㅣㄴㅗ VIP 멤버십 신규 첫 충전 보너스 30% 지급 코드 STAR77",
    "ㅂㅏㅋㅏㄹㅏ 온라인 게임 먹튀 검증 완료 안전 사이트 텔레그램 @deal_h19",
    "ㅋㅏㅈㅣㄴㅗ 라이브 게임 추천 안전 보증업체 첫충 20% 지급 @deal_h20",
    "ㅂㅏㅋㅏㄹㅏ 사설토토 메이저놀이터 무제한 배팅 가입코드 FAST77",
    "ㅋㅏㅈㅣㄴㅗ 입플 사이트 당일 환전 보장 신규 가입머니 지급 tg:@deal_h22",
    "ㅂㅏㅋㅏㄹㅏ 게임 무료체험 실시간 라이브 배팅 코드 LUCKY7",
    "ㅋㅏㅈㅣㄴㅗ 토토 복합 베팅 안전놀이터 첫충 30% 텔레그램 @deal_h24",
)

HOMOGLYPH_TRANSPARENT_POOL = (
    "ｃａｓｉｎｏ 실시간 배팅 회원 모집, 텔레그램 @deal_h01 가입코드 WIN77",
    "ｂａｃｃａｒａｔ 실시간 라이브 게임 먹튀검증 완료, 가입코드 WIN777",
    "ｃａｓｉｎｏ 공식 안전 보증업체 신규 첫충 30% 지급 텔레그램 @deal_h03",
    "ｔｏｔｏ 메이저놀이터 추천 입플 보너스 즉시 지급 텔레그램 @safe_toto",
    "ｓｌｏｔ 무료체험 프라그마틱 게임 환전 보장 텔레그램 @deal_hg04",
    "ｃａｓｉｎｏ 슬롯 머신 프라그마틱 무료체험 가입코드 ACE77",
    "ｂａｃｃａｒａｔ 메이저놀이터 추천 입플 보너스 즉시 지급 tg:@deal_h07",
    "ｐｏｋｅｒ 홀덤 텍사스 배팅 사이트 가입 문의 @holdem_pro",
    "ｃａｓｉｎｏ 커뮤니티 검증 완료 안전놀이터 무제한 환전 safe-fast.top",
    "ｂａｃｃａｒａｔ 로투스 게임 참여 첫충 매충 입플 혜택 telegram @deal_h10",
    "ｃａｓｉｎｏ 입플 정밀 분석 리포트 첫충 30% 매충 15% 보너스 지급",
    "ｔｏｔｏ 안전 보증업체 먹튀 검증 완료 해외 스포츠 베팅 @deal_h12",
    "ｂａｃｃａｒａｔ 에볼루션 실시간 라이브 게임 첫충 20% 보너스 지급",
    "ｓｌｏｔ 사이트 추천 프리스핀 머신 게임 입플 혜택 텔레그램 @deal_h14",
    "ｃａｓｉｎｏ 사설토토 메이저사이트 추천 배당률 1위 무제한 배팅 tg:@deal_h15",
    "ｂａｃｃａｒａｔ 온라인 게임 먹튀검증 완료 안전 사이트 가입코드 VIP88",
    "ｈｏｌｄｅｍ 파워볼 실시간 게임 가입코드 LUCKY7 첫충 20% 보너스",
    "ｃａｓｉｎｏ VIP 멤버십 신규 첫 충전 보너스 30% 지급 텔레그램 @deal_h18",
    "ｂａｃｃａｒａｔ 공식 안전 인증업체 신규 가입머니 즉시 지급 telegram @deal_h19",
    "ｔｏｔｏ 입플 사이트 당일 환전 보장 신규 가입머니 지급 @deal_h20",
    "ｓｌｏｔ 머신 프라그마틱 게임 무료체험 가입코드 TOP88",
    "ｃａｓｉｎｏ 골드피시 공식인증업체 롤링 0% 무제한 환전 safe-play.vip",
    "ｂａｃｃａｒａｔ 실시간 라이브 스튜디오 게임 참여 충전 20% 보너스",
    "ｃａｓｉｎｏ 토토 복합 베팅 안전놀이터 첫충 30% 텔레그램 @deal_h24",
)

TWO_STYLES_POOL = (
    "먹튀검증 | 구글검색 꽁타 먹튀 피하는 법, 안전 보증업체 꽁머니 첫충 30% 지급 텔레그램 @deal_two01",
    "바카라 카지노 회원 모집, 텔레그램 @deal_two02 가입코드 WIN77",
    "메이저-놀이터 : 스포츠 베팅, 실시간 바카라, 파워볼 홀덤 안전 보증업체 가입코드 VIP77",
    "추천하는 토토 사이트, 먹튀 검증 완료, 첫충 매충 입플 혜택 안전 베팅 사이트 tg:@deal_two04",
    "로투스 바카라 사이트 안전 보증업체 카지노 토토 TOP 6 신규 가입머니 즉시 지급 @deal_two05",
    "온라인 슬롯 머신 게임 안전 보증업체 카지노 토토 프라그마틱 무료체험 충전 보너스 30% 지급",
    "카지노입플 2026 핵심 보안 지표 정밀 리포트 첫충 30% 매충 15% 지급 텔레그램 @deal_two07",
    "골드피시카지노 공식인증업체, 롤링 0% 무제한 환전 미러 도메인 safe-bet.top",
    "사설토토 메이저사이트 추천 배당률 1위 단폴 크로스 무제한 배팅 문의 텔레그램 @deal_two09",
    "바카라 공식 안전 보증업체 실시간 라이브 게임 첫충 20% 지급 telegram @deal_two10",
    "슬롯사이트 추천, 무료체험 프라그마틱 슬롯 머신 게임 환전 보장 코드 ACE777",
    "출장마사지 안내, 자택 호텔 모텔 24시간 방문 케어 예약 상담 텔레그램 @deal_two12",
    "한국야동 무료보기 고화질 성인동영상 최신 스트리밍 무제한 바로가기 adult-tube.vip",
    "성인방송 19금 라이브 BJ 소통 방송 무료 쿠폰 지급 바로가기 hot-live.online",
    "조건만남 실시간 1:1 매칭 24시간 비밀 보장 프로필 문의 tg:@deal_two15",
    "에볼루션 바카라 라이브 카지노 실시간 게임 참여 첫충 20% 보너스 지급 @deal_two16",
    "토토 입플 사이트 추천, 먹튀 검증 완료 안전 보증업체 가입머니 지급 텔레그램 @deal_two17",
    "파워볼 실시간 게임 홀짝 배팅 안전놀이터 첫충 20% 보너스 지급 @deal_two18",
    "포커 베팅 추천 카지노 게임, 텍사스 홀덤 안전 사이트 첫충 20% 지급 telegram @deal_two19",
    "안전놀이터 추천 먹튀검증 완료 사설토토 첫충 30% 지급 텔레그램 @deal_two20",
    "스웨디시 힐링 마사지 출장안마 20대 관리사 대기 예약 상담 텔레그램 @deal_two21",
    "온라인 카지노 커뮤니티 안전 보증업체 카지노 토토 TOP 6 가입머니 @deal_two22",
    "스포츠 베팅 축구 야구 실시간 라이브 배팅 안전놀이터 텔레그램 @deal_two23",
    "프라그마틱 슬롯 머신 게임 무료체험 가입코드 WIN77 무제한 환전",
)

PREVENTION_POOL = (
    "불법 도박 및 바카라 광고를 신고하세요. 청소년 중독 예방 교육 안내입니다.",
    "해외 온·오프라인 카지노 취업 및 이용 시 처벌 가능성 안내 - 외교부 해외안전여행",
    "겨울철 도로 위 공포 '블랙아이스' 대처법 안내 - 경기도청 안전총괄과",
    "청소년 불법 도박 및 사이버 도박 근절 예방 교육 안내 (도박문제 헬프라인 1336)",
    "국회도서관 소장도서 검색: 섹슈얼 엑스터시 사랑의 탄트라 (태일출판사)",
    "스웨디시 마사지가 체육전공 학생들의 자율신경계에 미치는 영향 (KCI 학술연구 논문)",
    "찾기쉬운 생활법령정보: 해외여행 준비하기 외화 환전 및 여행자보험 가입 절차",
    "목포시 상가 안내: 늘푸른오피 의류 매장 (신중앙시장 내 입점)",
    "서울문화포털 공연 안내: 청년음악 페스티벌 [2025 오피시디 스테이지: 디스커버리]",
    "강릉시 버스정보시스템: BIS 노선 안내 배차시간표 및 교통카드 충전소 안내",
    "성매매 피해자 지원 및 청소년 성범죄 예방 캠페인 안내 - 여성가족부",
    "사행산업통합감독위원회 불법 사행행위 신고센터 안내 (포상금 지급 규정)",
    "불법 마약류 및 향정신성의약품 오남용 확산 근절 대책 홍보 보도자료",
    "대리운전 및 성인전화방 불법 옥외광고물 강력단속 결과 공고",
    "불법 스포츠 도박 근절을 위한 대국민 서약 캠페인 안내 (국민체육진흥공단)",
    "인터넷 중독 및 스마트폰 과의존 예방 치유 지원 안내 센터",
    "사이버 범죄 예방의 날: 메신저 피싱 및 불법 스팸 문자 주의보 발령",
    "학교폭력 및 청소년 유해환경 정화 주간 운영 계획 공고",
    "가상자산 이용 사기 범죄 및 불법 투자 리딩방 피해 예방 안내문",
    "소비자원 피해예방주의보: 해외 직구 온라인 쇼핑몰 사기 주의",
    "불법 대부업 및 미등록 대부업체 고금리 피해 신고센터 안내",
    "지자체 공공 도서관 정기 휴관일 및 희망도서 신청 접수 안내",
    "공공체육시설 시설 대관 예약 슬롯 및 사용료 면제 대상 안내",
    "경찰청 국가수사본부 온라인 불법 도박 특별 단속 결과 발표",
)

VISIBLE_AD_POOL = (
    "바카라 카지노 회원 모집, 텔레그램 @localdemo 가입코드 WIN77",
    "먹튀검증 안전놀이터 메이저사이트 회원 모집 꽁머니 3만 지급 텔레그램 @deal_v02",
    "메이저-놀이터 스포츠 베팅 실시간 파워볼 회원 모집 가입코드 VIP77",
    "추천하는 토토 사이트 먹튀 검증 완료 회원 모집 첫충 매충 입플 혜택 tg:@deal_v04",
    "로투스 바카라 사이트 안전 보증업체 카지노 토토 회원 모집 즉시 지급",
    "온라인 슬롯 머신 게임 프라그마틱 무료체험 회원 모집 충전 보너스 30%",
    "카지노입플 핵심 보안 지표 정밀 리포트 회원 모집 첫충 30% 매충 15%",
    "골드피시카지노 공식인증 회원 모집 롤링 0% 무제한 환전 미러 도메인 safe-bet.top",
    "사설토토 메이저사이트 추천 배당률 1위 회원 모집 단폴 크로스 무제한",
    "바카라 공식 안전 보증업체 실시간 라이브 게임 회원 모집 첫충 20% 지급",
    "슬롯사이트 추천 무료체험 프라그마틱 슬롯 머신 회원 모집 코드 ACE777",
    "출장마사지 안내 자택 호텔 모텔 24시간 방문 케어 회원 모집 텔레그램 @deal_v12",
    "성인방송 19금 라이브 BJ 소통 방송 회원 모집 무료 쿠폰 즉시 지급",
    "조건만남 실시간 1:1 매칭 24시간 비밀 보장 회원 모집 tg:@deal_v14",
    "에볼루션 바카라 라이브 카지노 실시간 게임 회원 모집 첫충 20% 보너스",
    "토토 입플 사이트 추천 먹튀 검증 완료 안전 보증업체 회원 모집 가입머니 지급",
    "파워볼 실시간 게임 홀짝 배팅 안전놀이터 회원 모집 첫충 20% 보너스",
    "포커 베팅 추천 카지노 게임 텍사스 홀덤 안전 사이트 회원 모집 @deal_v18",
    "안전놀이터 추천 먹튀검증 완료 사설토토 회원 모집 첫충 30% 지급",
    "스웨디시 힐링 마사지 출장안마 20대 관리사 대기 회원 모집 텔레그램 @deal_v20",
    "온라인 카지노 커뮤니티 안전 보증업체 회원 모집 카지노 토토 TOP 6",
    "스포츠 베팅 축구 야구 실시간 라이브 배팅 안전놀이터 회원 모집",
    "프라그마틱 슬롯 머신 게임 무료체험 회원 모집 가입코드 WIN77",
    "바카라 온라인 게임 먹튀 검증 완료 안전 사이트 회원 모집 텔레그램 @deal_v24",
)

COMPOSITE_TWO_CTAS = (
    "안전 보증업체 먹튀검증 완료 첫충 30% 지급 텔레그램 @deal_h01 가입코드 WIN77",
    "실시간 라이브 베팅 신규 첫충 20% 보너스 텔레그램 @safe_h02 코드 TOP88",
    "메이저놀이터 추천 입플 보너스 환전 보장 텔그: @live_h03 코드 ACE77",
    "공식 인증업체 꽁머니 3만 즉시 지급 telegram @vip_h04 가입코드 WIN99",
    "슬롯 머신 게임 무료체험 환전 보장 텔레그램 @slot_h05 가입코드 STAR77",
)

COMPOSITE_MANY_CTAS = (
    "안전 보증업체 먹튀검증 완료 첫충 30% 지급 텔레그램 @deal_h06 가입코드 WIN77",
    "메이저놀이터 추천 입플 보너스 환전 보장 텔레그램 @safe_h07 가입코드 TOP88",
    "공식 인증업체 꽁머니 3만 즉시 지급 텔그: @vip_h08 가입코드 ACE77",
    "실시간 라이브 베팅 신규 첫충 20% 보너스 telegram @live_h09 코드 WIN99",
    "슬롯 머신 게임 무료체험 환전 보장 텔레그램 @slot_h10 가입코드 STAR77",
)


def _case(number, family, variant):
    identity = f"hard-{number:03d}"
    root = f"/cases/{identity}/"
    mark = f"[HARD_{number:03d}]"
    family_index = (number - 1) // len(VARIANTS)
    texts = [
        JAMO_OFFSCREEN_POOL[family_index % len(JAMO_OFFSCREEN_POOL)],
        HOMOGLYPH_TRANSPARENT_POOL[family_index % len(HOMOGLYPH_TRANSPARENT_POOL)],
        TWO_STYLES_POOL[family_index % len(TWO_STYLES_POOL)],
        PREVENTION_POOL[family_index % len(PREVENTION_POOL)],
        VISIBLE_AD_POOL[family_index % len(VISIBLE_AD_POOL)],
    ]
    styles = ["position:absolute;left:-12000px;top:40px;width:340px", "color:transparent",
              "position:absolute;left:-12000px;top:40px;width:340px;color:transparent",
              "color:transparent", "color:#222;background:#fff"]
    labels = [["JAMO", "OFFSCREEN"], ["HOMOGLYPH", "TRANSPARENT"],
              ["OFFSCREEN", "TRANSPARENT"], [], []]
    text, style, techniques = texts[variant] + " " + mark, styles[variant], labels[variant].copy()
    role = "positive" if techniques else "negative"
    if family == "composite-two":
        combinations = [("HOMOGLYPH", "TRANSPARENT"), ("JAMO", "OFFSCREEN"),
                        ("HOMOGLYPH", "JAMO"), ("HOMOGLYPH", "OFFSCREEN"), ("JAMO", "TRANSPARENT")]
        techniques = list(combinations[variant])
        cta = COMPOSITE_TWO_CTAS[variant % len(COMPOSITE_TWO_CTAS)]
        text = (("ｃａｓｉｎｏ " if "HOMOGLYPH" in techniques else "") +
                ("ㅂㅏㅋㅏㄹㅏ " if "JAMO" in techniques else "") +
                f"{cta} {mark}")
        style = ("color:transparent;" if "TRANSPARENT" in techniques else "") + (
            "position:absolute;left:-12000px;top:40px;width:340px;" if "OFFSCREEN" in techniques else "")
        role = "positive"
    elif family == "composite-many":
        combinations = [("HOMOGLYPH", "JAMO", "TRANSPARENT"), ("HOMOGLYPH", "JAMO", "OFFSCREEN"),
                        ("HOMOGLYPH", "TRANSPARENT", "OFFSCREEN"), ("JAMO", "TRANSPARENT", "OFFSCREEN"),
                        ("HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN")]
        techniques = list(combinations[variant])
        cta = COMPOSITE_MANY_CTAS[variant % len(COMPOSITE_MANY_CTAS)]
        text = (("ｃａｓｉｎｏ " if "HOMOGLYPH" in techniques else "") +
                ("ㅂㅏㅋㅏㄹㅏ " if "JAMO" in techniques else "") +
                f"{cta} {mark}")
        style = ("color:transparent;" if "TRANSPARENT" in techniques else "") + (
            "position:absolute;left:-12000px;top:40px;width:340px;" if "OFFSCREEN" in techniques else "")
        role = "positive"
    elif family == "negative-obfuscation":
        text = [
            "ㅂㅏㅋㅏㄹㅏ 불법 광고에 대한 청소년 예방 교육 안내문입니다.",
            "ｃａｓｉｎｏ 불법 홍보 및 사이버 도박을 신고하는 방법 안내입니다.",
            "바카라 카지노 불법 광고 단속 결과 보도자료 - 경찰청 사이버수사국",
            "새 창 열림. 이전 댓글과 다음 댓글을 키보드로 선택하세요.",
            "（주）공공도서관 정기 프로그램 접수 안내 ２０２６",
        ][variant] + " " + mark
        techniques, role = [], "negative"
    target = f'<p id="target" class="item text" style="{style}">{escape(text)}</p>'
    routes, steps, frames, statuses, forbidden = {}, [], [], [], []
    additional_frames = []
    checkpoint_path = root
    tags = ["synthetic", "local-only", VARIANTS[variant], "independent-authored-label"]

    family_index = (number - 1) // len(VARIANTS)
    admin_title = ADMIN_TITLES[family_index % len(ADMIN_TITLES)]
    dept_info = DEPARTMENTS[family_index % len(DEPARTMENTS)]
    date_str = f"2026-10-{(number % 28) + 1:02d}"
    views = 1580 + number * 23

    # Register authentic benign civil notices and negative false-positive traps
    for p in BENIGN_PUBLIC_POSTS:
        routes[root + f"post/{p['id']}"] = _route(render_benign_detail_page(p, root, family))
    for p in FALSE_POSITIVE_TRAPS:
        routes[root + f"post/{p['id']}"] = _route(render_benign_detail_page(p, root, family))

    related_pool = [
        BENIGN_PUBLIC_POSTS[family_index % len(BENIGN_PUBLIC_POSTS)],
        FALSE_POSITIVE_TRAPS[family_index % len(FALSE_POSITIVE_TRAPS)],
        BENIGN_PUBLIC_POSTS[(family_index + 1) % len(BENIGN_PUBLIC_POSTS)],
        FALSE_POSITIVE_TRAPS[(family_index + 2) % len(FALSE_POSITIVE_TRAPS)],
        BENIGN_PUBLIC_POSTS[(family_index + 3) % len(BENIGN_PUBLIC_POSTS)],
    ]
    related_posts = _render_related_posts_section(related_pool, root)

    def put(path, body, script="", **extra):
        routes[path] = _route(_page(body, script, title=f"{identity} · {admin_title}"), **extra)

    body = _render_post_view("h1", admin_title, target, dept_info, date_str, views, related_posts_html=related_posts)
    if family == "inherited-transparency":
        # Effective opacity may be inherited through ancestors even when the
        # text element's own computed opacity is one; retain that expectation.
        parent_style = ["color:transparent", "opacity:0", "color:rgba(0,0,0,0)", "opacity:0", "color:#fff;background:#fff"][variant]
        core = f'<section style="{parent_style}"><div><p id="target" class="item text">{escape(text)}</p></div></section>'
        body = _render_post_view("h1", admin_title, core, dept_info, date_str, views, related_posts_html=related_posts)
        techniques = (["JAMO", "TRANSPARENT"] if variant == 0 else
                      ["HOMOGLYPH", "TRANSPARENT"] if variant == 1 else
                      [] if variant == 3 else ["TRANSPARENT"])
        role = "positive" if techniques else "negative"
        tags += ["ancestor-style", "known_limitation"]
    elif family == "repeated-structure":
        card_items = [
            BENIGN_PUBLIC_POSTS[0],
            FALSE_POSITIVE_TRAPS[0],  # 도박 1336
            BENIGN_PUBLIC_POSTS[1],
            FALSE_POSITIVE_TRAPS[2],  # 작업대출 주의보
            BENIGN_PUBLIC_POSTS[2],
            FALSE_POSITIVE_TRAPS[3],  # PCIe 슬롯
            BENIGN_PUBLIC_POSTS[5],
        ]
        cards_html = []
        for c in card_items:
            c_trap = c.get("trap_type")
            c_badge = '<span class="badge-trap">[예방]</span> ' if c_trap == "prevention" else ('<span class="badge-normal">[점검]</span> ' if c_trap == "homonym" else '<span class="badge-normal">공지</span> ')
            cards_html.append(
                f'<article class="card">'
                f'<h3 class="card-title">{c_badge}<a href="{root}post/{c["id"]}" style="text-decoration:none;color:inherit">{escape(c["title"])}</a></h3>'
                f'<p class="card-desc">{escape(c["summary"])}</p>'
                f'<div class="card-meta"><span>{escape(c.get("dept", "스마트행정과"))}</span><span>{escape(c.get("date", "2026-10-01"))}</span></div>'
                f'</article>'
            )
        cards_html.append(
            f'<article class="card">'
            f'<h3 class="card-title"><span class="badge-pinned">[안내]</span> {escape(admin_title)}</h3>'
            f'<div class="card-desc">{target}</div>'
            f'<div class="card-meta"><span>{escape(dept_info[0])}</span><span>{escape(date_str)}</span></div>'
            f'</article>'
        )
        cards_wrap = f'<div class="cards-grid">{"".join(cards_html)}</div>'
        body = _render_post_view("h1", admin_title, cards_wrap, dept_info, date_str, views, related_posts_html=related_posts)
    elif family == "nested-frames":
        inner, outer = root + "inner", root + "outer"
        put(inner, target)
        put(outer, f'<div style="padding:10px"><h4 style="margin:0 0 8px 0;font-size:13px">중첩 의견 프레임</h4><iframe id="nested" title="중첩 댓글" src="{inner}"></iframe></div>')
        frame_content = (
            f'<div class="comment-section">'
            f'<div class="comment-header">기관 산하 참여 의견</div>'
            f'{_render_comments_list_html(DEFAULT_COMMENTS[:2])}'
            f'<iframe id="frame" title="게시판" src="{outer}"></iframe>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, frame_content, dept_info, date_str, views, related_posts_html=related_posts)
        frames = ["#frame", "#nested"]
    elif family == "same-source-frames":
        child = root + "shared"
        put(child, target)
        frames_content = (
            f'<div class="comment-section">'
            f'<div class="comment-header">좌우 대조 의견 게시판</div>'
            f'{_render_comments_list_html(DEFAULT_COMMENTS[:2])}'
            f'<div style="display:flex;gap:12px;margin-top:12px">'
            f'<iframe id="left" title="왼쪽" src="{child}"></iframe>'
            f'<iframe id="right" title="오른쪽" src="{child}"></iframe>'
            f'</div></div>'
        )
        body = _render_post_view("h1", admin_title, frames_content, dept_info, date_str, views, related_posts_html=related_posts)
        frames, additional_frames = ["#left"], [["#right"]]
        tags += ["duplicate-frame-source", "known_limitation"]
    elif family == "frame-replacement":
        initial, loaded = root + "empty", root + "loaded"
        put(initial, '<p style="padding:16px;color:#64748b">댓글을 선택하세요.</p>')
        put(loaded, target)
        frame_box = (
            f'<div class="comment-section">'
            f'<div class="comment-header">주민 참여 의견 및 피드백</div>'
            f'{_render_comments_list_html(DEFAULT_COMMENTS[:3])}'
            f'<div class="btn-area" style="margin-bottom:12px"><button id="more" type="button" class="btn btn-primary">댓글 더보기</button></div>'
            f'<iframe id="frame" src="{initial}"></iframe>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, frame_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            f"document.querySelector('#more').onclick=()=>setTimeout(()=>document.querySelector('#frame').src={json.dumps(loaded)},120)")
        steps, frames = [_click("#more"), _wait()], ["#frame"]
    elif family == "same-url-replacement":
        content_box = (
            f'<div class="comment-section">'
            f'<div class="comment-header">주민 참여 의견 및 제언</div>'
            f'<div class="btn-area" style="margin-bottom:16px"><button id="more" type="button" class="btn btn-primary">다음 페이지</button></div>'
            f'<section id="slot"><div class="comment-card"><div class="comment-meta"><span class="comment-author">김*호</span></div><div class="comment-body">첫 번째 목록: 공공 행정 서비스 개선을 위해 신속한 접수 및 피드백 부탁드립니다.</div></div>{_render_comments_list_html(DEFAULT_COMMENTS[:3])}</section>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            f"document.querySelector('#more').onclick=()=>setTimeout(()=>document.querySelector('#slot').innerHTML={json.dumps(target)},150)")
        steps = [_click("#more"), _wait()]
    elif family == "async-html-comments":
        response = root + "comments"
        put(response, target)
        content_box = (
            f'<div class="comment-section">'
            f'<div class="comment-header">주민 참여 의견 및 정책 제언 (총 7건)</div>'
            f'{_render_comments_list_html()}'
            f'<div class="btn-area"><button id="more" type="button" class="btn btn-primary">댓글 더보기</button></div>'
            f'<section id="slot"></section>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            _async_comments_script(response))
        steps = [_click("#more"), _wait()]
    elif family == "async-json-comments":
        response = root + "comments-data"
        routes[response] = {"body": json.dumps({"html": target}, ensure_ascii=False), "status": 200,
                            "content_type": "application/json; charset=utf-8"}
        content_box = (
            f'<div class="comment-section">'
            f'<div class="comment-header">주민 참여 의견 및 정책 제언 (총 7건)</div>'
            f'{_render_comments_list_html()}'
            f'<div class="btn-area"><button id="more" type="button" class="btn btn-primary" aria-label="댓글 더보기">댓글</button></div>'
            f'<section id="slot"></section>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            _async_comments_script(response, json_response=True))
        steps = [_click("#more"), _wait()]
    elif family == "delegated-listener":
        content_box = (
            f'<div class="comment-section">'
            f'<div class="comment-header">주민 참여 의견 (총 7건)</div>'
            f'{_render_comments_list_html()}'
            f'<section id="controls" class="btn-area"><button id="more" type="button" class="btn btn-primary"><span>댓글 더보기</span></button></section>'
            f'<section id="slot"></section>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            f"document.querySelector('#controls').addEventListener('click',e=>{{if(e.target.closest('#more'))setTimeout(()=>document.querySelector('#slot').innerHTML={json.dumps(target)},120)}})")
        steps = [_click("#more"), _wait()]
        tags += ["event-delegation"]
    elif family == "window-scroll":
        content_box = _render_window_scroll_content(target_slot='<section id="slot"></section>')
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            f"window.addEventListener('scroll',()=>setTimeout(()=>document.querySelector('#slot').innerHTML={json.dumps(target)},120),{{once:true}})")
        steps = [{"action": "scroll", "frames": []}, _wait()]
    elif family == "container-scroll":
        content_box = _render_container_scroll_content(target_slot='<section id="slot"></section>')
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            f"document.querySelector('#scrollbox').addEventListener('scroll',()=>setTimeout(()=>document.querySelector('#slot').innerHTML={json.dumps(target)},120),{{once:true}})")
        steps = [{"action": "scroll", "selector": "#scrollbox", "frames": []}, _wait()]
        tags += ["container-scroll", "known_limitation"]
    elif family == "finite-pagination":
        second, third = root + "page?page=2", root + "page?page=3"
        p1_items = [
            BENIGN_PUBLIC_POSTS[0],
            FALSE_POSITIVE_TRAPS[0],  # 도박 1336
            BENIGN_PUBLIC_POSTS[1],
            BENIGN_PUBLIC_POSTS[2],
            FALSE_POSITIVE_TRAPS[1],  # 위조약품 주의보
            BENIGN_PUBLIC_POSTS[3],
            BENIGN_PUBLIC_POSTS[4],
            BENIGN_PUBLIC_POSTS[5],
        ]
        p1_rows = _make_board_table_rows(p1_items, root, start_no=24)
        p1_pager = (
            f'<nav class="pagination" aria-label="게시판 1페이지 내비게이션">'
            f'<strong class="page-current">1</strong>'
            f'<a href="{second}" class="page-link">2</a>'
            f'<a href="{third}" class="page-link">3</a>'
            f'<a id="next" href="{second}" class="page-link">다음 &gt;</a>'
            f'</nav>'
        )
        p1_body = _render_board_list_view(p1_rows, p1_pager, page_num=1, total_pages=3, total_count=24)
        put(root, p1_body)

        p2_items = [
            BENIGN_PUBLIC_POSTS[6],
            FALSE_POSITIVE_TRAPS[2],  # 햇살론 사칭 작업대출
            FALSE_POSITIVE_TRAPS[3],  # PCIe 슬롯
            BENIGN_PUBLIC_POSTS[7],
            FALSE_POSITIVE_TRAPS[4],  # 성인 아카데미
            BENIGN_PUBLIC_POSTS[0],
            FALSE_POSITIVE_TRAPS[5],  # 창가의 토토
            BENIGN_PUBLIC_POSTS[2],
        ]
        p2_rows = _make_board_table_rows(p2_items, root, start_no=16)
        p2_pager = (
            f'<nav class="pagination" aria-label="게시판 2페이지 내비게이션">'
            f'<a href="{root}" class="page-link">&lt; 이전</a>'
            f'<a href="{root}" class="page-link">1</a>'
            f'<strong class="page-current">2</strong>'
            f'<a href="{third}" class="page-link">3</a>'
            f'<a id="next" href="{third}" class="page-link">다음 &gt;</a>'
            f'</nav>'
        )
        p2_body = _render_board_list_view(p2_rows, p2_pager, page_num=2, total_pages=3, total_count=24)
        put(second, p2_body)

        p3_items = [
            BENIGN_PUBLIC_POSTS[3],
            FALSE_POSITIVE_TRAPS[6],  # 웹 접근성 품질인증
            BENIGN_PUBLIC_POSTS[4],
            FALSE_POSITIVE_TRAPS[0],  # 도박 1336
            BENIGN_PUBLIC_POSTS[5],
            FALSE_POSITIVE_TRAPS[2],  # 햇살론 사칭
            BENIGN_PUBLIC_POSTS[1],
        ]
        p3_rows = _make_board_table_rows(
            p3_items, root, start_no=8, target_row_index=2,
            target_html=target, target_title=admin_title,
            dept_info=dept_info, date_str=date_str, views=views,
        )
        p3_pager = (
            f'<nav class="pagination" aria-label="게시판 3페이지 내비게이션">'
            f'<a href="{second}" class="page-link">&lt; 이전</a>'
            f'<a href="{root}" class="page-link">1</a>'
            f'<a href="{second}" class="page-link">2</a>'
            f'<strong class="page-current">3</strong>'
            f'</nav>'
        )
        p3_body = _render_board_list_view(p3_rows, p3_pager, page_num=3, total_pages=3, total_count=24)
        put(third, p3_body)
        for page_url, posts in ((root, p1_items), (second, p2_items), (third, p3_items)):
            for post in posts:
                response = routes[f"{root}post/{post['id']}"]
                response["list_url"] = page_url
                response["list_return_urls"] = [root, second, third]
        checkpoint_path = third
        tags += ["finite-cycle", "query-distinction"]
    elif family == "get-hidden-form":
        destination = root + "list?page=2&board=notice"
        form_items = [
            BENIGN_PUBLIC_POSTS[0],
            FALSE_POSITIVE_TRAPS[0],  # 도박 1336
            FALSE_POSITIVE_TRAPS[2],  # 작업대출 주의보
            FALSE_POSITIVE_TRAPS[3],  # PCIe 슬롯 점검
            BENIGN_PUBLIC_POSTS[1],
            BENIGN_PUBLIC_POSTS[2],
            FALSE_POSITIVE_TRAPS[5],  # 창가의 토토
            BENIGN_PUBLIC_POSTS[3],
        ]
        form_rows = _make_board_table_rows(form_items, root, start_no=16)
        form_pager = (
            f'<div class="pagination">'
            f'<strong class="page-current">1</strong>'
            f'<button type="submit" class="page-link" style="border:1px solid #cbd5e1;background:#fff;cursor:pointer">2</button>'
            f'<button type="submit" class="btn btn-primary" style="margin-left:8px;padding:5px 14px;font-size:13px">다음 페이지 &gt;</button>'
            f'</div>'
        )
        form_html = (
            f'<form method="get" action="{root}list" class="board-list-wrap">'
            f'<div class="board-search-bar">'
            f'<div class="board-total">전자정부 공지사항 (총 <strong>16</strong>건, 1/2 페이지)</div>'
            f'<div class="search-form">'
            f'<input type="text" class="input-search" placeholder="제목 검색" readonly value="">'
            f'<button type="button" class="btn-search">검색</button>'
            f'</div>'
            f'</div>'
            f'<input type="hidden" name="page" value="2">'
            f'<input type="hidden" name="board" value="notice">'
            f'<table class="board-list" summary="스마트행정안전포털 공지사항 목록">'
            f'<thead><tr>'
            f'<th style="width:8%">번호</th><th style="width:52%">제목</th><th style="width:16%">담당부서</th><th style="width:14%">작성일</th><th style="width:10%">조회수</th>'
            f'</tr></thead>'
            f'<tbody>{form_rows}</tbody>'
            f'</table>'
            f'{form_pager}'
            f'</form>'
        )
        put(root, form_html)
        detail_dest = _render_post_view("h1", admin_title, target, dept_info, date_str, views, related_posts_html=related_posts)
        put(destination, detail_dest)
        checkpoint_path = destination
    elif family == "blocked-post":
        forbidden_path = root + "submit"
        put(forbidden_path, '<p>상태 변경용 시험 경로입니다.</p>')
        forbidden = [forbidden_path]
        if variant % 2:
            put(root, body + '<div class="btn-area"><button id="submit" type="button" class="btn btn-primary">댓글 등록</button></div>',
                f"document.querySelector('#submit').onclick=()=>fetch({json.dumps(forbidden_path)},{{method:'POST',body:'fixture=1'}})")
        else:
            body += (f'<form method="post" action="{forbidden_path}" class="comment-card" style="margin-top:20px"><input name="comment" value="기능 시험" class="input-search">'
                     '<button type="submit" class="btn btn-primary" style="margin-left:8px">등록</button></form>')
        tags += ["state-change-blocked"]
    elif family == "blocked-delete":
        first, second = root + "delete", root + "logout"
        put(first, '<p>삭제 요청 시험 경로</p>')
        put(second, '<p>로그아웃 요청 시험 경로</p>')
        forbidden = [first, second]
        body += f'<div class="btn-area"><a href="{first}" class="btn">게시글 삭제</a><a href="{second}" class="btn">로그아웃</a></div>'
        tags += ["state-change-blocked"]
    elif family in ("http-404", "http-500"):
        code = 404 if family == "http-404" else 500
        failed = root + "missing" if code == 404 else root + "unavailable"
        put(failed, '<h1>현재 게시글을 제공할 수 없습니다.</h1>', status=code)
        body += f'<div class="btn-area"><a href="{failed}" class="btn">다음 페이지</a></div>'
        statuses = [{"path": failed, "status": "오류 응답"}]
        tags += ["partial-crawl-status"]
    elif family in ("retry-429", "retry-503"):
        code = 429 if family == "retry-429" else 503
        retry = root + "retry"
        retry_items = [
            BENIGN_PUBLIC_POSTS[0],
            FALSE_POSITIVE_TRAPS[0],  # 도박 1336
            FALSE_POSITIVE_TRAPS[2],  # 작업대출 주의보
            BENIGN_PUBLIC_POSTS[1],
            FALSE_POSITIVE_TRAPS[3],  # PCIe 슬롯
            BENIGN_PUBLIC_POSTS[2],
        ]
        retry_rows = _make_board_table_rows(retry_items, root, start_no=12)
        retry_row = (
            f'<tr style="background:#f0f7ff">'
            f'<td>13</td>'
            f'<td class="title-col"><span class="badge-pinned">[필독]</span> <a href="{retry}" style="font-weight:700;color:#1a3c6e">{escape(admin_title)}</a></td>'
            f'<td>{escape(dept_info[0])}</td>'
            f'<td>{escape(date_str)}</td>'
            f'<td>{escape(f"{views:,}")}</td>'
            f'</tr>'
        )
        list_html = (
            f'<div class="board-list-wrap">'
            f'<div class="board-search-bar">'
            f'<div class="board-total">자료실 공지 목록 (총 <strong>13</strong>건)</div>'
            f'<div class="search-form"><a href="{retry}" class="btn btn-primary" style="padding:6px 14px;font-size:13px">게시글 보기</a></div>'
            f'</div>'
            f'<table class="board-list" summary="자료실 목록">'
            f'<thead><tr><th style="width:8%">번호</th><th style="width:52%">제목</th><th style="width:16%">담당부서</th><th style="width:14%">작성일</th><th style="width:10%">조회수</th></tr></thead>'
            f'<tbody>{retry_row}{retry_rows}</tbody>'
            f'</table>'
            f'</div>'
        )
        put(root, list_html)
        retry_content = _render_post_view("h1", admin_title, target, dept_info, date_str, views, related_posts_html=related_posts)
        put(retry, retry_content, status_sequence=[code, 200], headers={"Retry-After": "0"})
        checkpoint_path = retry
        statuses = [{"path": retry, "status": "성공"}]
        tags += ["bounded-retry"]
    elif family == "dialog-transition":
        content_box = (
            f'<div class="comment-section">'
            f'<div class="comment-header">주민 열린 마당</div>'
            f'{_render_comments_list_html(DEFAULT_COMMENTS[:3])}'
            f'<div class="btn-area"><button id="more" type="button" class="btn btn-primary">댓글 보기</button></div>'
            f'<dialog id="dialog" class="gov-dialog" style="border:1px solid #cbd5e1;border-radius:6px;padding:24px;max-width:540px"></dialog>'
            f'</div>'
        )
        body = _render_post_view("h1", admin_title, content_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            f"document.querySelector('#more').onclick=()=>{{let dialog=document.querySelector('#dialog');dialog.innerHTML={json.dumps(target)};dialog.showModal()}}")
        steps = [_click("#more"), _wait(100)]
        tags += ["modal", "known_limitation"]
    elif family == "dynamic-tabs":
        tabs_box = (
            '<div role="tablist" class="gov-tabs">'
            '<button id="notice-tab" role="tab" type="button" class="tab-btn" aria-controls="tab-notice" aria-selected="true">본문 안내</button>'
            '<button id="more" role="tab" type="button" class="tab-btn" aria-controls="slot" aria-selected="false">주민 의견 (6건)</button>'
            '</div>'
            '<section id="tab-notice" role="tabpanel" aria-labelledby="notice-tab" class="tab-panel">'
            '<div class="info-callout">'
            '<strong>[행정안내]</strong> 2026년도 하반기 공공서비스 및 주요 추진 과제 세부 지침을 아래와 같이 공표합니다.'
            '</div>'
            '<table class="board-meta-table" style="margin:16px 0">'
            '<tbody>'
            '<tr><th>과제명</th><td>공공시설물 정기 점검 및 안심 귀갓길 조성</td><th>추진기간</th><td>2026-10-01 ~ 2026-12-31</td></tr>'
            '<tr><th>담당부서</th><td>생활안전과 열린민원팀</td><th>문의전화</th><td>02-120</td></tr>'
            '</tbody></table>'
            '<div class="info-callout info-callout-alert">'
            '<strong>[공공예방 1336] 청소년 불법 사이버 도박 근절</strong><br>'
            '청소년 대상 온라인 불법 바카라 및 사설 스포츠토토는 범죄 행위입니다. 한국도박문제예방치유원 헬프라인(☎ 1336)에서 24시간 익명 무료 상담을 지원합니다.'
            '</div>'
            '<div class="info-callout info-callout-warning">'
            '<strong>[금융사기 주의보] 정책자금 사칭 불법 작업대출 주의</strong><br>'
            '서민금융진흥원 또는 햇살론을 사칭하여 수수료를 요구하거나 통장 대여를 유도하는 사기 수법에 각별히 유의하십시오.'
            '</div>'
            '<div class="info-callout">'
            '<strong>[전산 시스템 점검] 메인프레임 PCIe 슬롯 확장</strong><br>'
            'I/O 패킷 처리 최적화를 위한 서버실 고속 PCIe 슬롯 증설 점검이 예정되어 있습니다.'
            '</div>'
            '</section>'
            '<section id="slot" role="tabpanel" aria-labelledby="more" class="tab-panel" hidden>'
            '<p style="color:#64748b;padding:12px 0">상단 [주민 의견] 탭을 클릭하시면 주민 제언 및 의견이 표시됩니다.</p>'
            '</section>'
        )
        body = _render_post_view("h1", admin_title, tabs_box, dept_info, date_str, views, related_posts_html=related_posts)
        put(root, body,
            "let commentsLoaded=false;function selectTab(comments){"
            "document.querySelector('#notice-tab').setAttribute('aria-selected',String(!comments));"
            "document.querySelector('#more').setAttribute('aria-selected',String(comments));"
            "document.querySelector('#tab-notice').hidden=comments;document.querySelector('#slot').hidden=!comments;}"
            "document.querySelector('#notice-tab').onclick=()=>selectTab(false);"
            "document.querySelector('#more').onclick=()=>{selectTab(true);if(commentsLoaded)return;commentsLoaded=true;"
            f"setTimeout(()=>document.querySelector('#slot').innerHTML={json.dumps(target + '<div class=\"comment-section\" style=\"margin-top:20px\"><div class=\"comment-header\">주민 참여 의견</div>' + _render_comments_list_html() + '</div>')},120);}}")
        steps = [_click("#more"), _wait()]
    if root not in routes:
        put(root, body)
    targets = [{"selector": "#target", "frames": frames, "text": text,
                "techniques": techniques, "role": role}]
    targets.extend({"selector": "#target", "frames": chain, "text": text,
                    "techniques": techniques, "role": role} for chain in additional_frames)
    condition = ('+'.join(techniques) if techniques else
                 "negative-prevention" if any(word in text for word in ("예방", "신고", "단속")) else
                 "visible-ad" if "회원 모집" in text else "negative-normal")
    tags = [tag for tag in tags if tag not in VARIANTS] + [condition]
    return {"id": identity, "difficulty": "hard", "family": family, "group_id": "hard-" + family,
            "description": f"{family}: {condition}의 복합 관측 및 정상 반례", "tags": tags,
            "entry": root, "routes": finish_routes(routes, root),
            "checkpoints": [{"path": checkpoint_path, "steps": steps, "targets": targets}],
            "expected_statuses": statuses, "forbidden_requests": forbidden}


def build_cases():
    return [_case(i * 5 + variant + 1, family, variant)
            for i, family in enumerate(FAMILIES) for variant in range(5)]
