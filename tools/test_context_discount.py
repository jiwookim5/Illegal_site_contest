"""감점 반복·문장 범위·우회 삽입·사용자 사전 설정 회귀."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from findings import classify
from context_evidence import assess
from normalize import normalize


class ContextDiscountTests(unittest.TestCase):
    def test_repeated_words_never_accumulate_discount(self):
        for suffix in ('예방', '예방 주의 안전 공식 ' * 15):
            verdict = classify('토토사이트 ' + suffix)
            self.assertTrue(verdict['is_ad'])
            self.assertEqual(verdict['score']['context_discount'], 0)
        once = classify('카지노 중독 예방교육 안내')['score']
        repeated = classify('카지노 중독 예방교육 예방수칙 예방캠페인 안내')['score']
        self.assertEqual(once['context_discount'], 0.5)
        self.assertEqual(repeated['context_discount'], 0.5)

    def test_distinct_families_are_bounded_and_auditable(self):
        detail = classify('카지노 피해 예방 안내 및 중독상담 지원')['score']
        self.assertEqual(detail['context_discount'], 0.8)
        self.assertEqual(len(detail['normal_evidence']), 2)
        self.assertGreater(detail['original_score'], detail['score'])
        self.assertTrue(detail['penalties'])

    def test_public_contact_is_not_a_domain_allowlist(self):
        normal = classify('카지노 피해 예방 안내 https://help.example.org')['score']
        self.assertEqual(normal['context_discount'], 0.5)
        self.assertEqual(normal['decision'], 'normal')
        ad = classify('카지노 가입코드 TEST77 https://www.gov.kr')['score']
        self.assertEqual(ad['decision'], 'ad')
        self.assertEqual(ad['context_discount'], 0)

    def test_prevention_and_report_words_cannot_cancel_live_action(self):
        for text in (
            '먹튀 피해 예방 카지노 가입 보너스',
            '카지노 광고에 속지 마세요 가입코드 TEST77 지금 가입',
            '피해 예방교육 안내\n카지노 가입코드 TEST77',
            '카지노 가입코드 TEST77\n피해 예방교육 안내',
        ):
            for strict in (True, False):
                with self.subTest(text=text, strict=strict):
                    self.assertTrue(classify(text, strict=strict)['is_ad'])

    def test_personal_contact_is_preserved_without_discount(self):
        verdict = classify('카지노 피해 예방 안내 @sample_test')
        self.assertTrue(verdict['review_candidate'])
        self.assertEqual(verdict['score']['context_discount'], 0)

    def test_disabled_caution_and_partial_words(self):
        self.assertEqual(assess(normalize('카지노 예방교육'), []), [])
        self.assertEqual(assess(normalize('자기소개서 대필'), ['기소']), [])

    def test_penalty_notice_is_not_a_sales_offer(self):
        for text in (
            '불법 토토·카지노 사이트 이용은 처벌 대상입니다. 도박 문제는 1336 으로 상담하십시오.',
            '대포통장 매입 제의를 받으면 즉시 신고하세요 (112)',
            '불법 광고 예방 교육의 예시: 카지노 가입 보너스라는 문장을 삭제합니다.',
            '식약처, 비아그라 등 발기부전치료제 불법 판매 사이트 단속',
        ):
            for strict in (True, False):
                with self.subTest(text=text, strict=strict):
                    verdict = classify(text, strict=strict)
                    self.assertFalse(verdict['is_ad'])
                    self.assertFalse(verdict['review_candidate'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
