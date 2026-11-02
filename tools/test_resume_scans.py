"""Continuation contracts using only localhost; no live-site requests."""
import collections
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'detector'))
import resume_state
from scan import scan
from run_archive import RunArchive, verify
from ui.server import Session


class ResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = collections.Counter()
        cls.delay_a = 0
        class Local(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                cls.requests[self.path] += 1
                if self.path == '/a': time.sleep(cls.delay_a)
                if self.path == '/many':
                    body = ''.join(f'<a href="/item/{i}">안내 {i}</a>' for i in range(251))
                elif self.path == '/files':
                    body = '<a href="/one.pdf">첨부 문서.pdf</a><a href="/two.pdf">첨부 문서.pdf</a>'
                elif self.path == '/':
                    body = '<a href="/a">안내</a><a href="/b">다음</a>'
                else:
                    body = '<p style="display:none">카지노 가입 보너스</p>'
                data = ('<!doctype html><html><body>' + body + '</body></html>').encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                try:
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Local)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_scan(self, path='/', **kwargs):
        return scan(self.base + path, respect_robots=False, primary_only=True, **kwargs)

    def test_full_frontier_beyond_display_sample_and_settings_guard(self):
        first = self.run_scan('/many', max_pages=1)
        state = json.loads(json.dumps(first['resume_state']))
        self.assertEqual(len(first['coverage']['left']), 200)
        self.assertEqual(first['coverage']['left_count'], 251)
        self.assertEqual(state['pending'], 251)
        seen = self.requests['/many']
        second = self.run_scan('/many', max_pages=1, resume_state=state)
        self.assertEqual(self.requests['/many'], seen)
        self.assertEqual(second['coverage']['analyzed'], 2)
        self.assertEqual(second['resume_state']['pending'], 250)
        with self.assertRaisesRegex(ValueError, '설정'):
            self.run_scan('/many', max_pages=1, settle_ms=500, resume_state=state)
        state['engine'] = 'old-version'
        with self.assertRaisesRegex(ValueError, '변경'):
            resume_state.validate(state)

    def test_interrupted_page_replayed_and_completed_page_skipped(self):
        stop = [False]
        def status(stage, url, **counts):
            if stage == 'analyze' and url.endswith('/a'): stop[0] = True
        first = self.run_scan(status=status, should_stop=lambda: stop[0])
        self.assertEqual(first['stopped'], 'user')
        self.assertEqual(first['coverage']['analyzed'], 1)
        root_gets, a_gets = self.requests['/'], self.requests['/a']
        second = self.run_scan(resume_state=json.loads(json.dumps(first['resume_state'])))
        self.assertEqual(self.requests['/'], root_gets)
        self.assertGreater(self.requests['/a'], a_gets)
        self.assertEqual(second['coverage']['analyzed'], 3)
        self.assertEqual(second['resume_state']['pending'], 0)
        self.assertEqual(len(second['pages']), 3)
        self.assertEqual(len(second['findings']), 2)

    def test_time_stop_has_resumable_initial_state(self):
        first = self.run_scan(time_limit=.001)
        self.assertEqual(first['stopped'], 'time')
        self.assertGreater(first['resume_state']['pending'], 0)
        second = self.run_scan(resume_state=first['resume_state'])
        self.assertEqual(second['coverage']['analyzed'], 3)

    def test_forced_worker_stop_reopens_in_progress_page(self):
        import scan_worker
        first = self.run_scan(max_pages=1)
        with tempfile.TemporaryDirectory() as out:
            archive = RunArchive(out, self.base+'/', {})
            stop = [False]
            def status(info):
                if info.get('current', '').endswith('/a'): stop[0] = True
            type(self).delay_a = 5
            try:
                with patch.object(scan_worker, 'CANCEL_GRACE', .1):
                    partial = scan_worker.run_scan(self.base+'/', archive, respect_robots=False,
                        primary_only=True, resume_state=first['resume_state'], status=status,
                        should_stop=lambda: stop[0])
            finally:
                type(self).delay_a = 0
            self.assertTrue(partial.get('forced_stop'))
            self.assertEqual(partial['resume_state']['pending'], 2)
            root_count = self.requests['/']
            final = self.run_scan(resume_state=partial['resume_state'])
            self.assertEqual(final['coverage']['analyzed'], 3)
            self.assertEqual(self.requests['/'], root_count)

    def test_ui_resume_button_and_saved_round_after_restart(self):
        from playwright.sync_api import sync_playwright
        from ui.server import Handler
        with tempfile.TemporaryDirectory() as out:
            first = self.run_scan(max_pages=1)
            archive = RunArchive(out, self.base+'/', dict(max_pages=1, respect_robots=False, primary_only=True))
            archive.finish(first)
            session = Session(out)
            class UI(Handler):
                def log_message(self, *args): pass
            UI.session = session
            server = ThreadingHTTPServer(('127.0.0.1', 0), UI)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            errors = []
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.locator(f'[data-open="{archive.id}"]').click()
                    page.locator('#resume-scan').wait_for(state='visible')
                    self.assertFalse(page.locator('#resume-minutes').count())
                    page.set_viewport_size({'width': 940, 'height': 700})
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                    page.screenshot(path=str(ROOT/'_regress'/'resume-controls.png'), full_page=True)
                    page.evaluate("document.getElementById('scan-minutes').value = '50'")
                    page.locator('#resume-scan').click()
                    page.wait_for_function("document.getElementById('topmeta').textContent.includes('/ 2회')", timeout=60000)
                    child = Path(out)/'runs'/session.result['run_id']
                    self.assertEqual(json.loads((child/'run.json').read_text(encoding='utf-8'))['options']['time_limit'], 3000)
                    self.assertEqual(errors, [])
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()

    def test_optional_budget_does_not_cache_unfinished_item(self):
        from attachments import AttachmentScanner
        from image_text import ImageTextScanner
        from types import SimpleNamespace
        manners = SimpleNamespace(allowed=lambda u: True)
        task = AttachmentScanner(None, manners, None, limit=0)
        self.assertIsNone(task._fetch(self.base + '/file.pdf', '문서'))
        self.assertEqual(task.cache, {})
        self.assertEqual(len(task.deferred), 1)
        task = ImageTextScanner(None, manners, None, deadline=lambda: True)
        self.assertIsNone(task._text(self.base + '/image.png'))
        self.assertEqual(task.cache, {})
        self.assertEqual(len(task.deferred), 1)

    def test_attachment_budget_continues_without_refetching_completed_file(self):
        import attachments
        from findings import classify
        original = attachments.AttachmentScanner
        def limited(*args, **kwargs): return original(*args, limit=1, **kwargs)
        text = '카지노 가입 보너스'
        with patch.object(attachments, 'AttachmentScanner', side_effect=limited), patch.object(
                attachments, 'inspect', return_value=('pdf', [text], [classify(text)], [])):
            first = scan(self.base+'/files', attachments=True, respect_robots=False)
            self.assertEqual(first['stopped'], 'budget')
            self.assertEqual(first['coverage']['analyzed'], 0)
            count = self.requests['/one.pdf']
            second = scan(self.base+'/files', attachments=True, respect_robots=False,
                          resume_state=json.loads(json.dumps(first['resume_state'])))
            self.assertEqual(self.requests['/one.pdf'], count)
            self.assertEqual(second['resume_state']['pending'], 0)
            self.assertEqual(second['coverage']['analyzed'], 1)
            self.assertEqual(len([r for r in second['findings'] if r.get('extra_finding', '').startswith('ATTACHMENT_AD')]), 2)

    def test_link_checkpoint_does_not_repeat_finished_hosts(self):
        from link_check import LinkChecker
        from types import SimpleNamespace
        task = LinkChecker(None, None, None, lambda u: False)
        task.collect(self.base, [dict(href='https://one.invalid/', selector='a', text='1'),
                                 dict(href='https://two.invalid/', selector='b', text='2')])
        stop = [False]
        task.on_checkpoint = lambda: stop.__setitem__(0, True)
        with patch.object(task, '_get', return_value=None) as get:
            task.run(should_stop=lambda: stop[0])
            self.assertEqual(get.call_count, 1)
        state = resume_state.unpack(json.loads(json.dumps(resume_state.pack(
            resume_state.capture(task, ['links', 'completed', 'saved_rows', 'missing', 'reached'])))))
        resumed = LinkChecker(None, None, None, lambda u: False)
        resume_state.restore(resumed, state)
        with patch.object(resumed, '_get', return_value=None) as get:
            resumed.run()
            self.assertEqual(get.call_count, 1)
        self.assertEqual(len(resumed.completed), 2)

    def test_index_resume_preserves_inspect_before_reflection_order(self):
        from index_check import IndexChecker
        from search_reflect import SearchReflectScanner
        from scan_control import ScanStopped
        reflect = SearchReflectScanner(None, None)
        urls = [self.base+'/search?q=normal', self.base+'/search?q=ad']
        classify = lambda text: {'is_ad': text == 'ad'}
        first = IndexChecker(reflect, classify)
        def stopped(): raise ScanStopped('user')
        first.on_checkpoint = stopped
        with patch.object(first, '_check', return_value=None):
            with self.assertRaises(ScanStopped): first.run(urls, self.base)
        state = resume_state.unpack(json.loads(json.dumps(resume_state.pack(resume_state.capture(
            first, ['inspected', 'completed', 'later', 'saved_rows', 'checked'])))))
        second = IndexChecker(reflect, classify)
        resume_state.restore(second, state)
        def probe(url, param):
            return None if reflect.endpoint(url, param) in reflect.seen else {'unwanted-warning': True}
        with patch.object(second, '_check', return_value={'confirmed': True}) as get, patch.object(
                reflect, 'check_url', side_effect=probe):
            rows = second.run(urls, self.base)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(rows, [{'confirmed': True}])
        self.assertEqual(set(urls), second.completed)

    def test_restart_new_round_preserves_archive_rules_and_evidence(self):
        with tempfile.TemporaryDirectory() as out:
            first = self.run_scan(max_pages=1)
            parent = RunArchive(out, self.base+'/', dict(max_pages=1, respect_robots=False, primary_only=True))
            (parent.path/'evidence').mkdir()
            (parent.path/'evidence'/'sample.txt').write_text('original', encoding='utf-8')
            parent.finish(first)
            manifest = (parent.path/'manifest.json').read_bytes()
            session = Session(out)  # app restarted, nothing retained in memory
            self.assertTrue(session.list_runs()[0]['can_resume'])
            import lexicon
            category = lexicon.CATEGORIES[0][0]
            with patch.object(lexicon, category, ['changed-user-dictionary']):
                self.assertTrue(session.start_resume(parent.id, 60))
                deadline = time.monotonic()+60
                while session.running and time.monotonic()<deadline: time.sleep(.05)
            self.assertFalse(session.running)
            self.assertIsNone(session.error)
            second = session.result
            self.assertEqual(second['session_number'], 2)
            self.assertEqual(second['scan_id'], parent.id)
            self.assertEqual(second['parent_run_id'], parent.id)
            self.assertGreater(second['total_elapsed'], first['elapsed'])
            self.assertEqual(second['coverage']['analyzed'], 2)
            child = Path(out)/'runs'/second['run_id']
            self.assertEqual((child/'rules.json').read_bytes(), (parent.path/'rules.json').read_bytes())
            self.assertEqual((child/'evidence'/'sample.txt').read_text(), 'original')
            self.assertEqual((parent.path/'manifest.json').read_bytes(), manifest)
            self.assertEqual(verify(parent.path), [])
            self.assertEqual(verify(child), [])


if __name__ == '__main__': unittest.main(verbosity=2)
