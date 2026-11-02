"""불법광고 판별 사전.

은닉 기법이 쓰였다는 사실만으로는 위반이 아니다. 스킵내비게이션이나
스크린리더용 요약문도 화면에서 감춰지기 때문이다. 정확도 배점을 지키려면
'감춰졌다' + '광고다' 두 조건을 모두 만족할 때만 보고해야 한다.
"""

# 단독으로 나와도 광고로 볼 수 있는 표현 (도박·성매매 광고에서만 쓰는 은어와 '○○사이트' 꼴)
STRONG = [
    "먹튀", "안전놀이터", "메이저놀이터", "메이저사이트", "사설토토", "첫충", "입플", "꽁머니", "무료머니",
    "총판모집", "가입쿠폰", "가입코드", "라이브카지노", "온라인카지노",
    "토토사이트", "카지노사이트", "바카라사이트", "슬롯사이트", "홀덤사이트", "파워볼사이트",
    "bet365", "megabet",
    "조건만남", "출장안마", "오피스텔후기",
    # 성인 방송·음란물 (섹파: 성관계 상대 모집)
    "성인라방", "19라방", "섹파", "무료야동", "국산야동",
    # 출장 성매매 (출장안마와 같은 꼴)
    "출장마사지", "출장샵", "출장홈타이", "출장오피",
    # 영문 도박 광고
    "onlinecasino", "casinosite", "totosite",
    # 유흥(오피) 사이트 이름 (공공·대학 누리집 게시판 스팸에서 확인)
    "밤의전쟁", "오피가자", "오피가니", "달림가이드", "오피맵", "오피런", "오피왕", "헬로밤",
    # 외국어 도박·성인 스팸 (인도네시아 슬롯·복권, 중국어·일본어 온라인 카지노, 영문 성인 만남)
    "slotgacor", "maxwin", "togel", "judibola", "situsslot",
    "网上赌场", "真人百家乐", "送彩金", "オンラインカジノ", "入金不要ボーナス",
    "sexdating", "adultwebcam", "hotsingles",
    # 검증 커뮤니티 이름·사설 도박 브랜드·유흥 업소 (2026-10-19, tools/lexicon_candidates.py 시험 통과분.
    # 먹튀·꽁머니를 품은 말은 점수는 같고, 두 낱말을 끄더라도 잡히게 둔다)
    "먹튀검증", "먹튀보증", "먹튀사이트", "먹튀폴리스", "먹튀자랑", "먹튀제보", "꽁머니사이트",
    "원엑스벳", "1xbet", "텐텐벳", "핀벳88",
    "출장아가씨", "오피사이트", "건마사이트",
]

# 도박 종목 이름. 광고에 늘 나오지만 정상 문서에도 나온다
# (동화 '창가의 토토', 카지노업 영업준칙, 바카라 게임규칙, 홀덤펍 단속 보도자료 등).
# 단독으로는 기준에 못 미치고, 다른 단서가 하나라도 붙어야 광고로 본다.
TOPIC = [
    "카지노", "바카라", "슬롯", "토토", "홀덤", "에볼루션", "배팅", "베팅", "환전", "파친코", "잭팟",
    "casino", "baccarat", "slot", "toto", "jackpot", "betting",
    "성인용품", "야동",
    # '음란'·'몸캠'은 신고·피해 주의 공고에도, '벗방'(노출 방송)은 국세청 탈세 적발 보도에도 나온다
    "음란", "성인방송", "몸캠", "벗방",
    # 성매매 업소 이름. 단속·적발 보도에도 나오므로 연락처·주소가 붙어야 광고로 본다
    # ('건마'는 '사건마다', '오피'는 '오피스'와 겹쳐 넣지 않는다.
    # '안마방'·'오피방'은 단속 보도에 여럿이 나란히 나와 점수가 겹치므로 넣지 않는다)
    "휴게텔", "키스방", "립카페", "룸싸롱", "풀싸롱", "셔츠룸",
    # 불법 사행성 게임(릴게임). '바다이야기 사태' 보도·단속 공고에도 나오므로 종목 이름으로 둔다
    # ('황금성'은 중국집 상호와 겹쳐 넣지 않는다)
    "바다이야기", "릴게임", "오션파라다이스",
    # 스포츠 도박 은어 (단폴: 한 경기만 거는 베팅)
    "단폴",
    # 성인물. '성인영상물 등급 분류' 안내에도 나온다
    "성인영상", "섹스영상", "포르노", "야설", "블랙잭",
    # 불법 스트리밍·웹툰·토렌트 사이트 (저작권 보호 안내·보도에도 나오므로 다른 단서가 붙어야 광고)
    "누누티비", "뉴토끼", "툰코", "토렌트",
    # 1인 마사지 업소, 사다리·픽 도박
    "1인샵", "스웨디시", "파워사다리", "픽스터",
    # 2026-10-19 시험 통과분 (홀덤 영문 표기, 양방 베팅, 성인 영상물·유흥 업소 이름)
    "holdem", "양방베팅", "토킹바", "섹스비디오", "포르노비디오",
]

