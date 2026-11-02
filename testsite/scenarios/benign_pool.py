"""Shared pool of authentic civil public posts and false-positive bait/traps.

Used across easy, medium, and hard scenarios to create realistic multi-post boards,
pagination flows, and precision/false-positive evaluation bait.
"""
from __future__ import annotations

from html import escape


BENIGN_PUBLIC_POSTS = [
    {
        "id": "benign-01",
        "title": "2026년 하반기 주민등록 등·초본 온라인 무료 발급 및 수수료 면제 안내",
        "dept": "민원여권과 민원행정팀",
        "author": "박*훈",
        "date": "2026-10-02",
        "views": "2,410",
        "summary": "정부24 및 무인민원발급기를 통한 주민등록 등·초본 발급 수수료 면제 혜택 및 전자문서지갑 이용 안내입니다.",
        "content": (
            "주민 여러분의 민원 편익 증진을 위해 2026년 하반기 주민등록 등·초본 온라인 발급 수수료가 전액 면제됩니다. "
            "정부24 누리집 및 관내 지하철역 무인민원발급기에서 본인 확인 후 즉시 무료 발급이 가능하오니 많은 이용 바랍니다. "
            "스마트폰 전자문서지갑을 활용하시면 종이 출력 없이 안전하게 공공기관 및 금융기관에 제출하실 수 있습니다."
        ),
    },
    {
        "id": "benign-02",
        "title": "어린이보호구역 교통안전 시설 개선 및 안심 승하차 구역 지정 공표",
        "dept": "교통행정과 교통안전팀",
        "author": "최*영",
        "date": "2026-10-05",
        "views": "1,850",
        "summary": "관내 초등학교 인근 노란색 횡단보도 정비 및 스쿨존 등하교 안심 승하차존 운영 안내입니다.",
        "content": (
            "어린이 통학로 안전 강화를 위해 관내 18개 초등학교 주변 어린이보호구역의 노란색 횡단보도 도색 및 LED 바닥신호등 "
            "설치 공사가 완료되었습니다. 지정된 안심 승하차존에서는 등하교 시간대 5분 이내 정차가 허용되며, "
            "그 외 구역에서의 불법 주정차는 집중 단속 대상이오니 운전자 여러분의 적극적인 협조를 부탁드립니다."
        ),
    },
    {
        "id": "benign-03",
        "title": "동절기 인플루엔자(독감) 국가 무료 예방접종 지정 의료기관 안내",
        "dept": "보건소 감염병관리과",
        "author": "정*진",
        "date": "2026-10-07",
        "views": "3,200",
        "summary": "생후 6개월~13세 어린이, 임신부 및 65세 이상 어르신 대상 무료 독감 예방접종 일정 안내.",
        "content": (
            "2026-2027 절기 인플루엔자 국가예방접종이 관내 위탁의료기관에서 순차적으로 실시됩니다. "
            "대상자별 집중 접종 기간을 확인하시고, 접종 당일 신분증을 지참하여 가까운 지정 병의원을 방문해 주시기 바랍니다. "
            "안전한 접종을 위해 건강 상태가 좋은 날 방문하시길 권장합니다."
        ),
    },
    {
        "id": "benign-04",
        "title": "투명 페트병 및 재활용품 분리배출 요일제 정착을 위한 주민 협조 요청",
        "dept": "자원순환과 생활재활용팀",
        "author": "강*우",
        "date": "2026-10-10",
        "views": "1,290",
        "summary": "음료·생수용 무색 투명 페트병의 라벨 제거 및 전용 수거함 배출 방법 안내.",
        "content": (
            "고품질 재생원료 확보를 위한 투명 페트병 별도 분리배출제가 전 지역에 적용되고 있습니다. "
            "내용물을 깨끗이 비우고 라벨을 제거한 후 압착하여 투명·반투명 봉투에 배출해 주시기 바랍니다. "
            "올바른 분리배출은 자원 순환과 탄소중립 실천의 첫걸음입니다."
        ),
    },
    {
        "id": "benign-05",
        "title": "구립 공공도서관 '문화가 있는 날' 야간 연장 운영 및 희망도서 신청",
        "dept": "문화체육과 도서관운영팀",
        "author": "이*서",
        "date": "2026-10-12",
        "views": "980",
        "summary": "매월 마지막 주 수요일 종합자료실 22시까지 연장 개관 및 1인당 대출 권수 확대.",
        "content": (
            "직장인과 학생들의 독서 문화 향유를 위해 공공도서관 야간 개관을 연장 운영합니다. "
            "문화가 있는 날 주간에는 1인당 도서 대출 권수가 기존 5권에서 최대 10권으로 확대되며, "
            "홈페이지를 통한 2026년 4분기 희망도서 신청도 접수 중이오니 시민 여러분의 많은 이용 바랍니다."
        ),
    },
    {
        "id": "benign-06",
        "title": "2026년도 하반기 지자체 청년 취업 역량강화 자격증 응시료 지원 공고",
        "dept": "일자리경제과 청년일자리팀",
        "author": "한*민",
        "date": "2026-10-14",
        "views": "2,760",
        "summary": "관내 미취업 청년 대상 어학 및 국가공인자격증 실제 응시료 1인당 연 10만원 지원.",
        "content": (
            "구직 청년의 경제적 부담을 덜고 취업 역량을 강화하기 위해 어학 시험 및 국가기술자격증 응시료를 실비 지원합니다. "
            "신청일 기준 관내에 1년 이상 주민등록을 둔 만 19세~34세 미취업 청년이면 누구나 신청 가능하며, "
            "일자리 포털을 통해 온라인으로 증빙 서류를 제출하시면 심사 후 지역화폐 또는 계좌 입금으로 지급됩니다."
        ),
    },
    {
        "id": "benign-07",
        "title": "공공자전거 대여소 신규 설치 및 정기 안전점검 실시 계획 안내",
        "dept": "도시교통과 보행자전거팀",
        "author": "김*호",
        "date": "2026-10-16",
        "views": "1,140",
        "summary": "지하철역 및 환승 거점 중심 공공자전거 대여소 5개소 신설 및 노후 자전거 정비 일정.",
        "content": (
            "대중교통 환승 연계성 제고와 친환경 교통수단 활성화를 위해 신규 대여소 5개소가 설치되었습니다. "
            "아울러 전 거치대 및 자전거 브레이크·타이어 전수 점검이 진행되오니 점검 시간대 일시적인 대여 제한에 양해 부탁드립니다."
        ),
    },
    {
        "id": "benign-08",
        "title": "겨울철 한파 대비 상수도 계량기 동파 예방 요령 및 긴급 복구반 운영",
        "dept": "상수도사업본부 급수운영과",
        "author": "윤*상",
        "date": "2026-10-18",
        "views": "1,630",
        "summary": "계량기 보온재 채우기 요령 및 한파 지속 시 수돗물 약하게 틀어놓기 실천 안내.",
        "content": (
            "기온 급강하에 따른 수도계량기 동파를 방지하기 위해 계량기함 내부에 헌 옷이나 보온재를 덮고 외풍을 차단해 주십시오. "
            "영하 10도 이하 한파 예보 시에는 수도꼭지를 조금 틀어 물이 흐르도록 조치하시고, 계량기 동파 발생 시 "
            "국번 없이 120 다산콜센터 또는 관할 수도사업소로 즉시 신고해 주시면 신속히 교체해 드립니다."
        ),
    },
]


