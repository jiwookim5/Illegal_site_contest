"""사람 검토를 돕는 판정 등급(확실·의심·경계)과 그 근거 문장.

광고 여부는 lexicon.match 가 정한다. 여기서는 이미 광고로 판정된 글을 두 축으로 다시 본다.
  문구: 판정 점수가 기준(lexicon.THRESHOLD)을 얼마나 넘었는가, 불법 은어 키워드·연락처가 있는가
  은닉: 투명·화면 밖·덮어 가림·문자 위장처럼 일부러 감춘 흔적이 있는가
숫자 점수는 화면에 내보내지 않는다. 담당자에게는 색과 근거 문장만 보여 준다.
결과 파일(result.json·result_extra.json)에는 넣지 않는다 (요강 스키마).
"""

HIGH, MID, LOW = "high", "mid", "low"
LABELS = {HIGH: "확실", MID: "의심", LOW: "경계"}
# 광고 근거가 부족한 항목(review)도 화면에는 '경계'로 보인다. 다만 제출용 위반 항목에서 빠지므로 이 표시를 붙인다
REVIEW, REVIEW_NOTE = "review", "제출 제외"


def label_of(j):
    """화면·보고서·CSV에 쓰는 등급 이름. 이름을 합치기 전에 저장한 '검토 후보'도 '경계'로 보인다."""
    level = (j or {}).get("level")
    if level == REVIEW:
        return f"{LABELS[LOW]} · {REVIEW_NOTE}"
    return LABELS.get(level) or (j or {}).get("label") or ""

# 기준을 이만큼 넘지 못하면 '겨우 넘음'이다. 신호 하나(lexicon.SIGNAL_W)만큼의 여유
NARROW = 0.35
# 기준을 이만큼 넘고 연락처·은닉이 함께 있으면 확정 표현이 없어도 확실로 본다
WIDE = 1.0

_GROUPS = (("strong", "불법 은어 키워드"), ("topic", "유해 업종·종목 키워드"), ("medium", "불법 행위·품목 키워드"),
           ("weak", "광고 유도 키워드"))
_SIGNALS = {"연락처": "연락처가 붙어 있음", "외부주소": "외부 주소가 붙어 있음",
            "금액·비율": "금액·비율 표기가 있음", "문자 난독화": "글자를 바꿔 써 위장함"}
BASIS = {"segment": "글 전체가 아닌 일부 조각만 광고로 판정됨",
         "linked": "이 글만으로는 기준 미달이나, 함께 숨긴 광고와 같은 도메인을 알림"}


def judge(verdict, conceal=(), basis="whole"):
    """classify 결과 하나로 등급을 정한다.

    conceal: 숨김·위장 이유 문장 목록 (없으면 화면에 그대로 보이는 글)
    basis: whole(글 전체 판정) · segment(조각 판정) · linked(인접 광고 도메인)
    """
    detail = (verdict or {}).get("score") or {}
    groups = detail.get("groups") or {}
    signals = groups.get("signals") or []
    score, threshold = detail.get("score"), detail.get("threshold", 1.0)
    margin = None if score is None else score - threshold
    conceal = [c for c in conceal if c]
    strong = bool(groups.get("strong"))
    lure = any(s in signals for s in ("연락처", "외부주소"))
    hidden = bool(conceal) or "문자 난독화" in signals

    reasons = [f"{name}: {', '.join(groups[key])}" for key, name in _GROUPS if groups.get(key)]
    reasons += [_SIGNALS.get(s, s) for s in signals]
    reasons += [f"감점: {p}" for p in detail.get("penalties") or []]
    reasons += [f"숨김: {c}" for c in conceal]

    if detail.get("review_candidate"):
        level = REVIEW
        reasons.append(detail.get("review_reason") or "광고 근거 확인 필요")
        reasons.append("광고 근거가 부족한 경계 항목은 제출용 위반 항목에 포함하지 않습니다")
    elif basis != "whole":
        level = LOW
        reasons.append(BASIS.get(basis, basis))
    elif strong and (lure or hidden):
        level = HIGH
    elif margin is not None and margin >= WIDE and (lure or hidden):
        level = HIGH
    elif margin is not None and margin < NARROW and not conceal:
        level = LOW
        reasons.append("판정 기준을 겨우 넘음")
    else:
        level = MID
    # 검색엔진 추가 탐색의 광고단어 후보로 쓰는 낱말 (홍보 표현·신호는 검색어로 쓰기에 너무 흔하다)
    # 조합 규칙 이름('놀이터 검증업체·연락처')은 낱말이 아니라 뺀다
    terms = [w for key in ("strong", "topic", "medium") for w in groups.get(key) or []
             if " " not in w and "·" not in w]
    return {"level": level, "label": LABELS[LOW] if level == REVIEW else LABELS[level],
            "decision": "review" if level == REVIEW else "ad", "reasons": reasons, "terms": terms}


def judge_many(verdicts, conceal=()):
    """여러 문단을 한 건으로 묶은 검출(첨부파일 등). 가장 강한 문단으로 등급을 정한다."""
    conceal = tuple(conceal)
    levels = {REVIEW: -1, LOW: 0, MID: 1, HIGH: 2}
    candidates = ((judge(v, conceal), (v.get("score") or {}).get("score") or 0) for v in verdicts)
    best = max(candidates, key=lambda item: (levels[item[0]["level"]], item[1]), default=None)
    return best[0] if best is not None else judge(None, conceal)
