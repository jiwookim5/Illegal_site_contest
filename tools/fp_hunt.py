"""정상 낱말 조합으로 오탐을 찾는 무작위가 아닌 전수 검사.

공공 누리집 공지·메뉴에 흔한 낱말 두 개를 띄어 써서 붙이고, 흔한 홍보 꼬리말을 달아 판정한다.
두 낱말 어느 쪽에도 없는 업종·은어·품목 낱말이 띄어쓰기를 넘어 맞춰져 광고가 되면 오탐이다
('가입 플랜' → 입플, '첫 충전' → 첫충). 화면에 보이는 글과 숨긴 글 기준을 모두 본다.

    python tools/fp_hunt.py            # 오탐 목록과 건수
    python tools/fp_hunt.py --quiet    # 건수만 (회귀 검사용, 오탐이 있으면 종료 코드 1)
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector"))

from findings import classify            # noqa: E402
from normalize import normalize          # noqa: E402

# 공공기관 공지·메뉴·행사 안내에 흔한 낱말. 앞뒤 음절이 사전 낱말과 겹치기 쉬운 것을 일부러 섞었다
VOCAB = """
가입 신규가입 회원가입 첫 충전 충전소 전기차 플랜 요금제 플랫폼 입학 입금 입주 입장 입찰 출입 수입
먹거리 먹을거리 튀김 튀어나온 바다 이야기 안전 놀이터 어린이 메이저 리그 마이너 토요일 토론 토지 토양
카드 지도 지노 노인 바닥 카페 라이브 방송 라디오 방문 방역 오피스 피스 스텔 출장 장소 안마 마사지
샵 홈 타이 오픈 런 맵 왕 가자 가니 헬로 밤 낮 성인 인권 용품 영상 영상물 동영상 야간 동네 물건
대마 마을 초등 초대 작업 업체 대기 기간 엑스 터시 코카 인형 물 뽕나무 빙수 두부 떨어진 액상 브랜드
통장 장부 법인 개인 돈 세탁 자금 대출 출금 무직 자격 당일 일자리 신불 내구 구제 고액 알바 꿀 고수익
재택 부업 단기 파워 볼링 접속 주소 빠른 보증 구글 검색 디비 팝니다 대포 폰 유심 달림 테크 휴대폰 개통
급전 개인돈 일수 서류 방문 소액 비아 그라 시알 레비 카마 발기 미프 낙태 흥신 심부름 사람 찾기
현금 현금화 상품권 매입 신분증 위조 면허증 졸업 증명서 백링크 상위 노출 라방 프릴 유출 몰카 도촬
해외 축구 중계 졸피 스테로이드 연고 아나 바나나 레플리카 계좌 대리 인증 문자 계정 판매 아이디 대량
회원 코인 주식 팔로워 조회수 구독자 좋아요 논문 과제 대행 자기소개서 유료 확정 수익 학교 도서관 체육관
""".split()
TAILS = ("무료 이벤트 안내", "신청 바로가기 문의")


def _keywords(verdict):
    groups = verdict["score"].get("groups") or {}
    return [w for k in ("strong", "topic", "medium") for w in groups.get(k) or []]


def _partial_only(word, a, b):
    """word 가 a|b 경계를 넘어서만 나오고, 그때마다 a 의 뒷부분이나 b 의 앞부분만 끌어다 쓰는가.

    '출장 안마'처럼 두 낱말 전체가 사전 낱말을 이루면 오탐이 아니다 (띄어 쓴 광고).
    '코카 인형'(코카인)·'출장 오피스'(출장오피)처럼 낱말 일부만 쓰인 경우만 센다.
    """
    joined = a + b
    hits = [i for i in range(len(joined)) if joined.startswith(word, i)
            and i < len(a) < i + len(word)]
    return bool(hits) and all(i > 0 or i + len(word) < len(joined) for i in hits)


def hunt():
    """낱말 일부를 띄어쓰기 너머로 끌어다 맞춘 사전 낱말로 광고 판정된 문구 목록."""
    found = []
    for a, b in itertools.permutations(VOCAB, 2):
        na, nb = normalize(a), normalize(b)
        alone = na + " " + nb
        for tail in TAILS:
            text = f"{a} {b} {tail}"
            for strict in (True, False):
                v = classify(text, strict=strict)
                if not v["is_ad"]:
                    continue
                crossing = [w for w in _keywords(v) if w not in alone and w not in normalize(tail)
                            and _partial_only(w, na, nb)]
                if crossing:
                    found.append((text, "보이는 글" if strict else "숨긴 글", crossing))
    return found


if __name__ == "__main__":
    found = hunt()
    if "--quiet" not in sys.argv:
        for text, basis, words in found:
            print(f"{basis}\t{text}\t{', '.join(words)}")
    pairs = len(VOCAB) * (len(VOCAB) - 1)
    print(f"낱말 조합 {pairs}개 × 꼬리말 {len(TAILS)} × 판정 기준 2 · 띄어쓰기를 넘은 오탐 {len(found)}건")
    sys.exit(1 if found else 0)
