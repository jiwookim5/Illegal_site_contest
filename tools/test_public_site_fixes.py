"""Paired, local regressions from the public-site observations (no external I/O)."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "detector"))
from findings import classify, findings_from_node
from session import wait_reactions
from urls import invalid_discovery_candidate, page_key

class PublicSiteFixes(unittest.TestCase):
    def test_public_notices_need_an_illegal_topic_not_only_contact_or_promotion(self):
        notices = [
            "개인정보 처리방침 회원가입 상담 문의 전화 02-1234-5678 https://example.org/privacy",
            "민방위 교육 안내 무료 체험 QR 코드 스마트 통지센터 https://example.org/edu",
            "탄소중립 나눔장터 참여자 모집 판매 신청 https://example.org/market",
            "정부지원금 사칭 스미싱 주의 피해 예방 예시: 지금 즉시 신청 20만원 http://***.kr/010-xxxx-xxxx",
            "기업 피해 애로사항 접수 ask16707072@korea.kr 콜센터 1670-7072 문의",
            "공식 홍보영상 이용 FAQ 회원가입 문의 press@example.org",
            "서울 정책 알리미 예약 바로가기 체험 판매 구매 실시간 50% https://example.org",
            "어린이 놀이터 안전검사 결과와 검사 업체 문의 안내 https://example.org",
        ]
        for text in notices:
            with self.subTest(text=text):
                self.assertFalse(classify(text)["is_ad"])
                node = dict(text=text, selector="#notice", transparent=False, offscreen=True, reasons=["display:none"])
                self.assertEqual(findings_from_node("http://localhost", node), [])
                # The same hidden container must still expose an injected advert.
                node["text"] += "\n카지노 가입 보너스 문의 @deal_777"
                self.assertTrue(findings_from_node("http://localhost", node))

    def test_numeric_identifiers_do_not_decode_but_obfuscated_ads_do(self):
        for text in ("ask16707072@korea.kr 문의 1670-7072", "박물관 안내 https://museum.example.org/item/7070", "문의 텔@public_help", "공식 문의 텔@ｐｕｂｌｉｃ") :
            self.assertFalse(classify(text)["is_ad"], text)
        for text in ("t0t0 가입 코드", "cas1n0 가입 보너스", "ｂｅｔ 게임 롤링 0% https://deal.example",
                     "ｐｏｋｅｒ 가입머니 즉시 지급 @deal_777", "안전한 놀이터 검증업체 순위 문의 @vip_kr", "문의 텔@𝖺𝖽𝗏𝗃𝖺𝗇𝗀"):
            self.assertTrue(classify(text)["is_ad"], text)

    def test_discovery_preserves_page_identity_and_multivalues(self):
        self.assertTrue(invalid_discovery_candidate("https://example.org/menu/undefined"))
        self.assertTrue(invalid_discovery_candidate("https://example.org/list?siteId=21&siteId=21&siteId=21"))
        self.assertFalse(invalid_discovery_candidate("https://example.org/list?id=1&id=2&id=3"))
        self.assertFalse(invalid_discovery_candidate("https://example.org/list?id=1&id=1"))
        self.assertNotEqual(page_key("https://example.org/list?page=1"),page_key("https://example.org/list?page=2"))

    def test_reaction_wait_uses_one_real_deadline(self):
        class Page:
            frames = []
            clock = 0
            def evaluate(self, *a): return 0
            def wait_for_timeout(self, ms): self.clock += ms / 1000
        page = Page()
        with patch("session.time.monotonic", side_effect=lambda: page.clock):
            wait_reactions(page, {"unfinished-request"}, 60)
        self.assertLessEqual(page.clock, 2.001)
        self.assertGreaterEqual(page.clock, 1.99)

if __name__ == "__main__": unittest.main(verbosity=2)