# 불법 거래를 가리키지만 정상 공고(예방 교육·피해 주의 안내)에도 나오는 표현.
# 단독으로는 기준에 못 미치고, 판매·연락처·금액 같은 유인 신호가 붙어야 광고로 본다.
# (2025년 보도된 공공 누리집 불법광고에 마약 거래·대포통장·돈세탁·고액 알바 광고가 섞여 있었다)
MEDIUM = [
    # 마약
    "필로폰", "대마초", "케타민", "엑스터시", "코카인", "물뽕", "빙두", "작대기", "아이스작대기",
    "떨액상", "대마젤리",
    # 통장·자금
    "대포통장", "통장매입", "통장임대", "통장삽니다", "법인통장", "돈세탁", "자금세탁",
    # 불법 대출
    "작업대출", "내구제", "무직자대출", "당일대출", "신불자대출",
    "법인장", "개인통장", "통장판매", "통장구매", "통장대여",
    # 마약 은어 (실제 공공 누리집 게시판 광고에서 확인)
    "떨액", "브액", "대마액상", "떨구매", "떨판매",
    # '대마' 단독은 삼베(안동포)·대마 재배 안내에도 나오므로 거래 표현과 붙은 꼴만 본다
    "대마판매", "대마구매", "대마구입", "대마사는곳", "대마파는곳", "대마구하는곳",
    # 불법 고수익 알바
    "고액알바", "꿀알바", "고수익알바", "당일지급알바", "재택부업", "단기고수익",
    # 불법 도박 유입 (스포츠 중계 미끼, 접속 주소 안내, 회원 DB 거래)
    "파워볼", "접속주소", "빠른주소", "보증업체", "구글검색",
    "토토디비", "토토db", "카지노디비", "카지노db", "디비팝니다", "db팝니다",
    # 대포폰·대포유심 (타인 명의 개통 휴대폰 거래. 달림폰·폰테크는 거래 은어)
    # ('선불유심'은 알뜰폰 안내에도 쓰이는 정상 용어라 넣지 않는다)
    "대포폰", "대포유심", "대포선불폰", "달림폰", "폰테크", "휴대폰개통대출",
    # 미등록 대부업 광고 표현
    "급전대출", "개인돈대출", "일수대출", "무서류대출", "무방문대출", "소액급전",
    # 발기부전 치료제 불법 판매 (식약처 단속·주의 안내에도 나오므로 판매·연락처가 붙어야 광고)
    "비아그라", "시알리스", "레비트라", "카마그라", "발기부전치료제", "viagra", "cialis", "levitra",
    # 먹는 낙태약 불법 판매 (식약처 단속 안내에도 나온다)
    "미프진", "낙태약",
    # 불법 흥신소 (개인정보 불법 수집·미행)
    "흥신소", "심부름센터", "사람찾기",
    # 휴대폰 소액결제·신용카드 현금화 (불법 대부. 금융감독원 주의 안내에도 나온다)
    "현금화", "카드깡", "상품권매입", "소액결제현금화", "상품권현금화",
    # 신분증·서류 위조
    "신분증위조", "위조신분증", "면허증위조", "졸업증명서위조",
    # 검색엔진 순위 조작 판매
    "백링크", "구글상위노출",
    # 성인 라이브 방송 유입. 지역 특산물 라이브커머스('복분자 라방 판매')에도 쓰여 종목 이름보다 약하게 둔다
    "라방",
    # 발기부전 치료제 (조루 치료제 포함)
    "프릴리지",
    # 불법 촬영물 판매
    "유출영상", "몰카영상", "도촬영상", "몰래카메라영상",
    # 불법 스포츠 중계 사이트 (도박 사이트로 끌어들이는 미끼). 방송사 편성 안내('KBS 스포츠중계')·행사 생중계
    # 안내('체육대회를 유튜브로 무료 실시간 중계합니다')와 겹치지 않게 해외 리그 이름을 붙인 꼴만 둔다
    "해외축구중계", "epl중계", "nba중계", "mlb중계",
    # 수면제·스테로이드·마약 (식약처 오남용 주의 안내에도 나온다)
    "졸피뎀", "스테로이드", "아나바", "mdma", "엘에스디",
    # 명품 위조품, 계좌 대여
    "레플리카", "계좌대여",
    # 청소년 대리입금(고금리 소액 대출), 본인인증·계정·개인정보 거래
    "대리입금", "본인인증대행", "문자인증대행", "계정판매", "아이디대량", "대량판매",
    "회원디비", "코인디비", "주식디비", "개인정보db",
    # SNS 조작, 대필, 유료 도박 픽, 투자 사기
    "팔로워구매", "조회수판매", "구독자판매", "좋아요늘리기",
    "논문대필", "과제대행", "자기소개서대필", "자소서대필",
    "유료픽", "확정수익",
    # 2026-10-19 시험 통과분 (마약류 신종 표기, 일변 대출, 선불유심 내구제, 이용료·상품권 현금화.
    # 내구제·현금화를 품은 말은 점수는 같고 낱말이 꺼져도 잡히게 둔다)
    "액상대마", "마리화나", "내구제대출", "선불유심내구제",
    "정보이용료현금화", "콘텐츠이용료현금화", "구글기프트카드현금화",
]

# 단독으로는 약하고, 둘 이상 겹칠 때 광고로 보는 표현
WEAK = [
    "텔레그램", "상담", "지급", "쿠폰", "코드", "추천", "순위표", "바로가기",
    "가입", "체험", "이벤트", "검증", "주소", "총판", "모집", "보너스",
    "놀이터", "업체", "순위", "문의", "입금", "출금", "머니", "충전",
    "telegram", "vip", "promo", "event", "free",
    # 거래를 권하는 말 (MEDIUM 과 겹칠 때 의미가 생긴다)
    "팝니다", "삽니다", "매입", "직거래", "던지기", "비대면", "당일", "고수익", "선입금", "즉시",
    "해드립니다", "대행",
    # 불법 의약품·성인물·대출 광고에 붙는 말
    "비밀배송", "무삭제", "무직자", "신불자",
    "판매", "구매", "구입", "대여", "파는곳", "사는곳", "구하는곳", "구입방법", "구매방법",
    "무료", "실시간", "중계", "티비", "스포츠중계", "무료중계",
    # 도박 롤링(충전액 대비 배팅 조건)·투자 사기의 수익 약속
    "롤링", "수익보장", "원금보장",
    # 불법 투자 리딩방. 금융위 주의 안내·검거 보도에 훨씬 많이 나와 약하게 두고, 수익 약속·연락처와 겹쳐야 광고로 본다
    "리딩방",
    # '가입금'이 가입·입금으로 따로 세지 않게 한 낱말로 둔다
    "가입금",
    # 대리입금·불법 의약품 광고에 붙는 말
    "빌려드림", "수고비", "디엠", "cheap", "buy",
    # 2026-10-19 시험 통과분 (도박 사이트 주소 안내·배송 표현·검증 업체 홍보)
    "당일배송", "총알배송", "익명배송", "고배당", "죽장", "평생주소", "평생도메인", "우회주소", "최신주소",
    "오픈카톡", "고페이", "월변", "인증업체", "위반주소",
]

