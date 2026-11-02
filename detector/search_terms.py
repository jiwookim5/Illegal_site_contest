"""검색엔진 보조 탐색에서 쓰는 유형별 고정 광고단어.

공공 누리집에 실제로 노출된 불법광고 검색 결과(게시판·첨부파일 제목, 요약)에서 자주 보인 말을
유형별로 고정해 두어, 담당자가 단어를 고르지 않아도 유형만 선택하면 검색할 수 있게 한다.
직접 입력은 화면의 고급 기능으로 둔다.

- 두 낱말을 띄어 쓴 항목(예: "구글검색 빠른주소")은 하나의 검색어로 함께 나온 글만 찾는다.
- 모든 낱말은 점검 사전(lexicon)에 있어야 제출 판정(result_extra.json)에 들어간다.
  사전에 아직 없는 말은 SEARCH_ONLY 에 따로 적는다. 검색에는 쓰지만 판정은 다른 단서에 기대므로,
  사전에 넣으면 이 목록에서 지운다 (tools/test_search_terms.py 가 둘의 일치를 확인한다).
"""

MAX_TERMS = 30       # 한 번에 검색할 단어 수 상한 (검색 API 이용 한도를 보호한다)

# (유형 id, 화면 이름, 고정 단어)
GROUPS = [
    ("gambling", "도박·사행성", ["꽁머니", "먹튀", "토토사이트", "카지노사이트", "슬롯사이트"]),
    # 도박 사이트 접속 주소 안내 글과 도박 자금 계좌 거래 글
    ("gambling_ref", "도박 주소·계좌 거래", ["구글검색 빠른주소", "토토계좌매입", "충전계좌팝니다"]),
    ("loan", "대포통장·불법 대출", ["대포통장", "통장매입", "통장대여", "작업대출"]),
    # 판매 글은 '시원한술·찬술(필로폰)' 같은 은어와 텔레그램 아이디를 함께 쓴다
    ("drug", "마약·불법 의약품", ["필로폰", "작대기", "시원한술", "찬술", "물뽕"]),
    ("adult", "성인·유흥", ["조건만남", "출장안마", "성인라방"]),
    ("job", "고수익 알바·가담자 모집", ["고액알바", "꿀알바", "재택부업"]),
    ("foreign", "외국어 도박 스팸", ["slotgacor", "togel"]),
]

# 검색에는 쓰지만 점검 사전에는 아직 없는 낱말 (사전에 넣으면 여기서 지운다)
SEARCH_ONLY = ("토토계좌매입", "충전계좌팝니다", "시원한술", "찬술")


def groups():
    """화면에 내려주는 유형 목록."""
    return [dict(id=i, name=name, terms=list(words)) for i, name, words in GROUPS]


def expand(group_ids, extra=()):
    """선택한 유형의 고정 단어와 추가 단어를 중복 없이 합친다. 모르는 유형이면 ValueError."""
    known = {i: words for i, _, words in GROUPS}
    if not isinstance(group_ids, (list, tuple)) or any(g not in known for g in group_ids):
        raise ValueError('알 수 없는 광고 유형입니다.')
    terms = [w for g in group_ids for w in known[g]]
    terms += [t.strip() for t in extra if t.strip()]
    return list(dict.fromkeys(terms))
