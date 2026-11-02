"""정상 연락 창구, 근거 거리, 후보 보존과 제출 분리의 정책 회귀."""
from datetime import datetime
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from findings import classify, findings_from_node
from judgement import judge, judge_many, label_of
import report
from ui import report_html


class PrecisionPolicy(unittest.TestCase):
    def test_reference_addresses_do_not_cancel_normal_context(self):
        for text in (
            '카지노 중독 피해 예방 안내 https://www.example.org',
            '카지노 중독 피해 예방 안내 카톡 상담',
            '먹튀 피해 사례 https://www.example.org',
            '도서관 토토 독서 모임 신규 회원 가입은 무료입니다. https://www.example.org',
            '바카라 유리공예 무료 체험 https://www.example.org',
        ):
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    v = classify(text, strict=strict)
                    self.assertFalse(v['is_ad'])
                    self.assertFalse(v['review_candidate'])

    def test_generic_commercial_words_remain_candidates(self):
        for text in ('재택부업 무료 상담 모집', '백링크 무료 상담 추천', '사람찾기 무료 상담 모집'):
            v = classify(text, strict=True)
            self.assertFalse(v['is_ad'], text)
            self.assertTrue(v['review_candidate'], text)
            self.assertEqual(judge(v, ['투명 처리'])['level'], 'review')

    def test_independent_ad_is_preserved_next_to_prevention(self):
        for text in ('카지노 중독 예방 안내. 첫충 가입코드 ABC77',
                     '피해 예방 안내\n카지노 가입 보너스',
                     '도서관 토토 독서 모임. 카지노 가입 보너스',
                     '카지노 가입 보너스 https://www.example.org'):
            self.assertTrue(classify(text, strict=True)['is_ad'], text)

    def test_distant_clues_do_not_confirm_ad(self):
        for text in ('카지노 현황입니다. 문의 https://www.example.org',
                     '카지노 현황입니다.\n무료 회원 가입 안내 https://www.example.org',
                     '카지노 ' + '정기 운영 기록 ' * 30 + '담당자 @sample_777'):
            v = classify(text, strict=True)
            self.assertFalse(v['is_ad'])
            self.assertTrue(v['review_candidate'])

    def test_real_personal_contacts_are_preserved_for_review(self):
        v = classify('바카라 작품 해설 @sample_777', strict=True)
        self.assertTrue(v['review_candidate'])
        self.assertFalse(v['is_ad'])
        self.assertTrue(classify('바카라 가입 보너스 @sample_777', strict=True)['is_ad'])

    def test_hidden_candidates_are_kept_but_not_exported_as_violations(self):
        rows = findings_from_node('http://127.0.0.1/page', {
            'text': '재택부업 무료 상담 모집', 'selector': '#candidate',
            'transparent': True, 'offscreen': False, 'reasons': ['opacity:0'],
        })
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['judgement']['decision'], 'review')
        ad = dict(rows[0], location='#ad', judgement=judge(classify('첫충 가입코드 ABC77')))
        now = datetime.now().astimezone()
        res = dict(findings=rows + [ad], started=now, finished=now, elapsed=1)
        with tempfile.TemporaryDirectory() as directory:
            paths, main_count, extra_count = report.write('http://127.0.0.1/page', res, directory)
            main = json.loads(Path(paths['result.json']).read_text(encoding='utf-8'))
            self.assertEqual((main_count, extra_count), (1, 0))
            self.assertEqual(main['findings'][0]['location'], '#ad')
            self.assertEqual(len(res['findings']), 2)
        self.assertIn('경계 · 제출 제외', report_html.level_chip(rows[0]))
        # 이름을 합치기 전에 저장한 결과의 '검토 후보'도 같은 이름으로 보인다
        self.assertEqual(label_of({'level': 'review', 'label': '검토 후보'}), '경계 · 제출 제외')

    def test_document_with_confirmed_ad_is_not_downgraded_by_candidate(self):
        v = judge_many([classify('재택부업 무료 상담 모집'), classify('첫충 가입코드 ABC77')])
        self.assertEqual(v['decision'], 'ad')

    def test_specific_offers_and_proven_font_disguise_remain_ads(self):
        for text in (
            '누누티비 대체 사이트 최신 주소 무료 영화 드라마 다시보기 바로가기',
            '무료웹툰 사이트 뉴토끼 툰코 최신주소 바로가기',
            '토렌트 사이트 순위 최신 주소 무료 다운로드',
            '논문 대필 과제 대행 리포트 작성 자기소개서 대필 카톡 문의',
        ):
            self.assertTrue(classify(text)['is_ad'], text)
        self.assertTrue(classify('카지노 가입 문의 텔레그램', font_decoded=True)['is_ad'])
        # 대조군: 위장 없이 보이는 같은 글. 숨긴 글이면 업종+권하는 말(가입)로 광고다 (precision_policy.HIDDEN_PROMO)
        self.assertFalse(classify('카지노 가입 문의 텔레그램', strict=True)['is_ad'])
        self.assertTrue(classify('카지노 가입 문의 텔레그램')['is_ad'])
        self.assertFalse(classify('메모리 슬롯 무료 상담', font_decoded=True)['is_ad'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