# 정상 문맥 패턴을 활성화하는 단서. 단어 단독으로 점수를 깎지는 않는다.
CAUTION = ["신고", "처벌", "예방", "주의", "피해", "사기", "금지", "범죄", "단속", "근절", "캠페인",
           "교육", "상담센터", "경찰", "불법", "도박문제", "중독",
           # 광고 문구를 따옴표로 인용해 경고하는 안내문 ('…라는 광고 문구에 속지 마세요')
           "속지", "광고문구",
           # 2026-10-19 시험 통과분 (광고에 섞어 쓰는 문구로 점수가 깎여 미탐이 나지 않는지 시험했다)
           "계도", "경고", "주의사항", "당부", "해악", "부작용", "오남용",
           "불법도박", "불법사금융", "사이버범죄", "합동단속", "집중단속",
           # 단속·수사 보도 ('가짜 비아그라 판매 성인용품점 적발', '코인 리딩방 일당 검거').
           # '차단'은 광고에도 '차단 걱정 없는 주소'로 쓰여 넣지 않는다
           *("적발", "검거", "기소", "구속", "덜미", "실태", "유혹", "미끼", "주의보", "수사", "송치", "혐의"),
           # 도박 피해 이야기 ('먹튀를 당했어요', '돈을 잃는 과정', '빚을 지게 됐다')
           "당했", "당해서", "잃", "빚"]


import functools
import re

from normalize import deleet_all, normalize
from context_evidence import assess, discount, OFFER, OFFER_LURE, REPORTED, LIVE_ACTION, VICTIM_FAMILIES
from combo_rules import COMPOUNDS, SEARCH_BADGE, compound_matches

# 광고 문구에 반복적으로 따라붙는 유인 신호
# 텔레그램 표기 변형: 텔레·텔래·텔그·탤레·텔그램, '텔' 바로 뒤에 아이디 (텔richdb888, 텔@advjang)
# '텔레그램' 낱말만 있는 글(텔레그램 범죄 보도·주의 안내)은 연락처가 아니다. 뒤에 아이디가 붙어야 한다.
_CONTACT = re.compile(r"(@[a-z0-9_]{4,}|t\.me/|텔레(?!그램)|텔래|텔그|탤레|탤그|"
                      r"텔레그램\s*[@:]?\s*[a-z][a-z0-9_]{3,}|(?<!호)텔\s*[@:]?\s*[a-z][a-z0-9_]{3,}|"
                      r"텔ㄹ\s*[@:]?\s*[a-z][a-z0-9_]{3,}|"
                      r"카톡|010\d{7,8})")
# 메신저 아이디가 붙은 연락처만 (전화번호·'카톡' 낱말은 제외)
_MESSENGER = re.compile(r"(@[a-z0-9_]{4,}|t\.me/|텔레(?!그램)|텔래|텔그|탤레|탤그|(?<!호)텔\s*[@:]?\s*[a-z][a-z0-9_]{3,})")
# 필로폰(시원한술·찬술)·케타민(케이) 판매 은어 + 판매 낱말. 정규화한 글에서 찾는다
_SLANG_SALE = re.compile(r"(?:시원한술|찬술)(?:삽니다|팝니다|구하는곳|파는곳|구매|구입|판매)|케이(?:삽니다|팝니다|구하는곳|파는곳)")
# 주소·전자우편 낱말은 영숫자 덩어리의 시작에서만 찾는다. 덩어리 중간에서 시작한 일치는 시작에서도
# 찾아지므로 결과는 같고, 띄어쓰기 없는 긴 값(목포 누리집 og:description 의 23만 자 base64)에서
# 위치마다 끝까지 다시 훑어 판정이 몇 분씩 멈추던 일이 없어진다
_URLISH = re.compile(r"(https?://|www\.|\.com|\.net|bit\.ly|"
                     r"(?<![a-z0-9-])[a-z0-9-]+\.(kr|cc|vip|shop|top|xyz|bet|win|club|site|online|io|me|link))")
_PROMO = re.compile(r"(\d{1,3}%|\d+만원|\d+원)")
# 공공기관 주소는 광고가 끌어들이는 '외부 주소'가 아니다 (메뉴·안내문의 www.gov.kr 등)
_PUBLIC_HOST = re.compile(r"(https?://)?(?<![a-z0-9.-])[a-z0-9.-]*\.(go\.kr|korea\.kr|mil\.kr|ac\.kr|re\.kr|gov)\b/?")
_PUBLIC_EMAIL = re.compile(r"(?<![a-z0-9.!#$%&'*+/=?^_`{|}~-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9-]+\.)*"
                           r"(?:go\.kr|korea\.kr|mil\.kr|ac\.kr|re\.kr|gov)(?![\w.-])", re.I)
# 문구 자체가 안내·예방 목적을 밝힌 경우만 쓴다. '주의' 한 단어로 광고를 면제하지 않는다.
_PREVENTION = re.compile(r"예방(?:및신고)?(?:교육|수칙|안내|캠페인)|피해예방|"
                         r"광고.{0,100}(?:현혹되지|속지마)|불법.{0,40}(?:근절|신고(?:하는)?(?:방법|안내))")
# 병원·약국·식약처의 가격·처방 안내 (정규화한 글에서 찾는다)
_HEALTH_NOTICE = re.compile(r"비급여|진료비|처방(?:이|전이)필요|전문의약품|의사(?:의)?처방|약사(?:와|에게)상담|의약품안전")
_DIRECT_LURE = re.compile(r"(?:가입코드|추천코드)[a-z0-9]{3,}|"
                          r"(?:지금|즉시|바로)(?:가입|접속|입금)|구글검색")
# 동음어가 쓰인 부분만 빼고 다른 위치의 광고 표현은 계속 판정한다.
# 스포츠토토 판매점은 합법 복권 판매소다 (국민체육진흥공단 판매점 모집 공고)
_NON_GAMBLING = {"토토": ("창가의토토", "스포츠토토판매점", "토토판매점"),
                 "슬롯": ("주차슬롯", "메모리슬롯", "확장슬롯", "시간슬롯", "pci슬롯")}

