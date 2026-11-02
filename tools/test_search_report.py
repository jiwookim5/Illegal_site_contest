"""검색 노출 점검 결과 보고서(report.html)가 점검 결과 보고서와 같은 틀이고, 값이 안전하게 나오는지 검사한다."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from search_discovery import save
from search_report import build
from ui import report_html

AD_URL = 'https://edu.example.test/bbs/view.jsp?FileName=%EC%B9%B4%EC%A7%80%EB%85%B8&x=' + 'a' * 200


def source(**extra):
    base = dict(engine='google', query='site:example.test 카지노', term='카지노', page=1,
                search_url='https://www.google.com/search?q=x', searched_at='2026-10-19T21:26:00+09:00',
                title='카지노 가입 보너스 텔레그램 @casino777', snippet='신규 가입 보너스 지급 <b>꽁머니</b>',
                evidence={'api': 'search_evidence/0001.json'})
    base.update(extra)
    return base


def run():
    return dict(target='example.test', subdomains=True, entry_host='www.example.test', mode='api',
                started_at='2026-10-19T21:22:00+09:00', finished_at='2026-10-19T21:27:47+09:00',
                stopped=False, limit_reached=False, notes=['제공자 안내 <script>alert(1)</script>'],
                results=[dict(url=AD_URL, status='미검사', sources=[source()], findings=[]),
                         dict(url='https://example.test/normal', status='미검사',
                              sources=[source(title='도서관 안내', snippet='방문 안내')], findings=[])],
                queries=[dict(engine='google', query='site:example.test 카지노', term='카지노', page=1, state='collected',
                              end_reason='다음 페이지 진행', target_links=2, new_urls=2, evidence={'api': 'search_evidence/0001.json'}),
                         dict(engine='google', query='site:example.test 카지노', term='카지노', page=2, state='error',
                              end_reason='API 오류로 해당 질의 종료', error='응답 오류', error_detail='keys=[a]', evidence={})])


class SearchReportTests(unittest.TestCase):
    def test_same_frame_and_design_as_the_scan_report(self):
        text = build(run())
        # 점검 보고서의 디자인 값(CSS)·틀을 그대로 쓴다
        self.assertIn(report_html.CSS.strip()[:200], text)
        for part in ('class="bar"', 'class="sheet"', 'class="eyebrow"', 'class="tiles"', 'class="info"', 'class="sign"',
                     '인쇄 · PDF로 저장', '검색 정보', '판정 유형별 건수', '수집한 URL 목록', '질의별 수집 상태', '진행/종료 이유'):
            self.assertIn(part, text)
        self.assertIn('<html lang="ko">', text)

    def test_numbers_and_verdicts(self):
        text = build(run())
        self.assertIn('example.test 및 하위 도메인 (입력한 주소: www.example.test)', text)
        self.assertIn('구글 (SerpApi 검색 API)', text)                      # mode 가 없는 합본 기록도 증거로 방식을 안다
        self.assertIn('class="chip ad">광고 판정', text)                    # 제목·요약이 광고인 URL
        self.assertIn('검색 제목·요약의 광고 노출', text)
        self.assertIn('class="chip">검토 필요', text)                       # 판정하지 않은 URL
        self.assertIn('확인하지 못한 질의가 1건', text)                     # 오류 질의는 광고 없음으로 보이지 않게
        self.assertLess(text.index('class="chip ad">광고 판정'), text.index('class="chip">검토 필요'))    # 광고 판정 URL 이 앞

    def test_long_url_is_readable_and_everything_is_escaped(self):
        text = build(run())
        self.assertIn('<b>edu.example.test/bbs/view.jsp</b>', text)         # 도메인·경로
        self.assertIn('카지노', text)                                         # 퍼센트 인코딩을 풀어 보여 준다
        self.assertIn('<summary>전체 주소</summary>', text)
        self.assertNotIn('<script>alert', text)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', text)
        self.assertNotIn('<b>꽁머니</b>', text)

    def test_only_relative_evidence_links(self):
        data = run()
        data['results'][0]['sources'][0]['evidence'] = {'api': 'search_evidence/0001.json', 'x': '../secret.txt',
                                                        'y': 'C:\\secret.txt', 'z': 'https://evil.test/a', 'w': '/etc/passwd'}
        text = build(data)
        self.assertIn('href="search_evidence/0001.json"', text)
        for bad in ('../secret.txt', 'C:\\secret.txt', 'evil.test/a', '/etc/passwd'):
            self.assertNotIn(f'href="{bad}"', text)

    def test_stopped_and_empty_runs_render_and_save_writes_it(self):
        data = run()
        data.update(stopped=True, limit_reached=True)
        text = build(data)
        self.assertIn('담당자가 검색을 중지해', text)
        self.assertIn('수집 URL 상한(300건)', text)
        empty = build(dict(target='example.test', started_at='2026-10-19T21:22:00+09:00', results=[], queries=[]))
        self.assertIn('수집한 URL이 없습니다', empty)
        self.assertIn('광고로 판정한 항목이 없습니다', empty)
        with tempfile.TemporaryDirectory() as folder:
            save(run(), folder)
            self.assertIn('검색엔진 노출 광고 점검 결과 보고', (Path(folder) / 'report.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
