"""복합 정상 문맥과 같은 구조의 광고를 짝지어 검사한다."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from findings import classify, walk_frame
from playwright.sync_api import sync_playwright


class ContextPairs(unittest.TestCase):
    def test_benign_semantics_do_not_become_ads_when_hidden_or_transformed(self):
        samples = [
            '민원 예약 슬롯별 무료 상담 시간을 확인하세요.',
            '토토와 함께하는 어린이 책놀이, 무료 참여',
            '도서관 토토 독서 모임 신규 회원 가입은 무료입니다.',
            '바카라 크리스털 유리잔 전시 무료 관람 안내',
            'ＢＡＣＣＡＲＡＴ 유리공예 도록 무료 배부',
            '바카라 작품 해설 무료 예약',
            '야동동 마을 사진전 무료 관람 신청',
            '카지노 종사자 현황 통계',
            'ＣＡＳＩＮＯ 산업분류 코드의 변경 이력을 보관합니다.',
            '카지노 통계 무료 열람 안내',
            '카지노 이용으로 생활이 어려운 분에게 무료 상담을 제공합니다.',
        ]
        for text in samples:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)['is_ad'])

    def test_independent_lures_override_benign_vocabulary(self):
        samples = [
            '도서관 토토 가입 보너스', '책놀이 토토 첫충 혜택',
            '토토 자동화 가입 보너스', '바카라 유리공예 가입 보너스',
            '바카라 유리한 승률 가입 보너스',
            '야동동 마을 최신주소 offer777.vip', '카지노 통계 첫충 보너스',
            '예약 슬롯 보너스 가입',
            '도서관 토토 가입 보\u200b너스', '바카라 작품 해설 가입코드 BONUS77',
        ]
        for text in samples:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertTrue(classify(text, strict=strict)['is_ad'])

    def test_normal_context_with_personal_contact_is_reviewable_not_confirmed(self):
        for text in ('바카라 작품 해설 @sample_777', '카지노 생활이 어려운 분 @sample_777'):
            for strict in (False, True):
                verdict = classify(text, strict=strict)
                self.assertFalse(verdict['is_ad'])
                self.assertTrue(verdict['review_candidate'])

    def test_visible_bonus_offer_including_symbol_split_is_an_ad(self):
        for text in ('카지노 가입 보너스', '카.지.노 가입 보너스'):
            with self.subTest(text=text):
                self.assertTrue(classify(text, strict=True)['is_ad'])

    def test_fullwidth_gambling_words_remain_ads_while_normal_acronyms_do_not(self):
        for text in (
            '해외 라이브 ｂｅｔ 게임 공식인증업체 롤링 0% 미러 도메인 safe-fast.top',
            '토너먼트 ｐｏｋｅｒ 게임 추천 가입머니 즉시 지급 @deal_hg18',
        ):
            with self.subTest(text=text):
                result = classify(text, strict=True)
                self.assertTrue(result['is_ad'], result)
                self.assertTrue(result['homoglyph'], result)
        for text in ('ＱＲ코드 이벤트 무료 지급 안내',
                     'ａｌｐｈａｂｅｔ 표기와 ＡＩ 안내, 무료 이벤트 추천',
                     '도서관 ＶＩＰ 이벤트 무료 지급 안내'):
            with self.subTest(text=text):
                self.assertFalse(classify(text, strict=True)['is_ad'])


class BrowserPairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def findings(self, body):
        page = self.browser.new_page(viewport={'width': 1280, 'height': 800})
        try:
            page.set_content('<!doctype html><html><body>' + body + '</body></html>')
            rows = []
            walk_frame(page.main_frame, '', page.url, rows, set())
            result = []
            for row in rows:
                element = page.query_selector(row['location'])
                self.assertIsNotNone(element, row)
                identity = element.evaluate('(e) => e.closest("[id]")?.id')
                result.append((identity, row.get('extra_finding') or row['technique']))
            return result
        finally:
            page.close()

    def test_comment_details_are_opened_before_classification(self):
        from session import BrowserSession
        session = BrowserSession(self.pw)
        ad = '조건만남 실시간 매칭 프로필 문의 @sample_777'
        try:
            session.page.set_content(f"""<body>
              <details id="visible-panel"><summary><span>댓글 펼치기</span></summary><p id="visible">{ad}</p></details>
              <details id="transparent-panel"><summary>댓글 더보기</summary><p id="transparent" style="opacity:0">{ad}</p></details>
              <details id="offset-panel"><summary>답글 펼치기</summary><p id="offset" style="position:absolute;left:-9999px">{ad}</p></details>
              <details id="already" open><summary>댓글 더보기</summary><p>{ad}</p></details>
              <details id="generic"><summary>자세히</summary><p id="still-hidden">{ad}</p></details>
              <details id="risky"><summary id="delete-comments">댓글 펼치기</summary><p>{ad}</p></details>
            </body>""")
            session.expand()
            session.expand()
            for identity in ('visible-panel', 'transparent-panel', 'offset-panel', 'already'):
                self.assertTrue(session.page.locator('#' + identity).evaluate('(e) => e.open'))
            for identity in ('generic', 'risky'):
                self.assertFalse(session.page.locator('#' + identity).evaluate('(e) => e.open'))
            rows = []
            walk_frame(session.page.main_frame, '', session.page.url, rows, set())
            found = {(session.page.locator(row['location']).get_attribute('id'),
                      row.get('extra_finding') or row['technique']) for row in rows}
            self.assertIn(('visible', 'VISIBLE_AD(게시판 노출 광고)'), found)
            self.assertNotIn(('visible', 'OFFSCREEN'), found)
            self.assertIn(('transparent', 'TRANSPARENT'), found)
            self.assertNotIn(('transparent', 'OFFSCREEN'), found)
            self.assertIn(('offset', 'OFFSCREEN'), found)
            self.assertIn(('still-hidden', 'OFFSCREEN'), found)
        finally:
            session.browser.close()

    def test_local_quotes_keep_hidden_linked_and_contact_ads(self):
        text = 'ｃａｓｉｎｏ 가입 보너스'
        quote = '<article><h3>수업에서 분석한 스팸 문장</h3>{}</article>'
        body = quote.format(f'<p id="normal">{text}</p>')
        body += quote.format(f'<p id="hidden" style="opacity:0">{text}</p>')
        body += quote.format(f'<p id="contact">{text} @sample_777</p>')
        body += quote.format(f'<a id="linked" href="/offer"><p>{text}</p></a>')
        body += f'<article><h3 hidden>스팸 문장 예시</h3><p id="hidden-heading">{text}</p></article>'
        body += f'<h2>스팸 문장 예시</h2><article><p id="remote-heading">{text}</p></article>'
        found = self.findings(body)
        self.assertNotIn('normal', {item[0] for item in found}, found)
        required = {(name, 'HOMOGLYPH') for name in ('hidden', 'contact', 'linked', 'hidden-heading', 'remote-heading')}
        self.assertTrue(required <= set(found), found)
        self.assertIn(('hidden', 'TRANSPARENT'), found)

    def test_code_and_table_quotes_and_self_documented_labels(self):
        text = 'ｃａｓｉｎｏ 가입 보너스'
        body = f'<h2>HTML 코드 설명</h2><pre><code id="code">&lt;p&gt;{text}&lt;/p&gt;</code></pre>'
        body += f'<h2>교재 인용문 비교</h2><table><tr><th>삭제할 메시지</th></tr><tr><td id="table">{text}</td></tr></table>'
        body += f'<button id="label" title="스팸 문자 예시: {text}">설명</button>'
        body += f'<button id="label-ad" title="스팸 문자 예시: {text} @sample_777">설명</button>'
        body += f'<button id="label-hidden" style="opacity:0" title="스팸 문자 예시: {text}">설명</button>'
        found = self.findings(body)
        # Include unlabeled parents: a spurious <pre> result must not escape this check.
        self.assertEqual({item[0] for item in found}, {'label-ad', 'label-hidden'}, found)

    def test_recovery_service_context_does_not_exempt_promotions_or_hidden_copy(self):
        section = '<section><h3>도박 중독 회복 지원</h3>{}</section>'
        body = section.format('<p id="normal">카지노 무료 상담 접수</p>')
        body += section.format('<p id="offer">카지노 무료 상담 가입 보너스</p>')
        body += section.format('<p id="contact">카지노 무료 상담 @sample_777</p>')
        body += section.format('<p id="hidden" style="opacity:0">카지노 무료 상담</p>')
        found = self.findings(body)
        self.assertNotIn('normal', {item[0] for item in found}, found)
        self.assertTrue({'offer', 'contact', 'hidden'} <= {item[0] for item in found}, found)

    def test_inactive_recovery_tab_requires_reciprocal_control_and_preserves_ad_lures(self):
        body = ''
        for name, text, reciprocal in (
            ('normal', '카지노 무료 상담 접수는 예약제로 운영합니다.', True),
            ('offer', '카지노 무료 상담 가입 보너스', True),
            ('broken', '카지노 무료 상담', False),
        ):
            body += f'<button role="tab" id="tab-{name}" aria-selected="false" aria-controls="panel-{name}">상담 안내</button>'
            label = f'tab-{name}' if reciprocal else 'missing'
            body += f'<div role="tabpanel" hidden id="panel-{name}" aria-labelledby="{label}"><h3>도박 중독 회복 지원</h3><p id="{name}">{text}</p></div>'
        found = self.findings(body)
        self.assertFalse({'normal', 'panel-normal'} & {item[0] for item in found}, found)
        self.assertTrue({'offer', 'broken'} <= {item[0] for item in found}, found)

    def test_identical_text_at_distinct_visible_and_hidden_elements_is_not_deduplicated(self):
        text = '카지노 가입코드 TEST88'
        body = f'<p id="hidden" style="opacity:0">{text}</p><p id="visible">{text}</p>'
        found = self.findings(body)
        self.assertIn(('hidden', 'TRANSPARENT'), found)
        self.assertIn(('visible', 'VISIBLE_AD(게시판 노출 광고)'), found)
        self.assertEqual(len(found), 2, found)

    def test_hidden_child_is_not_reported_again_as_visible_parent(self):
        ad = '카지노 가입코드 TEST88'
        body = f'<p id="normal-parent">정상 안내 <span id="hidden" style="color:transparent">{ad}</span></p>'
        body += f'<p id="visible">{ad} <span id="hidden-twin" style="color:transparent">{ad}</span></p>'
        body += '<p id="normal-prefix">공지 <span id="disguised">ｃａｓｉｎｏ 가입 보너스</span></p>'
        found = self.findings(body)
        self.assertEqual(set(found), {('hidden', 'TRANSPARENT'), ('hidden-twin', 'TRANSPARENT'),
            ('visible', 'VISIBLE_AD(게시판 노출 광고)'), ('disguised', 'HOMOGLYPH')}, found)

    def test_css_generated_ads_include_plain_text_and_preserve_normal_content(self):
        body = r'''<style>
          #generated::after { content: "\BC14\CE74\B77C 사이트 추천 gen77.top"; }
          #bonus::before { content: "카지노 가입 보너스"; }
          #hidden::after { content: "카지노 가입 보너스"; color: transparent; }
          #disguised::before { content: "ｃａｓｉｎｏ 가입 보너스"; }
          #normal::after { content: "새창 열림"; }
          #context::after { content: "바카라 유리잔 전시 무료 관람 안내"; }
        </style><span id="generated"></span><span id="bonus"></span>
        <span id="hidden"></span><span id="disguised"></span>
        <span id="normal"></span><span id="context"></span>'''
        found = self.findings(body)
        self.assertEqual(set(found), {('generated', 'VISIBLE_AD(게시판 노출 광고)'),
            ('bonus', 'VISIBLE_AD(게시판 노출 광고)'), ('hidden', 'TRANSPARENT'),
            ('disguised', 'HOMOGLYPH')}, found)
        self.assertEqual(len(found), 4, found)


if __name__ == '__main__':
    unittest.main(verbosity=2)