# A semantic exception covers every topic in the text and only the listed mild words.
# Contacts, independent strong/transactional words and bonuses keep the advertising route.
NORMAL_CONTEXTS = (
    (("슬롯", "slot"), ("예약", "시간대", "메모리", "확장슬롯", "카드슬롯", "pcie", "하드웨어"),
     {"무료", "상담", "이벤트", "바로가기"}),
    (("토토", "toto"), ("독후감", "권장도서", "추천도서", "명작동화", "동화책", "동화속", "독서", "도서관", "책놀이"),
     {"가입", "무료", "추천"}),
    (("바카라", "baccarat"), ("유리잔", "크리스털", "크리스탈", "유리공예", "소장품", "작품해설"),
     {"무료", "체험"}),
    (("카지노", "casino"), ("통계", "현황", "산업분류", "종사자"), {"무료", "바로가기", "코드"}),
    (("야동",), ("마을", "행정동", "법정동", "지명"), {"무료"}),
    (("카지노", "casino"), ("생계", "생활고", "생활이어려운", "위기가구", "복지", "심리상담"), {"무료", "상담"}),
)

STRONG_W, TOPIC_W, TOPIC_MORE_W, MEDIUM_W, MEDIUM_MORE_W, WEAK_W, SIGNAL_W, THRESHOLD = 1.0, 0.7, 0.4, 0.6, 0.3, 0.3, 0.35, 1.0
# 품목 낱말에 거래 표현이 띄어쓰기 없이 바로 붙은 꼴('졸피뎀구매')의 가점. 태그 스팸 제목은
# 이 한 낱말뿐이라 품목(0.6)+거래(0.3)로는 기준에 조금 못 미친다. 띄어 쓴 안내문('졸피뎀 구매 시')은 해당 없음
ATTACHED_W = 0.15
# MEDIUM 가운데 일상어와 같은 꼴인 낱말('작대기 하나로 그리기', '자산 현금화 상담', '스테로이드 연고').
# 거래 표현이 바로 붙었거나, 연락처·문자 위장이 함께 있을 때만 품목으로 센다.
# (사람찾기·라방처럼 정상 용도가 있어도 사람이 볼 만한 낱말은 precision_policy.BROAD 가 검토 후보로 남긴다)
EVERYDAY = {"작대기", "현금화", "스테로이드", "레플리카", "대량판매", "상품권매입"}
_ATTACHED_DEAL = re.compile(r"판매|팝니다|삽니다|구매|구입|매입|파는곳|사는곳|구하는곳|직거래|대행|해드립니다")
# 띄어 쓴 낱말 뒤에 광고가 흔히 바로 붙이는 꼬리 ('안전 놀이터추천', '카 지 노사이트')
_GLUE = ("사이트",)
# 처방이 필요한 의약품. 이름만으로는 식약처 주의 안내·단속 보도와 가를 수 없어 품목으로 둔다.
# 광고는 '처방전 없이·정품·최저가·당일 배송'처럼 처방을 건너뛴 구매를 권한다 (판매 유도).
# 안내문은 같은 낱말에 '구입할 수 없습니다·불법 판매 주의'처럼 금지·경고를 붙인다 (경고 안내).
RX_DRUGS = {"비아그라", "시알리스", "레비트라", "카마그라", "발기부전치료제", "viagra", "cialis", "levitra",
            "미프진", "낙태약", "프릴리지", "졸피뎀"}
_RX_SALE = re.compile(r"처방전?없이|무처방|정품|최저가|당일배송|해외직구|직구|구매대행")
_RX_WARNING = re.compile(r"수없|금지|불가|불법|주의|단속|적발|위험|가짜|처벌|신고|안됩니다|마세요|하지마")
# 영문 사전 낱말이 영어 단어 한가운데와 맞는 것('PHOTOGELLERY'의 togel)은 세지 않는다
_LATIN = re.compile(r"[a-z0-9]+")


@functools.lru_cache(maxsize=None)
def _latin_word(word):
    return bool(_LATIN.fullmatch(word))


@functools.lru_cache(maxsize=4096)
def _token_spans(raw, normalized):
    """정규화한 글에서 원문의 띄어쓰기 단위 낱말이 차지하는 (시작, 끝, 낱말). 맞춰 볼 수 없으면 None.

    자모를 띄어 쓴 위장(ㅋ ㅏ ㅈ ㅣ ㄴ ㅗ)은 낱말마다 정규화하면 이어 붙인 결과가 달라져 None 이 된다.
    그때는 경계를 따지지 않는다 (위장 글을 놓치지 않는 쪽).
    """
    if not raw:
        return None
    spans, pos = [], 0
    for token in raw.split():
        piece = normalize(token)
        if piece:
            spans.append((pos, pos + len(piece), piece))
            pos += len(piece)
    return tuple(spans) if "".join(s[2] for s in spans) == normalized else None


def _glued(rest, at_end, words):
    """낱말 일부만 끌어다 쓴 쪽의 남은 글자가 광고가 흔히 붙이는 말인가 ('놀이터추천'의 '추천')."""
    if not rest or rest[0 if at_end else -1].isdigit():
        return True
    return any(rest.startswith(w) if at_end else rest.endswith(w) for w in words())


def _accidental(start, end, spans, words):
    """띄어쓰기를 넘어 이웃 낱말의 일부만 끌어다 맞춘 우연한 일치인가.

    '가입 플랜'의 입플, '첫 충전'의 첫충, '코카 인형'의 코카인, '출장 오피스'의 출장오피는 우연이다.
    '출장 안마'·'토토 사이트'·'먹 튀'처럼 낱말 전체가 모여 사전 낱말이 되면 띄어 쓴 광고로 본다.
    """
    inside = [s for s in spans if s[0] < end and start < s[1]]
    if len(inside) < 2:
        return False
    first, last = inside[0], inside[-1]
    if first[0] < start and not _glued(first[2][:start - first[0]], False, words):
        return True
    return last[1] > end and not _glued(last[2][end - last[0]:], True, words)


