"""낱말 하나로는 뜻이 없고 여럿이 함께 있어야 광고 근거가 되는 조합 규칙.

판정 코드에 흩어져 있던 조합 조건을 표로 모았다. 규칙을 더하거나 고칠 때는 이 표만 바꾼다.
낱말은 정규화한 글(띄어쓰기·구분자 제거, 소문자) 기준으로 적는다.
"""
import re

# 품목(MEDIUM)으로 더하는 거래 조합. groups 의 각 묶음에서 min 개(기본 1개) 이상이 글에 있어야 한다.
#   contact: 연락처·외부주소가 함께 있어야 함
#   no_prevention: 예방 교육·피해 예방 문구가 있으면 쓰지 않음
#   pattern: 이 정규식이 글에 맞아야 함 (낱말 사이 거리가 중요한 조합)
#   unless: 이 정규식이 글에 맞으면 쓰지 않음 ('게임머니 환전은 불법입니다' 같은 경고)
COMPOUNDS = (
    # 캔디·허브·크리스탈은 일상 상품 이름이라 은어 둘 이상 + 던지기(비대면 전달) + 연락처를 모두 요구한다
    {"name": "복합 거래 은어·던지기", "contact": True, "no_prevention": True,
     "groups": ((("던지기",), 1), (("캔디", "허브", "크리스탈"), 2))},
    {"name": "놀이터 검증업체·연락처", "contact": True,
     "groups": ((("놀이터",), 1), (("검증업체", "보증업체"), 1), (("순위", "추천"), 1))},
    {"name": "메신저 가짜 인원 거래",
     "groups": ((("텔레그램", "telegram"), 1), (("채널", "그룹"), 1), (("판매", "작업"), 1),
                (("유령", "가짜"), 1))},
    # 사행성 게임의 게임머니 환전 (2008 대전시 자유게시판 '모은 칩은 실버로 신청 현금화').
    # 게임산업법이 금지하는 환전 광고다. 카드 포인트 현금화는 합법 서비스라 '포인트'는 넣지 않는다
    {"name": "게임머니 환전", "no_prevention": True,
     # 카지노 안내의 '칩 환전'(강원랜드 환전소)은 합법이라 칩은 '현금화'와만 묶는다
     "pattern": r"(?:게임머니|겜머니|게임칩)(?:은|을|를)?.{0,8}(?:현금화|환전)|칩(?:은|을|를)?.{0,8}현금화|"
                r"(?:현금화|환전).{0,4}(?:게임머니|게임칩)",
     "unless": r"불법|신고|처벌|주의|금지|예방",
     "groups": ()},
    # 불법 스포츠 중계 홍보 (2026-10-20 광주교육청 배너모음 '통티비' 글 9건: '야구 무료중계는 통티비가 정답',
    # '버퍼링 없는 해외 스포츠 실시간'). 중계 낱말에 불법 중계 사이트가 쓰는 유인 말이 함께 있어야 한다.
    # 방송사 편성·행사 생중계 안내('체육대회를 유튜브로 실시간 중계 보러가기')와 중계권 보도는 이 유인 말이 없어
    # 빠진다. 유인 말은 불법 중계 사이트만 쓰는 것으로 둔다 ('보러가기'·'입장'은 행사 안내에도 붙어 뺀다)
    {"name": "불법 스포츠 중계", "no_prevention": True,
     "pattern": r"(?s)^(?=.*(?:(?:무료|해외|스포츠|실시간|야구|축구)(?:스포츠)?(?:무료)?중계|중계사이트))"
                r"(?=.*(?:티비입장|tv입장|중계사이트|빠른주소|접속주소|버퍼링|끊김없|무료라이브|올킬|종결자|끝판왕|"
                r"tongtv|티비바로가기))",
     "unless": r"저작권|신고|처벌|금지|예방|체육대회|축구대회|야구대회|거리응원|행사",
     "groups": ()},
)
# 검색 유도 도배 글의 표식 '✅구글검색 꽁타✅' (2026-10-20 광주교육청 배너모음 게시판 52건).
# 공공 안내문은 검색어를 체크 표시로 감싸 내걸지 않는다
SEARCH_BADGE = re.compile(r"✅\s*구글\s*검색\s*[^\s✅]{2,20}\s*✅")

_ADULT = ("섹스영상", "성인영상", "포르노", "porn", "야설", "야동")
_STREAMING = ("누누티비", "뉴토끼", "툰코", "토렌트")

# 업종 이름(TOPIC)과 함께 있을 때 '이용을 권하는 제안'으로 보는 조합 (precision_policy 의 offer).
# 적힌 조건을 모두 만족해야 한다.
#   weak_all: 이 광고 유도 키워드가 모두 잡힘     weak_any: 하나 이상 잡힘
#   text_all: 이 말이 모두 글에 있음              text_any: 하나 이상 있음
#   topic_any: 이 업종 이름 가운데 하나가 잡힘
OFFERS = (
    {"weak_all": ("가입", "보너스")},
    {"weak_all": ("쿠폰", "지급")},
    {"weak_all": ("총판", "모집")},
    {"weak_all": ("무료", "체험", "바로가기")},
    {"text_all": ("추천인코드",)},
    {"text_all": ("슬롯머신",), "weak_any": ("바로가기", "쿠폰")},
    {"topic_any": _ADULT, "weak_any": ("무료", "free")},
    {"topic_any": _STREAMING, "text_all": ("최신주소",), "text_any": ("바로가기", "다운로드", "다시보기")},
    {"topic_any": ("블랙잭",), "text_all": ("무료게임",)},
)
# 제안 조합을 이루는 광고 유도 키워드. 제안이 성립하면 '일반 홍보어 최대 2개' 제한에서 뺀다
OFFER_WORDS = frozenset(w for rule in OFFERS for w in rule.get("weak_all", ()))


def compound_matches(rule, normalized, contact, prevention):
    if rule.get("contact") and not contact:
        return False
    if rule.get("no_prevention") and prevention:
        return False
    if "pattern" in rule and not re.search(rule["pattern"], normalized):
        return False
    if "unless" in rule and re.search(rule["unless"], normalized):
        return False
    return all(sum(w in normalized for w in words) >= least for words, least in rule["groups"])


def offer_matches(rule, normalized, topic, weak):
    topic, weak = set(topic), set(weak)
    return (all(w in weak for w in rule.get("weak_all", ())) and
            ("weak_any" not in rule or weak & set(rule["weak_any"])) and
            all(w in normalized for w in rule.get("text_all", ())) and
            ("text_any" not in rule or any(w in normalized for w in rule["text_any"])) and
            ("topic_any" not in rule or topic & set(rule["topic_any"])))