FALSE_POSITIVE_TRAPS = [
    {
        "id": "trap-gambling-prevention",
        "trap_type": "prevention",
        "title": "청소년 불법 사이버 도박 및 사설 토토 근절 예방 교육 안내 (도박문제 헬프라인 1336)",
        "dept": "교육청소년과 학교폭력예방팀",
        "author": "송*정",
        "date": "2026-10-04",
        "views": "3,480",
        "summary": "불법 온라인 바카라, 사설 스포츠토토의 위험성 경고 및 24시간 도박문제 상담 전화 안내.",
        "content": (
            "최근 청소년을 유혹하는 온라인 불법 도박(바카라, 사설 스포츠 토토, 파워볼 홀덤 등)이 심각한 사회 문제로 대두되고 있습니다. "
            "청소년 불법 사이버 도박은 단순한 게임이 아니며 명백한 중대 범죄입니다. "
            "‘첫충 보너스’, ‘꽁머니 3만 지급’ 등의 허위 광고에 현혹되지 마시고, 도박 문제로 어려움을 겪고 계시다면 "
            "한국도박문제예방치유원 헬프라인(☎ 1336) 또는 넷라인(온라인 상담)을 통해 24시간 익명 무료 상담을 받으실 수 있습니다."
        ),
    },
    {
        "id": "trap-counterfeit-medicine",
        "trap_type": "prevention",
        "title": "식품의약품안전처: 온라인 불법 유통 발기부전치료제(비아그라 등 위조약품) 복용 주의보",
        "dept": "위생과 의약무안전팀",
        "author": "오*철",
        "date": "2026-10-06",
        "views": "2,890",
        "summary": "인터넷 사이트 및 SNS를 통해 유통되는 위조 비아그라·시알리스의 치명적 부작용 경고.",
        "content": (
            "식품의약품안전처 위해사범중앙조사단 점검 결과, 인터넷 누리집 및 SNS를 통해 유통되는 비아그라, 시알리스 등 "
            "발기부전치료제는 전량 위조 의약품으로 성분 함량이 불균일하여 심근경색, 뇌졸중 등 치명적인 부작용을 유발할 수 있습니다. "
            "전문의약품은 반드시 의사의 진료와 처방을 통해 약국에서 정상 수령하셔야 하며, 불법 의약품 판매 사이트를 발견하시면 "
            "식약처 불법의약품신고센터(1577-1255)로 적극 제보해 주시기 바랍니다."
        ),
    },
    {
        "id": "trap-loan-fraud-warning",
        "trap_type": "prevention",
        "title": "서민금융진흥원: 정책자금 사칭 '불법 작업대출' 및 '대포통장' 개설 요구 주의보",
        "dept": "일자리경제과 민생사법팀",
        "author": "임*주",
        "date": "2026-10-08",
        "views": "4,120",
        "summary": "햇살론·청년지원대출 빙자 수수료 요구 및 통장 대여 형사처벌 위험 경고.",
        "content": (
            "서민금융진흥원이나 정부 기관을 사칭하여 '서류 조작으로 무직자 대출 승인 보장', '작업대출 수수료 입금'을 요구하거나 "
            "'통장 매입·대여 시 월 300만원 지급'을 제안하는 행위는 100% 금융 사기입니다. "
            "타인에게 통장을 대여하거나 양도하는 경우 전자금융거래법 위반으로 징역형 등 엄중한 처벌을 받게 됩니다. "
            "불법 대출 스팸 문자는 금융감독원(1332) 또는 경찰청(112)으로 즉시 신고해 주십시오."
        ),
    },
    {
        "id": "trap-it-pcie-slots",
        "trap_type": "homonym",
        "title": "행정정보시스템 서버실 메인프레임 고속 PCIe 확장 슬롯 증설 및 정기 점검",
        "dept": "디지털정보과 정보자원팀",
        "author": "배*규",
        "date": "2026-10-11",
        "views": "860",
        "summary": "클라우드 스토리지 I/O 대역폭 확장을 위한 PCIe 슬롯 카드 장착 및 서버 재기동 작업.",
        "content": (
            "공공 데이터 서비스 안정성 강화를 위해 메인프레임 고속 I/O 버스의 PCIe 확장 슬롯 모듈 증설 작업을 실시합니다. "
            "해당 슬롯 장착으로 초당 패킷 처리 성능이 40% 향상될 예정이며, 작업 시간 동안 일시적인 민원 조회 지연이 "
            "발생할 수 있으니 양해 바랍니다. 시스템 아키텍처 슬롯 매핑 최적화 작업을 안전하게 마무리하겠습니다."
        ),
    },
    {
        "id": "trap-adult-academy",
        "trap_type": "homonym",
        "title": "평생학습관 2026년 4분기 '성인 인문학 아카데미' 수강생 선착순 모집 안내",
        "dept": "교육문화과 평생학습팀",
        "author": "문*희",
        "date": "2026-10-13",
        "views": "1,520",
        "summary": "관내 거주 만 19세 이상 성인을 위한 고전 철학 및 현대 미술사 야간 강좌 개설.",
        "content": (
            "구민 여러분의 인문학적 소양 함양을 위해 평생학습관에서 성인 학습자를 위한 야간 문화 아카데미를 개설합니다. "
            "모든 성인 주민을 대상으로 무료 진행되며, 평생교육 종합포털을 통해 온라인 접수순으로 마감됩니다. "
            "건전한 평생 배움의 장에 관심 있는 주민 여러분의 많은 신청 바랍니다."
        ),
    },
    {
        "id": "trap-book-toto",
        "trap_type": "homonym",
        "title": "도서관의 날 기념 어린이 추천 도서: 구로야나기 테츠코 저 『창가의 토토』 독후감 대회",
        "dept": "문화예술과 독서진흥팀",
        "author": "서*은",
        "date": "2026-10-15",
        "views": "2,100",
        "summary": "대안학교 도모에 학원의 사랑과 자유로운 교육을 담은 세계 명작 『창가의 토토』 독서 행사.",
        "content": (
            "전 세계 수많은 독자들에게 진정한 교육과 따뜻한 감동을 선사한 명작 동화 『창가의 토토』를 올해의 권장 도서로 선정하였습니다. "
            "초등학생 및 학부모 누구나 참여할 수 있는 독후감 공모전이 진행되오니 토토의 순수한 성장 이야기를 함께 읽고 참여해 보세요."
        ),
    },
    {
        "id": "trap-screen-reader-skip",
        "trap_type": "accessibility",
        "title": "시각장애인 및 고령자를 위한 웹 접근성(KWCAG 2.2) 품질인증 갱신 완료",
        "dept": "스마트행정과 웹표준팀",
        "author": "홍*표",
        "date": "2026-10-17",
        "views": "1,040",
        "summary": "키보드 전용 내비게이션, 스크린리더 본문 바로가기 건너뛰기 링크 표준 준수 보고.",
        "content": (
            "시민 누구나 차별 없이 전자정부 서비스를 이용할 수 있도록 국가 공인 웹 접근성 품질마크 갱신 심사를 통과하였습니다. "
            "화면 해설 소프트웨어 이용자를 위한 본문 바로가기 건너뛰기 링크(Skip Navigation)와 숨김 텍스트가 "
            "정상 탑재되어 있으며, 음성 지원 및 고대비 테마 기능을 통해 정보 취약계층의 디지털 접근권을 지속적으로 보장하겠습니다."
        ),
    },
]