# 업종 이름에 붙어도 광고라고 할 수 없는 응대 표현. 숨긴 메뉴·탭·스크린리더용 표 제목처럼
# 기관 누리집의 정상 화면 요소에 '카지노업 영업준칙 … 문의 관광정책과' 꼴로 흔히 붙는다
NEUTRAL_WEAK = ("문의", "상담")
# 외화 환전 문맥 (정규화된 글에서 찾으므로 띄어쓰기 없이 적는다)
FX_CONTEXT = ("외화", "환율", "외국환", "외국돈", "달러", "엔화", "유로", "위안", "해외여행", "여행자", "공항",
              "은행", "환전소", "우대")   # 환전 우대(환율 우대)는 은행 외화 상품 이름


def _coverage(words, text):
    """글자 가운데 주어진 낱말들이 차지하는 비율."""
    covered = set()
    for w in words:
        for m in re.finditer(re.escape(w), text):
            covered.update(range(m.start(), m.end()))
    return len(covered) / max(1, len(text))


def _maximal(words):
    """'순위'와 '순위표'처럼 겹치는 표현을 이중으로 세지 않는다."""
    return [w for w in words if not any(w != o and w in o for o in words)]


def match(normalized: str, obfuscated: bool = False, raw: str = "", strict: bool = False, context: str | None = None):
    """(광고 여부, 근거 낱말). 판정 내역은 match_detail 이 돌려준다."""
    detail = match_detail(normalized, obfuscated, raw, strict, context)
    return detail["is_ad"], detail["evidence"]


