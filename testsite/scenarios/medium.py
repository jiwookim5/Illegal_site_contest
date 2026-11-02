"""Independent, local synthetic institution UI patterns; no real-site copies.

The labels express advertising context AND transparent/offscreen concealment.
They are authored here without importing the implementation under evaluation.
Each UI family has five materially different content/style conditions, including
visible advertising, harmless hidden accessibility text and prevention notices.
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
    "jsp-query-table", "asp-query-cards", "egov-hidden-get", "js-go-function",
    "inline-location", "get-page-index", "select-navigation", "finite-number-pages",
    "listener-next-page", "same-url-replacement", "delayed-more", "accessible-name",
    "aria-tabs", "native-details", "dialog-comments", "iframe-document",
    "iframe-srcdoc", "nested-iframes", "legacy-frame", "duplicate-dom-ids",
    "ancestor-style", "scroll-insertion", "two-stage-replies", "short-title-detail",
)
VARIANTS = ("offscreen-ad", "transparent-ad", "visible-ad", "hidden-accessibility", "hidden-prevention")


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
    ".comment-meta { font-size: 12px; color: #64748b; margin-bottom: 4px; display: flex; gap: 12px; }"
    ".comment-author { font-weight: 600; color: #334155; }"
    ".btn-area { display: flex; justify-content: center; gap: 8px; margin-top: 24px; padding-top: 18px; border-top: 1px solid #e2e8f0; }"
    ".btn { padding: 8px 18px; font-size: 14px; font-weight: 500; border-radius: 4px; border: 1px solid #cbd5e1; background: #fff; color: #334155; cursor: pointer; text-decoration: none; }"
    ".btn-primary { background: #1a3c6e; color: #fff; border-color: #1a3c6e; }"
    ".board-list-wrap { background: #fff; padding: 20px; border: 1px solid #e2e8f0; border-radius: 6px; }"
    ".board-search-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; font-size: 13px; }"
    ".board-total strong { color: #1a3c6e; }"
    "table.board-list { width: 100%; border-collapse: collapse; margin-top: 8px; background: #fff; border-top: 2px solid #1a3c6e; }"
    "table.board-list th { background: #f8fafc; padding: 11px 8px; border-bottom: 1px solid #cbd5e1; font-weight: 600; font-size: 13px; color: #334155; }"
    "table.board-list td { padding: 10px 8px; border-bottom: 1px solid #e2e8f0; text-align: center; font-size: 13px; color: #475569; }"
    "table.board-list td.title-col { text-align: left; }"
    "table.board-list td.title-col a { color: #1e293b; text-decoration: none; font-weight: 500; }"
    "table.board-list td.title-col a:hover { text-decoration: underline; color: #1a3c6e; }"
    ".badge-pinned { background: #fee2e2; color: #b91c1c; font-weight: 600; padding: 2px 6px; border-radius: 3px; font-size: 11px; }"
    ".badge-normal { background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 3px; font-size: 11px; }"
    ".pagination { display: flex; justify-content: center; gap: 4px; margin-top: 16px; }"
    ".page-current { display: inline-block; padding: 4px 10px; background: #1a3c6e; color: #fff; border-radius: 3px; font-size: 13px; font-weight: bold; }"
    ".page-link { padding: 4px 10px; border: 1px solid #cbd5e1; background: #fff; color: #475569; border-radius: 3px; font-size: 13px; cursor: pointer; text-decoration: none; }"
    ".cards { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }"
    ".cards > a { display: block; padding: 18px; border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; text-decoration: none; color: inherit; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }"
    ".cards > a:hover { border-color: #1a3c6e; }"
    ".card-desc { font-size: 13px; color: #64748b; margin: 8px 0; }"
    ".card-meta { font-size: 12px; color: #94a3b8; display: flex; justify-content: space-between; }"
    ".gov-tabs { display: flex; border-bottom: 2px solid #1a3c6e; margin-bottom: 16px; }"
    ".tab-btn { padding: 10px 20px; font-size: 14px; font-weight: 600; background: #f1f5f9; border: 1px solid #cbd5e1; border-bottom: none; cursor: pointer; border-radius: 4px 4px 0 0; }"
    ".tab-btn[aria-selected='true'] { background: #1a3c6e; color: #fff; border-color: #1a3c6e; }"
    ".tab-panel { padding: 16px; background: #fff; border: 1px solid #e2e8f0; border-top: none; min-height: 120px; }"
    ".gov-dialog { padding: 24px; border: 1px solid #cbd5e1; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.15); max-width: 500px; width: 90%; }"
    "iframe { width: 100%; max-width: 600px; height: 200px; border: 1px solid #cbd5e1; border-radius: 4px; }"
    ".board-ol { list-style: decimal; padding-left: 24px; margin: 16px 0; }"
    ".board-ol li { padding: 8px 0; border-bottom: 1px dashed #e2e8f0; font-size: 14px; }"
    ".board-ol li a { color: #1a3c6e; text-decoration: none; font-weight: 600; }"
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
        f'<footer class="btn-area">'
        f'<button type="button" class="btn btn-primary">목록</button>'
        f'<button type="button" class="btn">인쇄</button>'
        f'<button type="button" class="btn">공유</button>'
        f'</footer>'
        f'</article>'
    )


def _page(body: str, script: str = "", *, title: str = "합성 공공 게시판") -> str:
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{escape(title)} - 스마트행정안전포털</title>'
            f'<style>{EGOV_CSS}</style>'
            f'</head><body>'
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
            + (f'<script>{script}</script>' if script else '') + '</body></html>')


def _route(body: str) -> dict:
    return {"body": body, "status": 200, "content_type": "text/html; charset=utf-8"}


def _click(selector: str, frames: list[str] | None = None) -> dict:
    return {"action": "click", "selector": selector, "frames": frames or []}


# Real-world inspired phrase pools from google_dataset_20260930
ADVERTISING_POOL = (
    "먹튀검증 | 구글검색 꽁타 먹튀 피하는 법, 안전 보증업체 꽁머니 첫충 30% 지급 텔레그램 @deal_med01",
    "메이저-놀이터 : 스포츠 베팅, 실시간 바카라, 파워볼 홀덤 안전 보증업체 가입코드 VIP77",
    "추천하는 토토 사이트, 먹튀 검증 완료, 첫충 매충 입플 혜택 안전 베팅 사이트 tg:@deal_med03",
    "로투스 바카라 사이트 안전 보증업체 카지노 토토 TOP 6 신규 가입머니 즉시 지급 @deal_med04",
    "온라인 슬롯 머신 게임 안전 보증업체 카지노 토토 프라그마틱 무료체험 충전 보너스 30% 지급",
    "카지노입플 2026 핵심 보안 지표 정밀 리포트 첫충 30% 매충 15% 지급 텔레그램 @deal_med06",
    "골드피시카지노 공식인증업체, 롤링 0% 무제한 환전 미러 도메인 safe-bet.top",
    "사설토토 메이저사이트 추천 배당률 1위 단폴 크로스 무제한 배팅 문의 텔레그램 @deal_med08",
    "바카라 공식 안전 보증업체 실시간 라이브 게임 첫충 20% 지급 telegram @deal_med09",
    "슬롯사이트 추천, 무료체험 프라그마틱 슬롯 머신 게임 환전 보장 코드 ACE777",
    "출장마사지 안내, 자택 호텔 모텔 24시간 방문 케어 예약 상담 텔레그램 @deal_med11",
    "한국야동 무료보기 고화질 성인동영상 최신 스트리밍 무제한 바로가기 adult-tube.vip",
    "성인방송 19금 라이브 BJ 소통 방송 무료 쿠폰 지급 바로가기 hot-live.online",
    "조건만남 실시간 1:1 매칭 24시간 비밀 보장 프로필 문의 tg:@deal_med14",
    "에볼루션 바카라 라이브 카지노 실시간 게임 참여 첫충 20% 보너스 지급 @deal_med15",
    "토토 입플 사이트 추천, 먹튀 검증 완료 안전 보증업체 가입머니 지급 텔레그램 @deal_med16",
    "파워볼 실시간 게임 홀짝 배팅 안전놀이터 첫충 20% 보너스 지급 @deal_med17",
    "포커 베팅 추천 카지노 게임, 텍사스 홀덤 안전 사이트 첫충 20% 지급 telegram @deal_med18",
    "안전놀이터 추천 먹튀검증 완료 사설토토 첫충 30% 지급 텔레그램 @deal_med19",
    "스웨디시 힐링 마사지 출장안마 20대 관리사 대기 예약 상담 텔레그램 @deal_med20",
    "온라인 카지노 커뮤니티 안전 보증업체 카지노 토토 TOP 6 가입머니 @deal_med21",
    "스포츠 베팅 축구 야구 실시간 라이브 배팅 안전놀이터 텔레그램 @deal_med22",
    "프라그마틱 슬롯 머신 게임 무료체험 가입코드 WIN77 무제한 환전",
    "바카라 사이트 회원 모집, 텔레그램 @localdemo 첫 충전 보너스 안내",
)

ACCESSIBILITY_POOL = (
    "본문 바로가기 안내: 키보드로 원하는 본문 영역으로 이동하세요.",
    "주 메뉴 건너뛰기 링크: 스크린리더 사용자를 위한 탐색 안내입니다.",
    "자료실 검색 결과 안내. 키보드로 다음 항목을 선택하세요.",
    "게시판 목록 페이징 안내: 이전 페이지와 다음 페이지 이동 링크.",
    "첨부파일 다운로드 바로가기 안내: 파일 형식 및 용량 확인.",
    "시각장애인용 대체 텍스트: 공공누리 제1유형 출처표시 마크.",
    "표 탐색 안내: 행과 열 헤더 정보를 음성으로 청취할 수 있습니다.",
    "기관 안내 사이트맵 바로가기: 전체 메뉴 구조를 확인하세요.",
    "검색 필터 초기화 바로가기: 선택된 검색 조건을 모두 해제합니다.",
    "팝업 레이어 닫기 안내: ESC 키 또는 닫기 버튼을 누르세요.",
    "모바일 반응형 메뉴 펼치기 안내: 하위 메뉴가 슬라이드로 열립니다.",
    "전자민원 접수 단계별 진행 상황 안내: 현재 2단계 신청서 작성 중.",
    "댓글 작성 구역 바로가기: 의견 등록 양식으로 포커스가 이동합니다.",
    "본문 글자 크기 확대 축소 기능 안내: 브라우저 기본 배율 유지 권장.",
    "동영상 플레이어 자막 켜기 끄기 단축키 안내: 키보드 C 키 입력.",
    "로그인 세션 만료 5분 전 연장 알림: 시간 연장 버튼을 누르세요.",
    "공공 데이터 API 명세서 다운로드 링크: JSON 및 XML 포맷 제공.",
    "도로명 주소 검색 우편번호 찾기 레이어 창 바로가기 안내.",
    "조직도 안내: 부서별 담당 업무 및 직원 연락처 검색 바로가기.",
    "이용약관 및 개인정보 처리방침 전문 보기 바로가기 링크.",
    "새 창 열림 안내: 외부 연계 시스템 링크로 새 탭에서 열립니다.",
    "예약 캘린더 날짜 선택 안내: 방향키로 날짜를 탐색할 수 있습니다.",
    "민원 처리 결과 알림톡 수신 동의 체크박스 안내문.",
    "시민 참여 투표 결과 그래프 대체 텍스트 및 상세 수치 표.",
)

PREVENTION_POOL = (
    "불법 도박과 바카라 광고 신고 안내. 청소년 피해 예방 교육 자료입니다.",
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


def _select_benign_and_traps(family_index: int, variant_index: int = 0) -> tuple[list[dict], list[dict]]:
    """Deterministically select 6 benign posts and 3 false-positive trap posts."""
    seed = family_index * 5 + variant_index
    b_len = len(BENIGN_PUBLIC_POSTS)
    t_len = len(FALSE_POSITIVE_TRAPS)
    benigns = [BENIGN_PUBLIC_POSTS[(seed + i) % b_len] for i in range(6)]
    traps = [FALSE_POSITIVE_TRAPS[(seed + i) % t_len] for i in range(3)]
    return benigns, traps


def _register_benign_and_trap_routes(routes: dict, root: str, family: str, posts: list[dict]):
    """Register authentic e-Gov detail page routes for all benign and trap posts."""
    for post in posts:
        post_url = f"{root}posts/{post['id']}.html"
        if post_url not in routes:
            routes[post_url] = _route(render_benign_detail_page(post, root, family))


def _render_board_table_rows(posts: list[dict], root: str, start_index: int = 2) -> str:
    """Generate HTML table rows for benign and trap posts."""
    rows = []
    for idx, post in enumerate(posts, start=start_index):
        post_url = f"{root}posts/{post['id']}.html"
        trap_type = post.get("trap_type")
        if trap_type == "prevention":
            badge = '<span class="badge-pinned">주의/예방</span>'
        elif trap_type:
            badge = '<span class="badge-normal">안내/교양</span>'
        else:
            badge = '<span class="badge-normal">일반공고</span>'
        title = escape(post["title"])
        dept = escape(post.get("dept", "스마트행정과"))
        date_str = escape(post.get("date", "2026-10-01"))
        rows.append(
            f'<tr><td>{idx}</td><td>{badge}</td><td class="title-col">'
            f'<a href="{escape(post_url, quote=True)}">{title}</a></td>'
            f'<td>{dept}</td><td>{date_str}</td></tr>'
        )
    return "".join(rows)


def _render_cards_html(posts: list[dict], root: str) -> str:
    """Generate HTML cards for benign and trap posts."""
    cards = []
    for post in posts:
        post_url = f"{root}posts/{post['id']}.html"
        trap_type = post.get("trap_type")
        badge = "예방" if trap_type == "prevention" else "안내"
        title = escape(post["title"])
        summary = escape(post.get("summary", "주민 편익을 위한 공식 행정 안내입니다."))
        dept = escape(post.get("dept", "열린민원과"))
        date_str = escape(post.get("date", "2026-10-01"))
        cards.append(
            f'<article><a href="{escape(post_url, quote=True)}">'
            f'<span class="badge-normal">{badge}</span> <strong>{title}</strong>'
            f'<p class="card-desc">{summary}</p>'
            f'<div class="card-meta"><span>담당: {dept}</span> <span>작성일: {date_str}</span></div>'
            f'</a></article>'
        )
    return "".join(cards)


def _render_related_board_box(posts: list[dict], root: str, title: str = "최신 행정 공고 및 유관 정보") -> str:
    """Generate a clean side/bottom board table box for benign/trap posts."""
    rows = _render_board_table_rows(posts, root, start_index=1)
    return (
        f'<div class="board-list-wrap" style="margin-top:24px">'
        f'<div class="board-search-bar"><div class="board-total"><strong>{escape(title)}</strong> (총 {len(posts)}건)</div></div>'
        f'<table class="board-list"><caption>{escape(title)} 목록</caption>'
        f'<thead><tr><th style="width:10%">번호</th><th style="width:18%">구분</th>'
        f'<th style="width:46%">제목</th><th style="width:16%">담당부서</th><th style="width:10%">일자</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        '<div class="pagination"><span class="page-current">1</span></div>'
        f'</div>'
    )


def _case(number: int, family: str, variant: str) -> dict:
    identity = f"medium-{number:03d}"
    root = f"/cases/{identity}/"
    marker = f"MEDIUM_{number:03d}"
    family_index = (number - 1) // len(VARIANTS)
    admin_title = ADMIN_TITLES[family_index % len(ADMIN_TITLES)]
    dept_info = DEPARTMENTS[family_index % len(DEPARTMENTS)]
    date_str = f"2026-10-{(number % 28) + 1:02d}"
    views = 1240 + number * 17
    advertising = f"{ADVERTISING_POOL[family_index % len(ADVERTISING_POOL)]} [{marker}]"
    if variant == "hidden-accessibility":
        text = f"{ACCESSIBILITY_POOL[family_index % len(ACCESSIBILITY_POOL)]} [{marker}]"
    elif variant == "hidden-prevention":
        text = f"{PREVENTION_POOL[family_index % len(PREVENTION_POOL)]} [{marker}]"
    else:
        text = advertising
    styles = {
        "offscreen-ad": "position:absolute;left:-12000px;top:40px;width:320px",
        "transparent-ad": "color:rgba(20,30,40,0)",
        "visible-ad": "color:#222;background:#fff",
        "hidden-accessibility": "position:absolute;left:-12000px;top:40px;width:320px",
        "hidden-prevention": "opacity:0",
    }
    style = styles[variant]
    techniques = (["OFFSCREEN"] if variant == "offscreen-ad" else
                  ["TRANSPARENT"] if variant == "transparent-ad" else [])
    target_html = f'<p id="target" style="{style}">{escape(text)}</p>'
    routes = {}
    path, steps, frames, selector = root, [], [], "#target"
    title = f"{identity} · {admin_title}"

    variant_index = VARIANTS.index(variant)
    benigns, traps = _select_benign_and_traps(family_index, variant_index)
    all_sample_posts = [
        benigns[0], traps[0], benigns[1], traps[1],
        benigns[2], traps[2], benigns[3], benigns[4], benigns[5],
    ]
    _register_benign_and_trap_routes(routes, root, family, all_sample_posts)

    def put(url, body, script=""):
        routes[url] = _route(_page(body, script, title=title))

    def detail_link(url, content, script=""):
        nonlocal path
        put(root, content, script)
        detail_html = _render_post_view("h1", admin_title, target_html, dept_info, date_str, views)
        put(url, detail_html)
        path = url

    if family == "jsp-query-table":
        detail = root + "selectBbsNttView.do?bbsNo=7&nttNo=42"
        target_row = (
            f'<tr><td>1</td><td><span class="badge-pinned">고정공지</span></td>'
            f'<td class="title-col"><a href="{escape(detail, quote=True)}">{admin_title}</a></td>'
            f'<td>{dept_info[0]}</td><td>{date_str}</td></tr>'
        )
        benign_rows = _render_board_table_rows(all_sample_posts, root, start_index=2)
        entry_content = (
            '<div class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">총 <strong>{len(all_sample_posts) + 1}</strong>건 (1/1 페이지)</div></div>'
            '<table class="board-list"><caption>시민 게시판 목록</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{target_row}{benign_rows}</tbody></table>'
            '<div class="pagination"><span class="page-current">1</span></div>'
            '</div>'
        )
        detail_link(detail, entry_content)
    elif family == "asp-query-cards":
        detail = root + "View.asp?BoardID=notice&IDX=21"
        target_card = (
            f'<article><a href="{escape(detail, quote=True)}">'
            f'<span class="badge-pinned">주요공지</span> <strong>{admin_title}</strong>'
            f'<p class="card-desc">주민 안내 새 소식 및 세부 시행계획 확인</p>'
            f'<div class="card-meta"><span>담당: {dept_info[0]}</span> <span>작성일: {date_str}</span></div>'
            '</a></article>'
        )
        benign_cards = _render_cards_html(all_sample_posts, root)
        entry_content = (
            '<div class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">총 <strong>{len(all_sample_posts) + 1}</strong>건 (1/1 페이지)</div></div>'
            f'<div class="cards">{target_card}{benign_cards}</div>'
            '<div class="pagination"><span class="page-current">1</span></div>'
            '</div>'
        )
        detail_link(detail, entry_content)
    elif family == "egov-hidden-get":
        detail = root + "detail.do?bbsId=BBS_0001&nttId=305"
        entry_content = (
            f'<form id="boardForm" method="get" action="{root}detail.do" class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">공지사항 상세조회 (전자정부 표준 서식)</div></div>'
            f'<p style="font-size:16px;font-weight:600;margin:12px 0">📌 {admin_title} <span style="font-size:13px;color:#64748b;font-weight:normal">(담당: {dept_info[0]})</span></p>'
            '<input type="hidden" name="bbsId" value="BBS_0001">'
            '<input type="hidden" name="nttId" value="305"><button type="submit" class="btn btn-primary">상세보기</button></form>'
            + _render_related_board_box(all_sample_posts, root, "사전정보공표 일반 행정자료 및 민원공고")
        )
        detail_link(detail, entry_content)
    elif family == "js-go-function":
        detail = root + "article.jsp?seq=19"
        entry_content = (
            f'<div class="board-list-wrap">'
            f'<p style="font-size:16px;font-weight:600;margin-bottom:12px">📌 {admin_title}</p>'
            f'<a href="#" id="open" onclick="goArticle(19);return false" class="btn btn-primary">게시글 보기</a>'
            f'</div>'
            + _render_related_board_box(all_sample_posts, root, "시민 열린마당 최근 게시글")
        )
        detail_link(detail, entry_content,
                    f'function goArticle(seq){{location.href={json.dumps(root + "article.jsp?seq=")}+seq;}}')
    elif family == "inline-location":
        detail = root + "view.html?article=8"
        entry_content = (
            f'<div class="board-list-wrap">'
            f'<p style="font-size:16px;font-weight:600;margin-bottom:12px">📌 {admin_title}</p>'
            f'<button id="open" type="button" class="btn btn-primary" onclick="location.assign(\'{detail}\')">상세보기</button>'
            f'</div>'
            + _render_related_board_box(all_sample_posts, root, "생활안전 및 주민 협조 공고 목록")
        )
        detail_link(detail, entry_content)
    elif family == "get-page-index":
        detail = root + "list.jsp?board=free&pageIndex=2"
        benign_rows = _render_board_table_rows(all_sample_posts, root, start_index=1)
        entry_content = (
            '<div class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">자유게시판 (1/2 페이지, 총 {len(all_sample_posts) + 1}건)</div></div>'
            '<table class="board-list"><caption>열린 자유게시판 1페이지</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{benign_rows}</tbody></table>'
            f'<div class="pagination"><span class="page-current">1</span><a href="{detail}" class="page-link">2</a></div>'
            '</div>'
            f'<form name="paging" method="get" action="{root}list.jsp" class="board-list-wrap" style="margin-top:16px">'
            f'<div class="board-search-bar"><div class="board-total">페이지 바로 이동: <strong>{admin_title}</strong></div></div>'
            '<input name="board" type="hidden" value="free"><input name="pageIndex" type="hidden" value="2">'
            '<button aria-label="다음 페이지" type="submit" class="btn btn-primary">다음</button></form>'
        )
        put(root, entry_content)
        put(detail, '<div class="board-list-wrap"><p>자유게시판 (2/2 페이지)</p>'
            + _render_post_view("h1", admin_title, target_html, dept_info, date_str, views)
            + f'<nav class="pagination"><a href="{root}" class="page-link">1</a><span class="page-current">2</span></nav></div>')
        path = detail
    elif family == "select-navigation":
        _register_benign_and_trap_routes(routes, root, family,
                                        [BENIGN_PUBLIC_POSTS[0], BENIGN_PUBLIC_POSTS[1], FALSE_POSITIVE_TRAPS[0]])
        detail = root + "departments.html?dept=library"
        entry_content = (
            f'<div class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">열린 자료실 부서별 바로가기</div></div>'
            f'<p style="margin-bottom:12px"><strong>{admin_title}</strong></p>'
            '<label for="dept" style="margin-right:8px;font-weight:600">자료실 선택: </label><select id="dept" '
            'onchange="if(this.value)location.href=this.value" style="padding:6px;border:1px solid #cbd5e1;border-radius:4px"><option value="">선택하세요</option>'
            f'<option value="{detail}">도서관</option>'
            f'<option value="{root}posts/benign-01.html">민원여권과</option>'
            f'<option value="{root}posts/benign-02.html">교통안전과</option>'
            f'<option value="{root}posts/trap-gambling-prevention.html">청소년보호과</option>'
            '</select>'
            f'<noscript><a href="{detail}">도서관 자료실</a></noscript>'
            f'</div>'
            + _render_related_board_box(all_sample_posts, root, "도서관 및 문화행정 추천 공고")
        )
        detail_link(detail, entry_content)
    elif family == "finite-number-pages":
        second = root + "list.do?page=2"
        detail = root + "read.do?id=11"
        page1_posts = [all_sample_posts[0], all_sample_posts[1], all_sample_posts[2],
                       all_sample_posts[3], all_sample_posts[4], all_sample_posts[5],
                       all_sample_posts[6], all_sample_posts[7]]
        b_len = len(BENIGN_PUBLIC_POSTS)
        t_len = len(FALSE_POSITIVE_TRAPS)
        p2_benigns = [BENIGN_PUBLIC_POSTS[(family_index * 5 + variant_index + 3 + i) % b_len] for i in range(4)]
        p2_traps = [FALSE_POSITIVE_TRAPS[(family_index * 5 + variant_index + 2 + i) % t_len] for i in range(3)]
        page2_posts = [p2_benigns[0], p2_traps[0], p2_benigns[1], p2_traps[1], p2_benigns[2], p2_traps[2], p2_benigns[3]]
        _register_benign_and_trap_routes(routes, root, family, page1_posts + page2_posts)

        page1_rows = _render_board_table_rows(page1_posts, root, start_index=1)
        entry_content = (
            '<div class="board-list-wrap">'
            '<div class="board-search-bar">'
            '<div class="board-total">총 <strong>16</strong>건 (1/2 페이지)</div>'
            f'<nav aria-label="게시판 페이지 상단 이동" class="pagination" style="margin:0">'
            f'<span class="page-current">1</span><a href="{second}" class="page-link" aria-label="2페이지로 이동">2</a>'
            f'<a href="{second}" class="page-link">&gt;</a>'
            '</nav>'
            '</div>'
            '<table class="board-list"><caption>공개 게시판 1페이지</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{page1_rows}</tbody></table>'
            f'<nav aria-label="게시판 페이지 하단 이동" class="pagination">'
            f'<span class="page-current">1</span><a href="{second}" class="page-link">2</a>'
            f'<a href="{second}" class="page-link">다음 &gt;</a>'
            '</nav>'
            '</div>'
        )
        target_row_p2 = (
            f'<tr><td>9</td><td><span class="badge-pinned">고정공지</span></td>'
            f'<td class="title-col"><a href="{detail}">{admin_title}</a></td>'
            f'<td>{dept_info[0]}</td><td>{date_str}</td></tr>'
        )
        page2_rows = _render_board_table_rows(page2_posts, root, start_index=10)
        second_content = (
            '<div class="board-list-wrap">'
            '<div class="board-search-bar"><div class="board-total">총 <strong>16</strong>건 (2/2 페이지)</div></div>'
            '<table class="board-list"><caption>공개 게시판 2페이지</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{target_row_p2}{page2_rows}</tbody></table>'
            f'<nav aria-label="게시판 페이지 하단 이동" class="pagination">'
            f'<a href="{root}" class="page-link">&lt; 이전</a><a href="{root}" class="page-link">1</a><span class="page-current">2</span>'
            '</nav>'
            '</div>'
        )
        put(root, entry_content)
        put(second, second_content)
        detail_html = _render_post_view("h2", admin_title, target_html, dept_info, date_str, views)
        put(detail, detail_html)
        path = detail
        routes[detail]["list_url"] = second
        for post in page1_posts + page2_posts:
            response = routes[f"{root}posts/{post['id']}.html"]
            response["list_return_urls"] = [root, second]
            if post in page2_posts:
                response["list_url"] = second
    elif family == "listener-next-page":
        detail = root + "board?page=2"
        benign_rows = _render_board_table_rows(all_sample_posts, root, start_index=1)
        entry_content = (
            '<div class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">열린 구정 소식 (총 {len(all_sample_posts) * 3}건, 1페이지)</div></div>'
            f'<p style="margin-bottom:12px"><strong>{admin_title}</strong> (담당: {dept_info[0]})</p>'
            '<table class="board-list"><caption>구정소식 목록</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{benign_rows}</tbody></table>'
            f'<div style="margin-top:16px;text-align:center">'
            f'<button id="next" type="button" class="btn btn-primary" aria-label="다음 페이지">다음 페이지 &gt;</button>'
            f'</div></div>'
        )
        detail_link(detail, entry_content,
                    f'document.querySelector("#next").addEventListener("click",()=>location.assign({json.dumps(detail)}));')
    elif family == "same-url-replacement":
        benign_rows = _render_board_table_rows(all_sample_posts, root, start_index=1)
        card_content = (
            '<section id="rows" class="board-rows">'
            f'<div class="board-search-bar"><div class="board-total">현재 1페이지 공공 안내 (총 {len(all_sample_posts)}건)</div></div>'
            '<table class="board-list"><caption>초기 공공 안내 목록</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{benign_rows}</tbody></table>'
            '</section>'
            '<div style="margin-top:16px;text-align:center"><button id="next" type="button" class="btn btn-primary">다음 페이지</button></div>'
        )
        detail_html = _render_post_view("h1", admin_title, card_content, dept_info, date_str, views)
        put(root, detail_html,
            f'document.querySelector("#next").onclick=function(){{document.querySelector("#rows").innerHTML={json.dumps(target_html)};this.disabled=true;}};')
        steps = [_click("#next")]
    elif family == "delayed-more":
        comments_content = (
            _render_related_board_box(all_sample_posts, root, "관련 행정 안내 및 사전정보공표")
            + '<section id="comments" class="comment-section"><h3 class="comment-header">주민 의견 목록</h3><p>의견을 불러오는 중입니다...</p></section>'
            '<div style="text-align:center;margin-top:12px"><button id="more" type="button" class="btn btn-primary">댓글 더보기</button></div>'
        )
        detail_html = _render_post_view("h1", admin_title, comments_content, dept_info, date_str, views)
        put(root, detail_html,
            f'document.querySelector("#more").onclick=function(){{this.disabled=true;setTimeout(()=>{{document.querySelector("#comments").innerHTML={json.dumps(target_html)};}},180);}};')
        steps = [_click("#more"), {"action": "wait", "ms": 250}]
    elif family == "accessible-name":
        benign_rows = _render_board_table_rows(all_sample_posts, root, start_index=1)
        rows_content = (
            '<section id="rows" class="board-rows">'
            f'<div class="board-search-bar"><div class="board-total">첫 목록 안내 (총 {len(all_sample_posts)}건)</div></div>'
            '<table class="board-list"><caption>열린 행정 안내</caption>'
            '<thead><tr><th style="width:8%">번호</th><th style="width:14%">구분</th>'
            '<th style="width:48%">제목</th><th style="width:15%">담당부서</th><th style="width:15%">작성일</th></tr></thead>'
            f'<tbody>{benign_rows}</tbody></table>'
            '</section>'
            '<div style="text-align:center;margin-top:16px"><button id="more" type="button" class="btn" aria-label="다음 페이지"><span aria-hidden="true">▶ 다음</span></button></div>'
        )
        detail_html = _render_post_view("h1", admin_title, rows_content, dept_info, date_str, views)
        put(root, detail_html,
            f'document.querySelector("#more").addEventListener("click",function(){{document.querySelector("#rows").innerHTML={json.dumps(target_html)};this.disabled=true;}});')
        steps = [_click("#more")]
    elif family == "aria-tabs":
        tabs_content = (
            '<div role="tablist" class="gov-tabs">'
            '<button id="notice-tab" role="tab" type="button" class="tab-btn" aria-controls="panel" aria-selected="true">본문 안내</button>'
            '<button id="comments-tab" role="tab" type="button" class="tab-btn" aria-controls="comments-panel" aria-selected="false">주민 의견</button>'
            '</div>'
            '<section role="tabpanel" id="panel" aria-labelledby="notice-tab" class="tab-panel"><p>기관 이용 및 행정 서비스 안내 본문입니다.</p>'
            + _render_related_board_box(all_sample_posts, root, "유관 정책 안내 및 주요 공지")
            + '</section><section role="tabpanel" id="comments-panel" aria-labelledby="comments-tab" class="tab-panel" hidden></section>'
        )
        detail_html = _render_post_view("h1", admin_title, tabs_content, dept_info, date_str, views)
        put(root, detail_html,
            'function selectTab(comments){'
            'document.querySelector("#notice-tab").setAttribute("aria-selected",String(!comments));'
            'document.querySelector("#comments-tab").setAttribute("aria-selected",String(comments));'
            'document.querySelector("#panel").hidden=comments;document.querySelector("#comments-panel").hidden=!comments;}'
            f'document.querySelector("#comments-tab").onclick=()=>{{document.querySelector("#comments-panel").innerHTML={json.dumps(target_html)};selectTab(true);}};'
            'document.querySelector("#notice-tab").onclick=()=>selectTab(false);')
        steps = [_click("#comments-tab")]
    elif family == "native-details":
        details_body = (
            f'<article class="board-detail-wrap">'
            f'<details><summary id="expand">댓글 펼치기</summary>{target_html}</details>'
            f'</article>'
            + _render_related_board_box(all_sample_posts, root, "관련 행정 소식 및 공지사항")
        )
        detail_html = _render_post_view("h2", admin_title, details_body, dept_info, date_str, views)
        put(root, detail_html)
        steps = [_click("#expand")]
    elif family == "dialog-comments":
        dialog_body = (
            f'<div style="text-align:center;margin-bottom:16px"><button id="open" type="button" class="btn btn-primary">댓글 보기</button></div>'
            f'<dialog id="dialog"><h2 class="comment-header">댓글 목록</h2>{target_html}</dialog>'
            + _render_related_board_box(all_sample_posts, root, "구정 소식 및 주민 알림")
        )
        detail_html = _render_post_view("h1", admin_title, dialog_body, dept_info, date_str, views)
        put(root, detail_html,
            'document.querySelector("#open").onclick=()=>document.querySelector("#dialog").showModal();')
        steps = [_click("#open")]
    elif family == "iframe-document":
        inner = root + "reply/list.jsp?post=5"
        frame_content = (
            f'<iframe id="frame" title="댓글 영역" src="{inner}"></iframe>'
            + _render_related_board_box(all_sample_posts, root, "유관 정보 공개 안내")
        )
        detail_html = _render_post_view("h1", admin_title, frame_content, dept_info, date_str, views)
        put(root, detail_html)
        put(inner, '<article class="comment-card"><div class="comment-meta"><span class="comment-author">주민의견</span></div>' + target_html + '</article>')
        frames = ["#frame"]
    elif family == "iframe-srcdoc":
        inner_html = _page('<div class="comment-card"><h2 class="comment-header">내장 댓글</h2>' + target_html + '</div>')
        frame_content = (
            f'<iframe id="frame" title="내장 게시판" srcdoc="{escape(inner_html, quote=True)}"></iframe>'
            + _render_related_board_box(all_sample_posts, root, "스마트행정 주요 공지")
        )
        detail_html = _render_post_view("h1", admin_title, frame_content, dept_info, date_str, views)
        put(root, detail_html)
        frames = ["#frame"]
    elif family == "nested-iframes":
        first, second = root + "board/frame.html", root + "board/comments.html"
        frame_content = (
            f'<iframe id="outer" title="게시판" src="{first}"></iframe>'
            + _render_related_board_box(all_sample_posts, root, "시정 공지사항")
        )
        detail_html = _render_post_view("h1", admin_title, frame_content, dept_info, date_str, views)
        put(root, detail_html)
        put(first, f'<h2 class="comment-header">게시글 상세</h2><iframe id="inner" title="댓글" src="{second}"></iframe>')
        put(second, target_html)
        frames = ["#outer", "#inner"]
    elif family == "legacy-frame":
        inner = root + "legacy/content.asp?num=3"
        routes[root] = _route(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title></head>'
                             f'<frameset cols="100%"><frame id="frame" name="contents" src="{inner}"></frameset></html>')
        detail_html = _render_post_view("h1", admin_title, target_html + _render_related_board_box(all_sample_posts, root, "공공 행정 안내"), dept_info, date_str, views)
        put(inner, detail_html)
        frames = ["#frame"]
    elif family == "duplicate-dom-ids":
        aside_target = '<aside id="summary"><p id="target">기관 일반 안내</p></aside>'
        main_target = f'<main id="thread">{target_html}</main>'
        detail_html = _render_post_view("h1", admin_title, aside_target + main_target + _render_related_board_box(all_sample_posts, root, "열린 행정 사전정보공표"), dept_info, date_str, views)
        put(root, detail_html)
        selector = "#thread #target"
    elif family == "ancestor-style":
        core = f'<article id="ancestor" style="{style}"><div><p id="target">{escape(text)}</p></div></article>'
        detail_html = _render_post_view("h1", admin_title, core + _render_related_board_box(all_sample_posts, root, "공공 안전 협조 안내"), dept_info, date_str, views)
        put(root, detail_html)
    elif family == "scroll-insertion":
        scroll_content = (
            '<section id="feed" class="board-feed"></section>'
            + _render_related_board_box(all_sample_posts, root, "주민 안내 및 사전공표 자료")
            + '<div style="height:1800px;padding:20px;background:#f8fafc;border:1px dashed #cbd5e1;margin-top:12px">목록 아래 추가 행정 자료 및 세부 지침이 이어집니다. 화면을 아래로 스크롤하세요.</div>'
        )
        detail_html = _render_post_view("h1", admin_title, scroll_content, dept_info, date_str, views)
        put(root, detail_html,
            f'window.addEventListener("scroll",()=>{{document.querySelector("#feed").innerHTML={json.dumps(target_html)};}},{{once:true}});')
        steps = [{"action": "scroll", "frames": []}, {"action": "wait", "ms": 80}]
    elif family == "two-stage-replies":
        nested = '<button id="reply-more" type="button" class="btn-sm">답글 더보기</button><section id="replies" class="replies-box"></section>'
        replies_content = (
            '<button id="comments" type="button" class="btn btn-primary">댓글 보기</button><section id="panel" class="comment-panel"></section>'
            + _render_related_board_box(all_sample_posts, root, "관련 행정 자료")
        )
        detail_html = _render_post_view("h1", admin_title, replies_content, dept_info, date_str, views)
        put(root, detail_html,
            f'document.querySelector("#comments").onclick=function(){{this.disabled=true;document.querySelector("#panel").innerHTML={json.dumps(nested)};'
            f'document.querySelector("#reply-more").onclick=function(){{this.disabled=true;document.querySelector("#replies").innerHTML={json.dumps(target_html)};}};}};')
        steps = [_click("#comments"), _click("#reply-more")]
    elif family == "short-title-detail":
        detail = root + "read.php?no=1&mode=view"
        target_li = f'<li><a href="{escape(detail, quote=True)}" title="게시글 상세보기">글</a> <span> - {admin_title}</span></li>'
        benign_lis = []
        for post in all_sample_posts:
            post_url = f"{root}posts/{post['id']}.html"
            benign_lis.append(f'<li><a href="{escape(post_url, quote=True)}" title="게시글 상세보기">글</a> <span> - {escape(post["title"])}</span></li>')
        entry_content = (
            '<div class="board-list-wrap">'
            f'<div class="board-search-bar"><div class="board-total">간략 제목 게시판 (총 {len(all_sample_posts) + 1}건)</div></div>'
            f'<ol class="board-ol">{target_li}{"".join(benign_lis)}</ol>'
            '<div class="pagination"><span class="page-current">1</span></div>'
            '</div>'
        )
        detail_link(detail, entry_content)
    else:
        raise ValueError(f"Unknown synthetic family: {family}")

    return {
        "id": identity, "difficulty": "medium", "family": family, "group_id": "medium-" + family,
        "description": f"다양한 기관 UI 패턴의 합성 재현(실제 사이트 복제 아님): {family} / {variant}",
        "tags": ["synthetic", "local-only", "ui-compatibility", family, variant],
        "entry": root, "routes": finish_routes(routes, root),
        "checkpoints": [{"path": path, "steps": steps, "targets": [{
            "selector": selector, "frames": frames, "text": text,
            "techniques": techniques, "role": "positive" if techniques else "negative",
        }]}], "expected_statuses": [], "forbidden_requests": [],
    }


def build_cases() -> list[dict]:
    return [_case(index + 1, family, variant)
            for index, (family, variant) in enumerate((family, variant)
                for family in FAMILIES for variant in VARIANTS)]