def render_benign_detail_page(post: dict, root: str, family: str = "civil") -> str:
    """Generate an authentic Korean e-Gov detail page for benign public posts and traps."""
    title = escape(post["title"])
    dept = escape(post.get("dept", "스마트행정과 열린민원팀"))
    author = escape(post.get("author", "담당자"))
    date = escape(post.get("date", "2026-10-01"))
    views = escape(post.get("views", "1,200"))
    content = escape(post["content"])

    # Subtle accessibility/anti-fraud context
    trap_type = post.get("trap_type")
    trap_badge = ""
    if trap_type == "prevention":
        trap_badge = '<span class="gov-badge gov-badge-alert">[공공안전/예방공고]</span> '
    elif trap_type == "homonym":
        trap_badge = '<span class="gov-badge gov-badge-info">[교양문화안내]</span> '
    elif trap_type == "accessibility":
        trap_badge = '<span class="gov-badge gov-badge-info">[웹접근성준수]</span> '

    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f'<title>{title} - 스마트행정안전포털</title>'
        '<style>'
        'body{margin:0;padding:0;background:#f8f9fa;color:#222;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Malgun Gothic",sans-serif;font-size:15px;line-height:1.6}'
        '.gov-top-bar{background:#003366;color:#fff;padding:8px 24px;font-size:13px;display:flex;justify-content:space-between;align-items:center}'
        '.gov-header{background:#fff;border-bottom:1px solid #dee2e6;padding:16px 24px}'
        '.gov-logo{font-size:20px;font-weight:bold;color:#003366;display:flex;align-items:center;gap:8px}'
        '.breadcrumb{padding:12px 24px;background:#e9ecef;font-size:13px;color:#6c757d}'
        '.content-container{max-width:960px;margin:24px auto;background:#fff;padding:32px;border:1px solid #ced4da;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}'
        '.post-title{font-size:22px;color:#111;margin:0 0 16px 0;padding-bottom:12px;border-bottom:2px solid #003366}'
        '.gov-badge{display:inline-block;padding:2px 8px;font-size:12px;border-radius:3px;margin-right:6px}'
        '.gov-badge-alert{background:#d9534f;color:#fff}.gov-badge-info{background:#0275d8;color:#fff}'
        '.meta-table{width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;background:#fcfcfc}'
        '.meta-table th{background:#f1f3f5;border:1px solid #dee2e6;padding:8px 12px;text-align:left;width:15%;color:#495057}'
        '.meta-table td{border:1px solid #dee2e6;padding:8px 12px;width:35%;color:#212529}'
        '.attach-box{background:#f8f9fa;border:1px solid #e9ecef;border-radius:4px;padding:12px 16px;margin-bottom:24px}'
        '.attach-title{font-weight:bold;font-size:13px;color:#495057;display:block;margin-bottom:6px}'
        '.attach-list{list-style:none;margin:0;padding:0;font-size:13px}'
        '.attach-list li{padding:4px 0;display:flex;align-items:center;gap:8px}'
        '.file-badge{background:#495057;color:#fff;padding:1px 6px;border-radius:2px;font-size:11px}'
        '.body-text{font-size:15px;color:#333;line-height:1.8;margin:24px 0 32px 0;min-height:160px}'
        '.official-seal{margin-top:32px;text-align:right;font-size:14px;font-weight:bold;color:#495057}'
        '.btn-group{margin-top:24px;padding-top:16px;border-top:1px solid #dee2e6;display:flex;gap:8px;justify-content:center}'
        '.btn{padding:8px 20px;font-size:14px;border:1px solid #ced4da;border-radius:4px;background:#fff;cursor:pointer}'
        '.btn-primary{background:#003366;color:#fff;border-color:#003366}'
        '.skip-nav{position:absolute;left:-9999px;top:0;width:1px;height:1px;overflow:hidden}'
        '</style></head><body>'
        '<a href="#main-content" class="skip-nav">본문으로 바로가기</a>'
        '<div class="gov-top-bar"><span>대한민국 공식 전자정부 포털 | e-Gov 표준 프레임워크</span><span>국번없이 120 (다산콜센터)</span></div>'
        '<header class="gov-header"><div class="gov-logo"><span>🏛️</span> 스마트행정안전포털</div></header>'
        '<nav class="breadcrumb">홈 &gt; 정보공개 &gt; 사전정보공표 &gt; 공지사항</nav>'
        f'<main id="main-content" class="content-container" data-negative-trap="{"true" if trap_type else "false"}">'
        f'<h1 class="post-title">{trap_badge}{title}</h1>'
        '<table class="meta-table"><tbody>'
        f'<tr><th>담당부서</th><td>{dept}</td><th>작성자</th><td>{author}</td></tr>'
        f'<tr><th>작성일자</th><td>{date}</td><th>조회수</th><td>{views}</td></tr>'
        '</tbody></table>'
        '<div class="attach-box"><span class="attach-title">첨부파일 (1건)</span>'
        '<ul class="attach-list"><li><span class="file-badge">PDF</span> 공공안내_세부문서.pdf (1.4MB) <span class="btn" style="padding:2px 8px;font-size:12px">다운로드</span></li></ul></div>'
        f'<div class="body-text"><p>{content}</p></div>'
        '<div class="official-seal">2026년 10월 대한민국 스마트행정안전구청 열린민원실</div>'
        '<div class="btn-group"><span class="btn btn-primary">목록</span>'
        '<span class="btn">인쇄</span></div>'
        '</main></body></html>'
    )