def _match_detail(normalized: str, obfuscated: bool = False, raw: str = "", strict: bool = False,
                 context: str | None = None):
    """정규화된 문자열이 불법광고인지 가중치로 판정하고, 사람이 볼 판정 내역을 함께 돌려준다.

    접근성용 숨김 문구('추천 순위표 바로가기' 등)는 약한 단어만 여러 개 겹치므로
    단순 개수 기준으로는 오탐이 난다. 확정적 표현과 유인 신호에 무게를 둔다.

    raw 는 정규화 전 원문이다. 정규화가 . / - _ 를 지우므로 t.me/, www., .com 같은
    연락처·주소 신호는 원문에서 찾아야 한다.

    strict 는 화면에 그대로 보이는 글에 쓴다. 보이는 글은 숨긴 글보다 훨씬 많고
    도서 소개('창가의 토토')·규정 안내처럼 종목 이름이 섞인 정상 글이 흔하다.
    그래서 확정 표현이나 거래 은어가 있거나, 연락 수단·문자 위장이 붙은 경우만 인정한다.
    약한 단어 조합(이벤트·쿠폰·카톡 문의)이나 종목 이름만으로는 보고하지 않는다.
    """
    alts = deleet_all(normalized)     # t0t0 -> toto 처럼 숫자 치환을 되돌린 보조 표기
    # 한글 종목 이름 뒤에 영문(전각 포함)으로 붙인 'site'는 '사이트'로도 본다 ('바카라 ｓｉｔｅ 추천')
    if "site" in normalized:
        alts = alts | {re.sub(r"(?<=[가-힣])site", "사이트", normalized)}
    # 연락처·주소·금액·위장 신호. 낱말 경계 판단에도 쓰므로 낱말보다 먼저 구한다
    signals = []
    contact_text = _PUBLIC_EMAIL.sub(" ", raw or "")
    both = (normalize(contact_text) if raw else normalized) + " " + contact_text.lower()
    if _CONTACT.search(both):
        signals.append("연락처")
    if _URLISH.search(_PUBLIC_HOST.sub(" ", both)):
        signals.append("외부주소")
    if _PROMO.search(both):
        signals.append("금액·비율")
    if obfuscated:
        signals.append("문자 난독화")

    spans = _token_spans(raw, normalized)
    # 실제 연락처나 문자 위장이 있으면 띄어쓰기를 넘은 일치도 센다. '바카 라게임 … 텔레 @id'처럼
    # 낱말 가운데를 띄워 피하는 광고는 연락처를 단다. 연락처 없는 '가입 플랜 안내'는 계속 뺀다
    loose = "연락처" in signals or obfuscated

    def glue():
        return (*STRONG, *TOPIC, *MEDIUM, *WEAK, *_GLUE)

    def latin_edge(i, text, edges):
        # 영문 사전 낱말의 앞이나 뒤가 낱말 경계인가. 띄어쓰기 자리(edges), 글의 처음·끝,
        # 한글·숫자처럼 영문자가 아닌 글자와 맞닿은 자리를 경계로 본다 ('agentogel', '카지노casino사이트')
        if i <= 0 or i >= len(text) or i in edges:
            return True
        return not (text[i - 1].isascii() and text[i - 1].isalpha() and text[i].isascii() and text[i].isalpha())

    def found(w, text):
        # 띄어쓰기를 넘어 이웃 낱말 일부만 끌어다 맞춘 자리는 세지 않는다
        if w not in text:
            return False
        same = spans is not None and len(text) == len(normalized)
        # 영문 낱말은 영어 단어 한가운데에 낀 자리를 세지 않는다 ('PHOTOGELLERY'의 togel, 2026-10-19 gb.go.kr).
        # 앞이나 뒤 한쪽만 경계여도 센다. 연락처·문자 위장이 있으면 붙여 쓴 스팸으로 보고 그대로 센다
        if _latin_word(w) and not loose:
            edges = {e for s in spans for e in s[:2]} if same else set()
            hits = [m.start() for m in re.finditer(re.escape(w), text)
                    if latin_edge(m.start(), text, edges) or latin_edge(m.start() + len(w), text, edges)]
            if not hits:
                return False
        else:
            hits = [m.start() for m in re.finditer(re.escape(w), text)]
        if not same or loose:
            return True
        return any(not _accidental(h, h + len(w), spans, glue) for h in hits)

    hay = "\0".join((normalized, *alts))      # 사전 낱말 대부분은 여기서 바로 걸러진다

    def has(w):
        return w in hay and (found(w, normalized) or any(found(w, a) for a in alts))

    def attached(w):
        """품목 낱말 바로 뒤에 거래 표현이 같은 낱말 안에서 붙었는가 ('졸피뎀구매')."""
        for m in re.finditer(re.escape(w), normalized):
            end = m.end()
            deal = _ATTACHED_DEAL.match(normalized, end)
            if deal and (spans is None or any(s[0] <= m.start() and deal.end() <= s[1] for s in spans)):
                return True
        return False

    strong = _maximal([w for w in STRONG if has(w)])
    # '메이저 사이트'는 큰 누리집이라는 일상어다. 붙여 쓴 은어이거나 도박 낱말이 함께 있을 때만 센다
    if "메이저사이트" in strong and "메이저사이트" not in (raw or normalized) and not any(
            has(w) for w in TOPIC if w != "메이저사이트"):
        strong.remove("메이저사이트")
    topic = _maximal([w for w in TOPIC if has(w)])
    # Whole English tokens only: "alphabet" is not a betting topic.
    english_tokens = {normalize(t) for t in re.findall(r"[A-Za-zＡ-Ｚａ-ｚ]+", raw)}
    topic += [w for w in ("bet", "poker", "porn", "blackjack") if w in english_tokens]
    topic = [w for w in topic if not any(w in s2 for s2 in strong)]
    for word, phrases in _NON_GAMBLING.items():
        remaining = normalized
        for phrase in phrases:
            remaining = remaining.replace(phrase, "")
        if word not in remaining and word in topic:
            topic.remove(word)
    # '환전'은 도박 머니 환전 말고 외화 환전(해외여행·은행 안내)에도 쓴다. 외화 문맥이고
    # 다른 도박 단서가 없으면 종목 이름으로 세지 않는다 ('당일 환전 보장 카지노'는 그대로 잡힌다)
    if topic == ["환전"] and not strong and any(w in normalized for w in (*FX_CONTEXT, "환전수수료")):
        topic = []
    medium = _maximal([w for w in MEDIUM if has(w)])
    # LSD 는 영문 낱말 하나일 때만 본다 ('bills due' 를 붙여 쓰면 'lsd' 가 들어 있다)
    medium += [w for w in ("lsd",) if w in english_tokens and w not in medium]
    medium = [w for w in medium if not any(w in s2 for s2 in strong + topic)]
    # 일상어 꼴 품목은 거래 표현이 붙었거나 연락처·위장, 또는 다른 불법 업종·품목 낱말이 있을 때만 센다
    # ('계정 판매 … 아이디 대량 판매'의 대량판매는 센다)
    everyday_ok = ("연락처" in signals or obfuscated or strong or topic or
                   any(w not in EVERYDAY for w in medium))
    medium = [w for w in medium if w not in EVERYDAY or everyday_ok or attached(w)]
    weak = _maximal([w for w in WEAK if has(w)])
    # English fragments such as event in prevention are not promotions.
    weak = [w for w in weak if w not in {"event", "free", "promo", "vip"} or w in english_tokens]
    weak = [w for w in weak if not any(w in s2 for s2 in strong + topic + medium)]

    contact = any(x in signals for x in ("연락처", "외부주소"))
    # 처방 의약품: 금지·경고 안내('처방전 없이 구입할 수 없습니다', '불법 판매 주의')는 아래에서 누르고,
    # 처방을 건너뛴 구매를 권하면('처방전 없이 정품 최저가') 그 표현을 거래 낱말로 센다.
    # 광고가 쓰는 '단속 걱정 없는'은 경고가 아니다
    rx = [w for w in medium if w in RX_DRUGS]
    rx_warning = (bool(rx) and not contact and not obfuscated and bool(_RX_WARNING.search(normalized))
                  and not re.search(r"걱정없|걱정마|안심", normalized))
    if rx and not rx_warning:
        weak += [c for c in dict.fromkeys(m.group(0) for m in _RX_SALE.finditer(normalized)) if c not in weak]
    caps, penalties, trace = [], [], []
    normal_evidence = assess(normalized, CAUTION)
    context_discount = 0.0
    original_score = None

    def cap(score, why):
        # 기준 바로 아래로 묶는 규칙. 판정 내역에 어떤 규칙이 점수를 눌렀는지 남긴다
        caps.append(why)
        capped = min(score, THRESHOLD - 0.05)
        if capped < score:
            trace.append({"step": f"상한: {why}", "delta": round(capped - score, 3), "score": round(capped, 3)})
        return capped

    def add(score, step, delta):
        # 점수를 바꾸는 단계마다 변화량과 바뀐 점수를 순서대로 남긴다 (판정 내역의 'trace')
        score += delta
        trace.append({"step": step, "delta": round(delta, 3), "score": round(score, 3)})
        return score

    def detail(is_ad, evidence, score=None, exempt=None):
        return {"is_ad": is_ad, "evidence": evidence,
                "groups": {"strong": strong, "topic": topic, "medium": medium, "weak": weak, "signals": signals},
                "score": None if score is None else round(score, 3), "threshold": THRESHOLD,
                "penalties": penalties, "caps": caps, "exempt": exempt,
                "normal_evidence": normal_evidence, "context_discount": context_discount,
                "original_score": original_score, "trace": trace}
    # 여러 낱말이 함께 있어야 의미가 생기는 거래 조합 (combo_rules.COMPOUNDS)
    prevention = bool(_PREVENTION.search(normalized))
    for rule in COMPOUNDS:
        if compound_matches(rule, normalized, contact, prevention):
            medium.append(rule["name"])
    # 필로폰·케타민 판매 은어(시원한술·찬술·케이). 단어만으로는 '시원한 술 판매 부스'·케이블·케이뱅크 같은
    # 정상 글과 구별되지 않아 사전 목록에 넣지 않는다. 판매 낱말이 바로 붙고 텔레그램 아이디가 함께 있을 때만
    # 거래 은어로 본다 ('시원한술구입방법 (텔레@아이디)', '케이구하는곳 (텔@아이디) 케이삽니다').
    if (_SLANG_SALE.search(normalized) and _MESSENGER.search(both) and not _PREVENTION.search(normalized)):
        medium.append('마약 판매 은어·텔레그램')
    if not contact and not _DIRECT_LURE.search(normalized):
        if (topic and not strong and not medium and
                set(topic) <= {"성인영상", "섹스영상", "포르노", "야설", "야동", "porn"} and
                any(w in normalized for w in ("차단프로그램", "차단설정", "유해사이트차단")) and
                set(weak) <= {"무료", "설치", "바로가기"}):
            return detail(False, topic + weak + signals, exempt="유해사이트 차단 안내")
        benign = (topic and not strong and not medium and not _PROMO.search(both) and
                  all(any(t in terms and any(word in normalized for word in contexts) and set(weak) <= allowed
                          for terms, contexts, allowed in NORMAL_CONTEXTS) for t in topic))
        # 병원·약국의 비급여 가격표·처방 안내는 의약품 이름과 금액을 함께 적는다.
        # 연락처·거래 표현·위장이 없을 때만 정상 안내로 본다
        if (medium and not strong and not topic and not obfuscated and
                _HEALTH_NOTICE.search(normalized) and not OFFER.search(normalized)):
            return detail(False, medium + weak + signals, exempt="병원·약국 가격·처방 안내")
        quotation = context == 'quotation'
        service = context == 'service' and topic and not strong and not medium and set(weak) <= {'무료', '상담'}
        if benign or quotation or service:
            return detail(False, strong + topic + medium + weak + signals,
                          exempt="정상 문맥" if benign else "인용문" if quotation else "기관 서비스 안내")

    # 한 문구 안에서 겹치는 중간 표현(대포통장·통장매입)이 점수를 부풀리지 않게 둘째부터는 덜 센다
    score = (len(strong) * STRONG_W +
             (TOPIC_W + (len(topic) - 1) * TOPIC_MORE_W if topic else 0) +
             (MEDIUM_W + (len(medium) - 1) * MEDIUM_MORE_W if medium else 0) +
             len(weak) * WEAK_W + len(signals) * SIGNAL_W)
    trace.append({"step": "기본 점수", "delta": round(score, 3), "score": round(score, 3)})
    # A transaction verb embedded in a compound must not disappear with
    # _maximal(). Require an actual contact; the global threshold stays intact.
    if ("연락처" in signals and not prevention and
            any(w in medium for w in ("대마판매", "대마구매", "대마구입", "대마사는곳",
                                      "대마파는곳", "대마구하는곳", "떨구매", "떨판매"))):
        score = add(score, "거래 낱말이 든 품목·연락처", WEAK_W)
    elif not prevention and any(attached(w) for w in medium if w not in EVERYDAY):
        score = add(score, "품목에 거래 표현이 붙음", ATTACHED_W)
    # 검색 유도 표식 '✅구글검색 빠른주소✅' 은 도배 광고만 쓴다. 연락처 대신 검색어로 끌어들이는 유인이다
    search_badge = bool(raw) and bool(SEARCH_BADGE.search(raw))
    if search_badge and not prevention:
        score = add(score, "검색 유도 표식", SIGNAL_W)
    original_score = round(score, 3)
    lure = any(x in signals for x in ("연락처", "외부주소", "문자 난독화")) or search_badge
    # 실제 거래와 경고가 충돌하면 감점으로 지우지 않는다. 인용 경고는
    # 연락처가 없을 때에만 면제하며, 문장별 후처리가 독립 광고를 다시 확인한다.
    reporting = bool(REPORTED.search(normalized)) and not contact and not LIVE_ACTION.search(normalized)
    conflict = bool(OFFER.search(normalized)) and not reporting
    if conflict and not OFFER_LURE.search(normalized) and any(
            e["family"] in VICTIM_FAMILIES for e in normal_evidence):
        conflict = False
    if normal_evidence and not conflict and not contact:
        context_discount = discount(normal_evidence)
        score = add(score, "정상 문맥 감점", -context_discount)
        penalties.append("정상 문맥 " + ", ".join(e["family"] for e in normal_evidence)
                         + f" (-{context_discount:g})")
        score = cap(score, "거래 유도 없는 예방·지원·보도 문맥")
    # 일반 홍보어·연락처·URL만으로 불법 업종을 추론하지 않는다. 공공 안내와 약관에도
    # 같은 조합이 있다. 업종·확정 표현·거래 은어가 있어야 광고 경보로 보고한다.
    # A deliberately disguised messenger handle remains reviewable evidence;
    # plain contact details and fullwidth public acronyms remain insufficient.
    disguised_handle = False
    if obfuscated:
        from normalize import disguised_chars
        handle = re.search(r"(?:텔레그램|텔레|텔)\s*@([^\s«»<>]+)", raw)
        if handle:
            chars = disguised_chars(handle.group(1))
            disguised_handle = any(not "\uff01" <= ch <= "\uff5e" for ch in chars)
    if not (strong or topic or medium or disguised_handle):
        score = cap(score, "유해 업종·불법 은어 키워드 없음")
    # 품목 이름만 문장 속에 늘어선 글은 목록·서식이다 (2026-10-19 gb.go.kr 채용 신체검사서의 '마약류 검사
    # 필로폰 대마 케타민 …'). 광고 유도 낱말·신호가 하나도 없고 품목 이름이 글의 절반이 안 될 때만 누른다.
    # 품목 이름만 빽빽한 숨김 도배('작업대출 내구제 무직자대출 …')는 그대로 본다
    # '계정판매'·'대량판매'처럼 거래 표현이 든 품목 낱말은 그 자체가 거래 단서다
    if (medium and not (strong or topic or weak or signals or search_badge) and
            not any(_ATTACHED_DEAL.search(w) for w in medium) and _coverage(medium, normalized) < 0.5):
        score = cap(score, "품목 이름만 있고 거래·연락 단서 없음")
    if rx_warning and not (strong or topic):
        score = cap(score, "처방 의약품 이름과 금지·경고 안내")
    # 업종 이름 + '문의'만 있는 글은 소관 기관의 안내다 (광고는 가입·충전·쿠폰처럼 권하는 말이나 연락처를 단다)
    if topic and not (strong or medium) and not lure and all(w in NEUTRAL_WEAK for w in weak):
        score = cap(score, "업종 이름과 문의 안내뿐")
    # 화면에 보이는 글에서 종목 이름 하나를 자모로 풀어 쓴 것만으로는 광고가 아니다
    # ('한글 자모 조합 연습: ㅋㅏㅈㅣㄴㅗ … 문의'). 광고는 가입·지급·연락처처럼 권하는 말이 함께 붙는다.
    # 숨겨 둔 글은 그것만으로도 수상하므로 그대로 둔다.
    if (strict and len(topic) == 1 and not (strong or medium) and all(w in NEUTRAL_WEAK for w in weak)
            and signals == ["문자 난독화"]):
        score = cap(score, "보이는 글의 자모 풀어쓰기뿐")
    is_ad = score >= THRESHOLD
    if strict and is_ad:
        bonus_offer = topic and {'가입', '보너스'} <= set(weak)
        is_ad = bool(strong or medium or "문자 난독화" in signals or (topic and contact) or bonus_offer)
    gated = strict and score >= THRESHOLD and not is_ad
    return detail(is_ad, strong + topic + medium + weak + signals, score,
                  exempt="보이는 글 기준(확정·은어·위장·연락처) 미달" if gated else None)


