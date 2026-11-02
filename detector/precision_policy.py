"""광고 근거의 의미와 거리를 확인하는 후처리. 점수는 확률이 아니다."""
import re
from normalize import normalize
from context_evidence import REPORTED, LIVE_ACTION, OFFER_LURE, discount
from combo_rules import OFFERS, OFFER_WORDS, SEARCH_BADGE, offer_matches

# URL의 마침표와 광고의 구분자 난독화는 문장 경계로 나누지 않는다.
BOUNDARY = re.compile(r"\n+|[;；]|\s+[|·•]\s+|(?<=[.!?。])\s+")
# 세로줄이 하나뿐인 'A | B' 는 홍보 글 제목의 '이름 | 소개' 꼴이다 ('야동티비 | ✅구글검색 빠른주소✅ …').
# 메뉴 목록('홈 | 소개 | 문의')처럼 세로줄이 둘 이상일 때만 나눈다
BOUNDARY_ONE_BAR = re.compile(r"\n+|[;；]|\s+[·•]\s+|(?<=[.!?。])\s+")
BROAD = {"재택부업", "사람찾기", "심부름센터", "백링크", "구글검색", "접속주소", "빠른주소", "라방"}
TRANSACTION = re.compile(r"가입(?:코드|쿠폰|보너스|머니)|추천코드|첫충|입플|꽁머니|"
                         r"(?:지금|즉시|바로)(?:가입|접속|입금)|"
                         r"가입시|판매|팝니다|삽니다|구매|구입|매입|주문|비밀배송|던지기|충전|입금|출금|롤링|수익보장|원금보장")
ACTION_CONTACT = re.compile(r"@[a-z0-9_]{4,}|t\.me/|010[\s-]*\d{3,4}[\s-]*\d{4}|"
                            r"(?:텔레그램|telegram|텔레|텔래|텔그|탤레|탤그|텔ㄹ|텔|카톡)\s*[:@]?\s*[a-z][a-z0-9_]{3,}", re.I)
# 숨긴 글에서 업종 이름과 함께 있으면 광고로 보는 권하는 말. 바로가기·문의·상담·주소는 숨긴 메뉴에도 있어 뺀다
HIDDEN_PROMO = frozenset(("무료", "체험", "이벤트", "가입", "보너스", "쿠폰", "지급", "추천", "충전", "입금",
                          "머니", "즉시", "free", "event", "promo"))
# 일상어로도 쓰는 업종 이름 (바다이야기 축제, 야구 배팅센터, 잭팟 경품, 외화 환전, 음란물 차단 프로그램).
# 하나만 있으면 숨긴 글의 권하는 말로 광고를 확정하지 않는다. 영문 업종 이름(slot·casino)도 영어판 누리집에 흔해 같다
AMBIGUOUS_TOPIC = frozenset(("바다이야기", "배팅", "베팅", "잭팟", "에볼루션", "환전", "음란", "토렌트", "스웨디시", "1인샵"))
# 숨긴 탭·팝업의 정상 공지에 붙는 낱말 ('청소년 홀덤 체험 금지 안내', '카지노 관광 셔틀버스 무료 운행')
NOTICE_WORDS = re.compile(r"안내|공지|축제|행사|프로그램|교육|강좌|센터|연습장|관광|체험관|전시|공연|대회|"
                          r"금지|차단|예방|설치|운행|판매점|접수")
# 글 전체에 있으면 한 문장의 광고 단서를 확정하지 않는 문맥. '주의하세요'·보도 낱말은 광고 글에도 흔해 뺀다
WHOLE_CONTEXT = frozenset(("예방·교육", "피해·상담 지원", "피해·결과", "불법 수식"))
AMBIGUOUS_GUIDE = re.compile(r"먹튀.{0,12}예방가이드|검증제휴사이트")


def _traced(detail, step, score):
    """점수를 바꾸고 lexicon 이 시작한 판정 내역(trace)에 그 단계를 잇는다."""
    score = round(score, 3)
    step = {"step": step, "delta": round(score - detail["score"], 3), "score": score}
    return dict(detail, score=score, trace=list(detail.get("trace") or []) + [step])


def _candidate(detail, reason):
    return dict(detail, is_ad=False, review_candidate=True, decision="review",
                review_reason=reason)


