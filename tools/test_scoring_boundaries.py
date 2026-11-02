"""띄어쓰기 경계·일상어 품목·붙여 쓴 거래 표현·판정 내역(trace) 회귀 검사."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from findings import classify  # noqa: E402

# 2026-10-19 점검에서 보이는 글 기준으로도 광고로 확정되던 정상 문구
NORMAL = [
    "전기차 첫 충전 무료 이벤트 안내",          # 첫충
    "요금제 가입 플랜 안내 바로가기 문의",       # 입플
    "신규 가입 플랜 비교 추천 이벤트",
    "작대기 하나로 그리기 체험 이벤트 무료",     # 작대기
    "자산 현금화 상담 문의 1588-0000",           # 현금화
    "스테로이드 연고 구매 시 약사와 상담",        # 스테로이드
    "코카 인형 만들기 체험 무료 신청 바로가기",   # 코카인
    "출장 오피스 대여 안내 문의 바로가기",        # 출장오피
    "유출 영상물 삭제 지원 무료 상담 신청",        # 유출영상
    "졸피뎀 구매 시 처방전이 필요합니다",          # 띄어 쓴 안내는 거래 가점 없음
]
# 띄어 쓰거나 위장해도 계속 잡아야 하는 광고
ADS = [
    "안전 놀이터 추천 텔레 @abcd1234",
    "출장 안마 010-1234-5678 24시간",
    "안전 놀이터추천 가입 보너스 텔레 @abcd1234",
    "카 지 노 가입 보너스 30% 지급",
    "토토 사이트 가입쿠폰 지급",
    "작대기 팝니다 텔레 @icejjang1",
    "작대기팝니다 비밀배송",
    "현금화 당일 입금 카톡 money01",
    "졸피뎀구매",
    "졸피뎀파는곳",
]


# 2026-10-19 개발 자료 밖에서 찾은 오류와 그 짝 (같은 낱말의 정상·광고 최소 쌍)
PAIRS = [
    # 실제 오탐: gb.go.kr 채용 신체검사서 / 품목 이름만 빽빽한 숨김 도배는 광고
    ("정상", "마약류 검사 필로폰 대마 케타민 엑스터시 코카인 아편 위와 같이 검사했습니다"),
    ("광고", "필로폰 대마초 케타민 엑스터시 물뽕 떨액"),
    ("광고", "작업대출 내구제 무직자대출 당일대출 개인돈대출"),
    # 병원·약국 안내 / 연락처·거래 표현이 붙은 판매는 광고
    ("정상", "비급여 진료비 시알리스정 20mg 1정 15,000원 비아그라정 50mg 1정 12,000원"),
    ("정상", "비아그라 시알리스 레비트라 등 전문의약품은 의사 처방이 필요합니다"),
    ("광고", "비아그라 시알리스 처방전없이 판매 카톡 abcd12"),
    # 낱말 가운데를 띄운 광고는 연락처가 있으면 잡는다 / 연락처 없는 우연한 결합은 뺀다
    ("광고", "바카 라게임 가입 보너스 지급 텔레 @abcd1234"),
    ("광고", "슬 롯머신 무료 쿠폰 지급 텔레 @abcd1234"),
    ("광고", "카지 노게임 첫 입금 보너스 텔레 @abcd1234"),
    ("광고", "출장 마사지샵 24시 010-1234-5678"),
    ("정상", "가입 플랜 안내 바로가기 문의"),
    ("정상", "전기차 첫 충전 무료 이벤트 안내"),
    # 붙여 쓴 거래 표현 / 띄어 쓴 안내
    ("광고", "졸피뎀구매"),
    ("정상", "졸피뎀 구매 시 처방전이 필요합니다"),
    # 실제 오탐: gb.go.kr 게시판 이동 목록의 숨긴 'PHOTOGELLERY'(togel) / 영문 낱말 앞뒤가 경계면 광고
    ("정상", "경북포토갤러리 (PHOTOGELLERY)"),
    ("광고", "togel online"),
    ("광고", "agentogel terpercaya"),
    ("광고", "bestslotsite 텔레 @abcd1234"),
    # '메이저사이트'(도박 은어) / 띄어 쓴 '메이저 사이트'(큰 누리집)
    ("광고", "스포츠토토 안전한 메이저사이트"),
    ("정상", "메이저 사이트 개편 안내"),
    # 처방 의약품: 처방을 건너뛴 구매 권유 / 금지·경고 안내
    ("광고", "비아그라 처방전 없이 정품 최저가"),
    ("광고", "레비트라 정품 최저가"),
    ("광고", "비아그라 정품 단속 걱정 없는 비밀배송"),
    ("정상", "비아그라는 처방전 없이 구입할 수 없습니다"),
    ("정상", "비아그라 등 발기부전 치료제 불법 판매 주의"),
    ("정상", "가짜 비아그라 정품 구별법"),
    # 전각 'ｓｉｔｅ'를 붙인 종목 이름 (요강의 닮은꼴 위장)
    ("광고", "바카라 ｓｉｔｅ 추천"),
]

# 숨긴 글에서만 광고로 보는 문구 (숨김 기준, 보임 기준). 요강 예시 '무료 슬롯 체험 바로가기'와 같은 꼴
HIDDEN_PAIRS = [
    ("광고", "정상", "무료 슬롯 체험 바로가기"),
    ("광고", "정상", "릴게임 바다이야기 무료"),
    ("광고", "정상", "홀덤 무료 체험"),
    ("광고", "정상", "토토 신규 가입 이벤트"),
    ("광고", "정상", "슬롯머신 잭팟 이벤트 참여하기"),
    ("정상", "정상", "스포츠토토 바로가기"),      # 숨긴 메뉴는 검토 후보로 남는다
    ("정상", "정상", "카지노 산업 동향 보고서"),
    # 숨긴 탭·팝업의 정상 공지 (공지 낱말, 일상어로도 쓰는 업종 이름, 영어판 누리집)
    ("정상", "정상", "청소년 홀덤 무료 체험 금지 안내"),
    ("정상", "정상", "바다이야기 축제 무료 체험 프로그램 안내"),
    ("정상", "정상", "배팅센터 무료 체험 이벤트"),
    ("정상", "정상", "카지노 관광 셔틀버스 무료 운행"),
    ("정상", "정상", "음란물 차단 프로그램 무료 설치"),
    ("정상", "정상", "Free parking slot booking"),
    # HEAD 에서도 광고로 잡던 정상 공지 (은행 환전 우대, 합법 복권 판매점)
    ("정상", "정상", "환전 우대 쿠폰 지급 안내"),
    ("정상", "정상", "스포츠토토 판매점 모집 안내"),
]


class PairTest(unittest.TestCase):
    def test_minimal_pairs(self):
        for want, text in PAIRS:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertEqual(classify(text, strict=strict)["is_ad"], want == "광고")

    def test_hidden_offer_pairs(self):
        for hidden, visible, text in HIDDEN_PAIRS:
            for strict, want in ((False, hidden), (True, visible)):
                with self.subTest(text=text, strict=strict):
                    self.assertEqual(classify(text, strict=strict)["is_ad"], want == "광고")


class BoundaryTest(unittest.TestCase):
    def test_normal_phrases_are_not_ads(self):
        for text in NORMAL:
            for strict in (True, False):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)["is_ad"])

    def test_spaced_and_disguised_ads_remain(self):
        for text in ADS:
            with self.subTest(text=text):
                self.assertTrue(classify(text)["is_ad"])

    def test_trace_explains_final_score(self):
        for text in ("졸피뎀구매", "먹튀 예방 캠페인: 안전놀이터 광고에 속지 마세요",
                     "카지노 쿠폰 이벤트 무료 체험 바로가기 추천 순위"):
            with self.subTest(text=text):
                detail = classify(text)["score"]
                trace = detail["trace"]
                self.assertEqual(trace[0]["step"], "기본 점수")
                self.assertAlmostEqual(trace[-1]["score"], detail["score"], places=3)
                self.assertAlmostEqual(sum(s["delta"] for s in trace), detail["score"], places=3)

    def test_long_base64_value_is_fast_and_not_an_ad(self):
        # 목포 누리집 og:description 처럼 본문을 base64 로 넣은 긴 값. 주소 정규식이 길이의 제곱으로
        # 느려져 판정이 몇 분씩 멈췄고, 숫자를 되돌려 읽은 'sl0t'·'t0t0' 가 광고로 판정됐다
        import base64
        import time
        blob = base64.b64encode(("게시글 본문 sl0t t0t0 buy " * 9000).encode()).decode()
        blob = blob[:5000] + "Sl0tT0t0Buy" + blob[5000:]
        start = time.perf_counter()
        self.assertFalse(classify(blob)["is_ad"])
        self.assertFalse(classify("안내 " + blob + " 바로가기", strict=True)["is_ad"])
        self.assertLess(time.perf_counter() - start, 3)
        # 광고 문구는 덩어리 앞뒤에 있어도 그대로 판정한다
        self.assertTrue(classify(blob + " 카지노사이트 가입 첫충 텔레 @casino77")["is_ad"])

    def test_gambling_victim_stories_are_not_ads(self):
        # 2026-10-20 한국도박문제예방치유원 상담 사례·예방 글과 법무부 예방 웹툰. 문장 하나만 떼면
        # '토토 등을 구입'·'먹튀를 당했어요'·'200만 원에 삽니다'가 광고처럼 읽혔다
        normal = [
            "게임장에 가면 돈을 내야하고, 경마장이나 카지노에도 돈을 내게 됩니다. 당신이 도박을 하는 곳에 가거나, "
            "복권, 토토 등을 구입하는 것은 분명 돈을 쓰는 행동이라는 점입니다. 반드시 기억하세요. 도박은 돈을 잃는 과정입니다.",
            "도박에서 이겼는데 업체에서 돈을 주지 않고 먹튀를 하면 상당히 화가 나겠지요.\n"
            "수사기관에 그 업체를 사기죄 등으로 신고하는 방안을 적극적으로 고려해 보는 것이 좋을 듯합니다.",
            "청소년들이 주로 하는 도박은 사설 불법 온라인 도박(사설토토, 사다리, 달팽이, 블랙잭, 룰렛, 슬롯머신 등), "
            "온라인 전자복권(행운의 파워볼 등)입니다.",
            "불법 온라인 카지노",
            "저희 자녀가 도박을 하다가 먹튀를 당해서 5백만 원을 잃고, 만회하려다가 더 큰 빚을 지게 됐다고 해요.",
            "고등학생인데 불법 스포츠 도박을 해서 돈을 땄어요. 그런데 업체에서 돈을 주지 않고 먹튀를 당했어요.",
            "투자사기\n정착금을 다 날렸어요.\n개인통장 1개당 200만 원에 삽니다\n빚을 내서라도 돌려받고 싶었어요.",
        ]
        for text in normal:
            for strict in (True, False):
                with self.subTest(text=text[:30], strict=strict):
                    self.assertFalse(classify(text, strict=strict)["is_ad"])
        # 광고는 같은 낱말을 '당하지 마세요'·'불법 아닌'·'걱정 없는'으로 쓰고 가입 혜택·연락처를 붙인다
        ads = [
            "먹튀 당하지 마세요 메이저 토토사이트 가입 첫충 20% 텔레 @major77",
            "불법 토토 아닌 합법 메이저사이트 가입코드 abc123",
            "불법 토토사이트 말고 안전한 메이저 토토사이트 추천 바로가기",
            "먹튀 당했다면 저희가 보상합니다 토토사이트 가입 보너스 지급",
            "도박으로 돈을 잃은 분들 환영 카지노사이트 첫충 30% 텔레 @casino77",
            "먹튀를 당했어요.\n메이저 토토사이트 추천 텔레 @abcd1234",
            "사기죄 걱정 없는 통장 삽니다 개인통장 200만원 텔레 @bank77",
            "빚이 많아 걱정이세요? 토토사이트 충전 즉시 환전",
        ]
        for text in ads:
            for strict in (True, False):
                with self.subTest(text=text, strict=strict):
                    self.assertTrue(classify(text, strict=strict)["is_ad"])

    def test_search_spam_titles_and_game_money(self):
        # 2026-10-20 광주교육청 어린이 누리집 배너모음: '이름 | ✅구글검색 ○○✅ 소개' 꼴 도배 글이
        # 세로줄에서 두 문장으로 나뉘어 검토 후보로만 남았고, 긴 본문은 문장마다 기준에 못 미쳤다
        ads = [
            "야동티비 | ✅구글검색 빠른주소✅ 스트레스 제로! 압도적 화질과 속도의 미디어 플랫폼",
            "뉴토끼 | ✅구글검색 빠른주소✅ 24시간 풀가동! 지연 없는 오늘자 뉴토끼 실시간 안내소",
            "스포츠 무료중계 | ✅구글검색 벳모아티비✅경기 어디서 봐? 무조건 여기!",
            "대출의 꿈 | ✅구글검색 빠른주소✅ 복잡한 인증 절차 아웃! 터치 몇 번으로 꽂히는 쾌속 모바일 펀딩. "
            "예상치 못한 현금 부족 사태, 이젠 아쉬운 소리 할 필요 없이 당일 입금. 업체 검증 완료.",
            # 2008 대전시 자유게시판 사행성 게임 환전 광고
            "매일 4회 무료충전, 무료게임만으로 모은칩은실버로신청 현금화,",
            "게임머니 환전 즉시 가능 맞고 포커 텔레 @game77",
        ]
        for text in ads:
            for strict in (True, False):
                with self.subTest(text=text[:30], strict=strict):
                    self.assertTrue(classify(text, strict=strict)["is_ad"])
        normal = [
            "홈 | 기관소개 | 민원안내 | 정보공개",          # 세로줄이 여럿인 메뉴는 계속 나눠 본다
            "청소년 도박 예방 | 상담 안내",
            "게임머니 환전 불법입니다 신고하세요",
            "강원랜드 카지노 칩 환전 안내: 칩은 환전소에서 현금으로 교환하실 수 있습니다",
            "반도체 칩 수요 급증, 보유 자산 현금화 나선 기업들",
            "카드포인트 현금화 서비스 안내",
        ]
        for text in normal:
            for strict in (True, False):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)["is_ad"])

    def test_search_badge_and_illegal_streaming(self):
        # 2026-10-20 광주교육청 배너모음 재점검에서 놓친 글: 검색 유도 표식만 있는 대출 글(품목 상한),
        # '피해사례'·'주의하세요'를 섞어 쓴 도배 글(경고 문맥), 업종 낱말이 없는 '통티비' 불법 스포츠 중계 글
        ads = [
            "청년대출 | ✅구글검색 빠른주소✅ 대학생·취준생·사회초년생을 위한 맞춤형 금융 길잡이 '대출의 꿈'",
            "꽁타 | ✅구글검색 꽁타✅ 빛보다 빠른 접속! 차단을 뚫는 우회 센터. 토토 먹튀 피해사례 없는 검증 주소. "
            "가입 코드 입력 시 VIP 즉시 혜택.",
            "링크모음 | ✅구글검색 빠른주소✅ 핫플 바로 연결. 놀이터 순위 추천. 가입 보너스 즉시 충전. "
            "사칭 사이트를 주의하세요.",
            "⚾통티비⚾ 야구 무료중계는 통티비가 정답인 이유. 통티비 바로가기",
            "통티비-마침내 찾은 완벽함, 버퍼링 없는 해외 스포츠 실시간 중계",
            "\"돈 내면 바보?\" 해외스포츠중계 종결자 '통티비' 등장! 모바일 실시간 고화질",
            # 도배 글은 '지구촌 축제', '경기장', '방송사', '불법 사이트'도 섞어 쓴다
            "스포츠중계 보러가기. 지구촌 축제 월드컵, 방송사 유료 중계 대신 경기장 열기 그대로 버퍼링 없는 통티비",
        ]
        for text in ads:
            for strict in (True, False):
                with self.subTest(text=text[:30], strict=strict):
                    self.assertTrue(classify(text, strict=strict)["is_ad"])
        normal = [
            "시민 축구대회 실시간 중계 입장 안내 (경기장 입장 시간 18시)",
            "월드컵 거리응원 안내: 광장 대형 스크린 실시간 중계, 입장 무료",
            "프로야구 개막전 실시간 중계 입장권 예매 안내",
            "KBS 스포츠중계 편성 안내: 프로야구 무료중계 일정",
            "구민 체육대회 무료 실시간 중계 바로가기",
            "OO축제 개막식 실시간 중계 보러가기",
            "전국체전 개막식은 유튜브로 실시간 중계합니다. 생중계 보러가기",
            "해외 축구 중계 고화질 끊김없는 시청 환경 개선 사업 안내",
            "야구 중계권 협상 난항, 구독료 인상 우려",
            "불법 스포츠 중계 사이트 이용은 저작권 침해입니다. 무료중계 바로가기 광고에 주의하세요",
        ]
        for text in normal:
            for strict in (True, False):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)["is_ad"])

    def test_word_pair_hunt_finds_nothing(self):
        import fp_hunt
        self.assertEqual(fp_hunt.hunt(), [])


if __name__ == "__main__":
    unittest.main()