def match_detail(normalized: str, obfuscated: bool = False, raw: str = "", strict: bool = False,
                 context: str | None = None):
    """기본 점수 뒤에 문맥·근거 거리 정책을 적용한다. 후보는 광고 확정과 구분한다."""
    from precision_policy import refine
    detail = _match_detail(normalized, obfuscated, raw, strict, context)
    return refine(detail, raw, normalized, obfuscated, strict, context, _match_detail,
                  NORMAL_CONTEXTS)



# ── 화면에서 관리하는 사용자 키워드 ──
# 담당자가 화면에서 단어를 더하거나 기본 단어를 끈 내역을 결과 폴더의 파일에 남기고,
# 실행할 때마다 기본 사전 위에 덧씌운다. 파일이 없거나 깨졌으면 기본 사전 그대로 동작한다.
USER_FILE = "keyword_state.json"

# (목록 이름, 화면 이름, 판정 방식 설명)
CATEGORIES = [
    ("STRONG", "불법 은어 키워드", "이 말만 있어도 광고로 봅니다. 광고에서만 쓰는 은어만 넣으십시오."),
    ("TOPIC", "유해 업종·종목 키워드", "보도·안내문에도 나오는 말이라 다른 단서(광고 유도 키워드·연락처 등)가 하나 더 있어야 광고로 봅니다."),
    ("MEDIUM", "불법 행위·품목 키워드", "예방 안내에도 쓰이는 말이라 판매·연락처·금액 같은 단서가 둘 이상 붙어야 광고로 봅니다."),
    ("WEAK", "광고 유도 키워드", "단독으로는 광고가 아니고, 다른 키워드와 겹칠 때 점수를 보탭니다."),
    ("CAUTION", "오탐 방지 키워드", "신고·예방 문맥을 확인하는 단서입니다. 단어 단독·반복으로 감점하지 않고, 의미군별 감점은 최대 0.8점입니다."),
]
_CAT_IDS = [c[0] for c in CATEGORIES]
VERSION = 0                           # 사전을 고칠 때마다 올린다
_BUILTIN = {c: list(globals()[c]) for c in _CAT_IDS}


