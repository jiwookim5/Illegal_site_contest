"""Six reported engine defects, checked against actual localhost pages in Edge."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from playwright.sync_api import sync_playwright, ElementHandle
import evidence
from findings import classify, walk_frame
from scan import scan
from selector_js import SELECTOR_OF
from session import BrowserSession
from urls import is_state_change_url

AD = '카지노 가입코드 REVIEW77 첫충 지급 텔레그램 @review777'
ADS = ['섹스 영상 무료', '포르노 무료 보기', 'porn free videos', '야설 무료 연재',
       '블랙잭 무료 게임', '대마 구매 텔레 @weed777']
NORMAL = ['성인사이트 차단 프로그램 무료 설치', '포르노 차단 프로그램 무료 설치',
          '섹스 영상 피해 예방 교육 무료 안내', '야설 불법 유통 단속 보도',
          '블랙잭 도박 예방 교육 자료 무료 배포', 'porn addiction prevention education',
          '대마 구매 예방 교육 텔레 @police777', '대마 재배 농가 지원 안내',
          '무료 팝콘 popcorn 영상 보기', '블랙잭 게임 규칙 설명', 'pornography research']
READS = ['/applyList.do', '/recommendList.do', '/vote/result.do', '/apply_guide.html']
BLOCKED = ['/delete.do', '/delete/list', '/apply.do', '/vote.do', '/logOut.do',
           '/signOut.do', '/applyList.do?action=delete', '/vote/result.do?mode=vote',
           '/save/apply_guide.html', '/recommendSubmit.do', '/apply/delete/result.do']
FRAMES = {
    'opacity': '<iframe style="opacity:0" src="/inner"></iframe>',
    'parent-opacity': '<div style="opacity:0"><iframe src="/inner"></iframe></div>',
    'product-opacity': '<div style="opacity:.2"><iframe style="opacity:.2" src="/inner"></iframe></div>',
    'filter': '<iframe style="filter:opacity(0)" src="/inner"></iframe>',
    'overflow': '<div style="position:relative;width:10px;height:10px;overflow:hidden"><iframe style="position:absolute;left:100px;top:100px" src="/inner"></iframe></div>',
    'clip-path': '<iframe style="clip-path:inset(50%)" src="/inner"></iframe>',
    'parent-clip': '<div style="clip-path:circle(0)"><iframe src="/inner"></iframe></div>',
    'display': '<iframe style="display:none" src="/inner"></iframe>',
    'nested': '<iframe style="opacity:0" src="/middle"></iframe>',
    'visible': '<iframe src="/inner"></iframe>',
    'partial-clip': '<iframe style="clip-path:inset(10%)" src="/inner"></iframe>',
    'partial-overflow': '<div style="position:relative;width:200px;height:200px;overflow:hidden"><iframe src="/inner"></iframe></div>',
    'escaped-overflow': '<div style="width:10px;height:10px;overflow:hidden"><iframe style="position:absolute;left:100px" src="/inner"></iframe></div>',
}
REQUESTS = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        REQUESTS.append(self.path)
        if path == '/':
            body = ''.join(f'<a href="{p}">{p}</a>' for p in
                           ['/capture', '/lexicon', '/selectors', '/lookup'] +
                           ['/frame/' + k for k in FRAMES])
        elif path == '/inner':
            body = f'<p class="ad2">{AD} FRAME</p>'
        elif path == '/middle':
            body = '<iframe style="position:absolute;left:-5000px" src="/inner"></iframe>'
        elif path == '/capture':
            body = f'<div class="hidden-box" style="position:absolute;left:-5000px"><p class="ad1">{AD} OUTER</p><iframe src="/inner"></iframe></div>'
        elif path.startswith('/frame/'):
            body = FRAMES[path.rsplit('/', 1)[-1]]
        elif path == '/lexicon':
            body = ''.join(f'<p class="sample-{i}" style="color:transparent">{text}</p>' for i, text in enumerate(ADS + NORMAL))
        elif path == '/lookup':
            body = ''.join(f'<a href="{p}">조회</a>' for p in READS + BLOCKED)
        elif path in READS or path in BLOCKED:
            body = f'<p class="ad" style="color:transparent">{AD}</p>'
        elif path == '/selectors':
            body = f'<section class="stable-post" id="stable-post"><span id="ad" style="color:transparent">{AD}</span><span>정상 안내</span></section>'
        elif path.startswith('/timer/'):
            variant = path.split('/')[2]
            body = '<div id="slides" class="a">정상 공지</div>'
            if len(path.split('/')) == 3:
                body += ''.join(f'<a href="/timer/{variant}/{i}">페이지 {i}</a>' for i in range(20))
            if variant == '1000':
                body += '<script>setInterval(()=>document.getElementById("slides").classList.toggle("b"),1000)</script>'
        elif path == '/late':
            body = '<p>정상 공지</p><script>let n=0; setInterval(()=>{if(++n===4)document.body.insertAdjacentHTML("beforeend",\'<p class="late" style="color:transparent">' + AD + '</p>\')},400)</script>'
        elif path == '/toggle-ad':
            body = '<style>.hidden{display:none}</style><p id="ad" class="hidden">' + AD + '</p><script>setInterval(()=>document.getElementById("ad").classList.toggle("hidden"),1000)</script>'
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = ('<!doctype html><meta charset="utf-8"><body>' + body).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.pw = sync_playwright().start()
        cls.browser = BrowserSession(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def rows(self, path, evidence_dir=None):
        self.browser.open(self.base + path)
        result = []
        walk_frame(self.browser.page.main_frame, '', self.browser.page.url, result, set(),
                   evidence_dir=evidence_dir, evid_map={}, primary_only=True)
        return result

    def scan_site(self, path, **kwargs):
        # scan owns its synchronous Playwright context. Run it on a separate
        # thread instead of nesting another event loop inside this test browser.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(scan, self.base + path, respect_robots=False,
                               primary_only=True, **kwargs).result()

    def test_evidence_restores_styles_and_iframe_findings(self):
        before = self.rows('/capture')
        with tempfile.TemporaryDirectory() as tmp:
            after = self.rows('/capture', tmp)
            self.assertTrue(list(Path(tmp).glob('*.png')))
        self.assertEqual([(r['location'], r['technique']) for r in before],
                         [(r['location'], r['technique']) for r in after])
        page = self.browser.page
        self.assertEqual(page.locator('.hidden-box').get_attribute('style'), 'position:absolute;left:-5000px')
        self.assertIsNone(page.locator('.ad1').get_attribute('style'))
        self.assertIsNone(page.locator('body').get_attribute('style'))

    def test_evidence_restores_on_screenshot_failure(self):
        self.browser.open(self.base + '/capture')
        page = self.browser.page
        before = page.locator('html').inner_html()
        with tempfile.TemporaryDirectory() as tmp, patch.object(ElementHandle, 'screenshot', side_effect=RuntimeError('test failure')):
            self.assertEqual(evidence.capture(page.main_frame, '.ad1', page.url, '.ad1', tmp), (None, None))
        self.assertEqual(page.locator('html').inner_html(), before)

    def test_hidden_frames_and_visible_controls(self):
        for case in FRAMES:
            with self.subTest(case=case):
                techniques = {r['technique'] for r in self.rows('/frame/' + case)}
                if case in {'visible', 'partial-clip', 'partial-overflow', 'escaped-overflow'}:
                    expected = set()
                elif case == 'nested':
                    expected = {'TRANSPARENT', 'OFFSCREEN'}
                elif case in {'opacity', 'parent-opacity', 'product-opacity', 'filter'}:
                    expected = {'TRANSPARENT'}
                else:
                    expected = {'OFFSCREEN'}
                self.assertEqual(techniques, expected)

    def test_lexicon_positive_and_negative_cases(self):
        for text in ADS:
            with self.subTest(text=text):
                self.assertTrue(classify(text)['is_ad'])
        for text in NORMAL:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)['is_ad'])
        rows = self.rows('/lexicon')
        self.assertEqual({r['evidence_text'] for r in rows}, set(ADS))

    def test_read_endpoints_and_unsafe_requests(self):
        for path in READS:
            self.assertFalse(is_state_change_url(self.base + path), path)
        for path in BLOCKED:
            self.assertTrue(is_state_change_url(self.base + path), path)
        REQUESTS.clear()
        result = self.scan_site('/lookup', max_pages=10)
        self.assertEqual({urlsplit(u).path for u in result['pages']}, {'/lookup', *READS})
        self.assertFalse(set(REQUESTS) & set(BLOCKED), REQUESTS)
        self.assertEqual(len(result['findings']), len(READS))

    def test_selector_survives_sibling_insertion(self):
        rows = self.rows('/selectors')
        self.assertEqual(len(rows), 1)
        selector = rows[0]['location']
        page = self.browser.page
        page.evaluate("document.querySelector('section').insertAdjacentHTML('afterbegin','<span>새 공지</span>')")
        self.assertEqual(page.locator(selector).get_attribute('id'), 'ad')

    def test_selector_anchor_escaping_and_duplicate_ids(self):
        page = self.browser.page
        page.set_content('<section id="stable:한글"><span>one</span><span data-target="yes">two</span></section><section id="dup"><b>one</b></section><section id="dup"><b data-target="yes">two</b></section>')
        for handle in page.locator('[data-target]').element_handles():
            selector = handle.evaluate(SELECTOR_OF)
            self.assertEqual(page.locator(selector).count(), 1)
            self.assertEqual(page.locator(selector).get_attribute('data-target'), 'yes')
            if handle.evaluate('el=>el.tagName') == 'SPAN':
                self.assertIn('#', selector)

    def test_timer_cycle_still_inspects_hidden_state_and_delayed_ads(self):
        self.assertIn('OFFSCREEN', {r['technique'] for r in self.rows('/toggle-ad')})
        self.assertIn('TRANSPARENT', {r['technique'] for r in self.rows('/late')})

    def test_21_page_repeating_timer_budget(self):
        timing = {}
        for variant in ('none', '1000'):
            start = time.perf_counter()
            result = self.scan_site('/timer/' + variant, max_pages=21)
            timing[variant] = time.perf_counter() - start
            self.assertEqual(len(result['pages']), 21)
            self.assertFalse(result['findings'])
        print('21-page elapsed:', timing, flush=True)
        # One complete binary cycle needs only its first tick, not two. Allow
        # machine overhead but reject the reproduced ~42 seconds of added wait.
        self.assertLess(timing['1000'] - timing['none'], 30)


if __name__ == '__main__':
    if '--serve' in sys.argv:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        print(f'http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()
    else:
        unittest.main(verbosity=2)