def refine(detail, raw, normalized, obfuscated, strict, context, evaluate,
           normal_contexts, local=True):
    detail = dict(detail, review_candidate=False, decision="ad" if detail["is_ad"] else "normal")
    judged = []
    if local and raw:
        boundary = BOUNDARY_ONE_BAR if len(re.findall(r"\s\|\s", raw)) == 1 else BOUNDARY
        parts = [p.strip() for p in boundary.split(raw) if p.strip()]
        if len(parts) > 1:
            judged = [refine(evaluate(normalize(p), obfuscated, p, strict, context),
                             p, normalize(p), obfuscated, strict, context, evaluate,
                             normal_contexts, local=False) for p in parts]
            ads = [d for d in judged if d["is_ad"]]
            if ads:
                best = dict(max(ads, key=lambda d: d.get("score") or 0), local_basis=True)
                # 상담 글·예방 웹툰은 문장 하나만 떼면 광고처럼 읽힌다 ('토토 등을 구입하는 것은',
                # '개인통장 1개당 200만 원에 삽니다'). 글 전체에 예방·피해 문맥이 있고 그 문장 밖에도
                # 연락처·주소·가입 혜택 같은 실제 유도가 없으면 확정하지 않고 후보로 둔다
                context_families = {e["family"] for e in detail.get("normal_evidence") or []}
                if (context_families & WHOLE_CONTEXT and not best.get("normal_evidence")
                        and not (obfuscated or ACTION_CONTACT.search(raw) or OFFER_LURE.search(normalized)
                                 or LIVE_ACTION.search(normalized)
                                 or {"연락처", "외부주소"} & set(detail["groups"]["signals"]))):
                    return _candidate(best, "글 전체가 예방·피해 이야기라 문장 하나의 단서로 확정하지 않음")
                return best
    if not detail["is_ad"]:
        candidates = [d for d in judged if d["review_candidate"]]
        if candidates:
            return max(candidates, key=lambda d: d.get("score") or 0)
        return detail
    groups = detail["groups"]
    strong, topic, medium, weak = (groups[k] for k in ("strong", "topic", "medium", "weak"))
    # 거래 동사와 업종 단어가 같은 가까운 구간에 있어야 직접 유도로 인정한다.
    anchors = strong + topic + medium
    positions = [m.start() for word in anchors for m in re.finditer(re.escape(word), normalized)]
    direct = any(abs(m.start() - pos) <= 80
                 for m in TRANSACTION.finditer(normalized)
                 for pos in positions)
    normal_evidence = detail.get("normal_evidence", [])
    warning = bool(normal_evidence)
    reporting = bool(REPORTED.search(normalized))
    actual_contact = bool(ACTION_CONTACT.search(raw) or ACTION_CONTACT.search(normalized))
    search_lure = bool(re.search(r"구글검색[a-z가-힣0-9]{2,}", normalized)) and any(
        w in normalized for w in ("스포츠중계", "해외축구", "무료실시간", "토토", "카지노", "먹튀"))
    search_badge = bool(SEARCH_BADGE.search(raw or ""))
    search_lure = search_lure or search_badge
    direct = direct or search_lure or {'가입', '보너스'} <= set(weak) or (
        "외부주소" in groups["signals"] and any(w in normalized for w in ("최신주소", "접속주소", "빠른주소")))
    offer = bool(topic) and any(offer_matches(rule, normalized, topic, weak) for rule in OFFERS)
    direct = direct or offer
    if AMBIGUOUS_GUIDE.search(normalized) and not direct:
        return _candidate(detail, "예방·검증 안내가 사이트 이용 유도인지 확인 필요")
    benign = bool(topic) and not (strong or medium) and all(
        any(t in terms and any(w in normalized for w in contexts) and set(weak) <= allowed
            for terms, contexts, allowed in normal_contexts) for t in topic)
    # 연락처가 있어 기본 감점을 보류했더라도, 거래 유도가 없는 안내 링크는
    # 같은 의미군 감점을 한 번만 적용한다. 개인 연락처는 계속 후보로 보존한다.
    if warning and not direct and not actual_contact and not detail.get("context_discount"):
        amount = discount(normal_evidence)
        detail = dict(_traced(detail, "정상 문맥 감점 (링크·안내)", detail["score"] - amount),
                      context_discount=amount,
                      penalties=detail["penalties"] + [
                          "정상 문맥 " + ", ".join(e["family"] for e in normal_evidence) + f" (-{amount:g})"])
    if reporting and not actual_contact and not LIVE_ACTION.search(normalized):
        return _candidate(detail, "광고 표현의 인용·경고 여부 확인 필요")
    # 정상 문맥의 링크·상담 창구는 거래 유도가 아니다. 실제 거래 지시가 있으면 보류한다.
    if judged:
        if (warning or benign or context in {"quotation", "service"}) and not direct and not actual_contact:
            return dict(detail, is_ad=False, decision="normal", exempt="거래 유도 없는 안내·정상 문맥")
        if all(d.get("exempt") == "거래 유도 없는 안내·정상 문맥" for d in judged):
            return dict(detail, is_ad=False, decision="normal", exempt="거래 유도 없는 안내·정상 문맥")
        # 검색 유도 도배 글은 업종·대출·주소 안내를 여러 문장에 나눠 쓴다. 표식이 있으면 글 전체로 판정한다.
        # 이런 글은 '먹튀 피해사례', '주의하세요'도 홍보 문구로 섞어 쓰므로 경고 문맥이 있어도 같다
        # 불법 스포츠 중계 홍보도 중계 낱말과 유인 말('통티비 바로가기')을 다른 문장에 쓴다
        if search_badge or "불법 스포츠 중계" in medium:
            return detail
        return _candidate(detail, "서로 다른 문장의 단서를 합쳐야 기준에 도달함")

    if (warning or benign or context in {"quotation", "service"}) and not direct:
        if actual_contact:
            return _candidate(detail, "정상 안내 문맥에 개인 연락처가 함께 있어 확인 필요")
        return dict(detail, is_ad=False, decision="normal", exempt="거래 유도 없는 안내·정상 문맥")

    # 일반 홍보어는 최대 두 개까지만 확정 판단에 기여한다. 거래 표현은 별도 근거다.
    mild = [w for w in weak if not TRANSACTION.search(w) and not (offer and w in OFFER_WORDS)]
    if len(mild) > 2:
        detail = _traced(detail, "일반 홍보어 가점은 최대 2개", detail["score"] - (len(mild) - 2) * 0.3)
        detail["penalties"] = detail["penalties"] + ["일반 홍보어 가점은 최대 2개"]
    adjusted = detail["score"]
    if adjusted < detail["threshold"]:
        return _candidate(detail, "일반 홍보 표현을 제외하면 광고 근거가 부족함")
    if medium and set(medium) <= BROAD and not (strong or topic or search_lure):
        return _candidate(detail, "정상 용도가 있는 키워드로 불법성을 확정할 수 없음")
    contact_positions = [m.start() for m in ACTION_CONTACT.finditer(normalized)]
    contact_positions += [len(normalize(raw[:m.start()])) for m in ACTION_CONTACT.finditer(raw)]
    if actual_contact and not (strong or direct or obfuscated) and positions and not any(
            abs(a - c) <= 80 for a in positions for c in contact_positions):
        return _candidate(detail, "업종·품목과 연락처가 떨어져 있어 같은 거래의 근거인지 확인 필요")
    explicit_offer = offer or any(w in normalized for w in ('첫충', '입플', '꽁머니', '가입코드', '추천코드', '지금가입'))
    if warning and not (direct and explicit_offer):
        return _candidate(detail, "안내·보도 문맥과 거래 표현이 함께 있어 원문 확인 필요")
    signals = groups["signals"]
    # 숨긴 글(strict 가 아님)에서 업종 이름에 권하는 말이 붙으면 광고로 본다 ('릴게임 바다이야기 무료',
    # 요강 예시 '무료 슬롯 체험 바로가기'). 감춰 둔 것 자체가 근거다. '스포츠토토 바로가기' 같은 숨긴 메뉴,
    # 공지 낱말이 붙은 글, 일상어로도 쓰는 업종 이름 하나뿐인 글은 후보로 둔다
    clear_topic = [t for t in topic if t not in AMBIGUOUS_TOPIC and not t.isascii()]
    hidden_offer = (not strict and bool(set(weak) & HIDDEN_PROMO) and (clear_topic or len(topic) >= 2)
                    and not NOTICE_WORDS.search(normalized))
    if not (strong or medium or direct or obfuscated or actual_contact or hidden_offer) and topic and not (
            len(topic) >= 2 and "외부주소" in signals):
        return _candidate(detail, "업종 이름과 일반 홍보·주소만 있어 거래 유도가 불명확함")
    if "연락처" in signals and not actual_contact and not direct and not strong and not (medium or obfuscated):
        return _candidate(detail, "연락 수단 언급만으로 광고 연락처를 확인할 수 없음")
    return detail