def _empty_state():
    return {"added": {c: [] for c in _CAT_IDS}, "off": {c: [] for c in _CAT_IDS}}


def clean_word(word: str) -> str:
    """매칭은 정규화된 글(띄어쓰기·구분자 제거, 소문자)에 대해 하므로 단어도 같은 꼴로 맞춘다."""
    from normalize import normalize
    return normalize(word or "").strip()


def apply_state(state):
    """기본 사전에서 꺼 둔 단어를 빼고 더한 단어를 붙여 판정 목록을 다시 만든다.

    목록 객체를 바꿔 끼우지 않고 내용만 고친다 (다른 모듈이 같은 목록을 들고 있어도 반영되게).
    """
    global VERSION
    VERSION += 1                      # 판정 결과를 기억해 둔 곳(findings.classify)이 새로 판정하게
    state = state or _empty_state()
    for c in _CAT_IDS:
        off = set(state.get("off", {}).get(c, []))
        added = [w for w in state.get("added", {}).get(c, []) if w not in _BUILTIN[c]]
        globals()[c][:] = [w for w in _BUILTIN[c] if w not in off] + added


def load_state(out_dir):
    import json, os
    try:
        with open(os.path.join(out_dir, USER_FILE), encoding="utf-8") as fp:
            state = json.load(fp)
        base = _empty_state()
        for part in ("added", "off"):
            for c in _CAT_IDS:
                base[part][c] = [str(w) for w in state.get(part, {}).get(c, []) if str(w)]
        apply_state(base)
        return base
    except Exception:
        apply_state(None)
        return _empty_state()


def save_state(out_dir, state):
    import os
    from fileio import write_json
    write_json(os.path.join(out_dir, USER_FILE), state, indent=1)
    apply_state(state)


def describe(state):
    """화면에 보여 줄 분류별 단어 목록."""
    rows = []
    for cid, name, desc in CATEGORIES:
        off = set(state["off"][cid])
        rows.append({
            "id": cid, "name": name, "desc": desc,
            "builtin": [{"word": w, "on": w not in off} for w in _BUILTIN[cid]],
            "added": list(state["added"][cid]),
        })
    return rows


def find_category(word):
    """이미 들어 있는 단어면 (분류, 기본 여부) 를 돌려준다."""
    for c in _CAT_IDS:
        if word in _BUILTIN[c]:
            return c, True
    return None, False
