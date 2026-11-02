"""Local shutdown lifecycle tests. Scan/search work is synthetic; Edge ownership is real."""
from datetime import datetime, timezone
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'detector'))
from run_archive import verify
from ui.server import Handler, Session, _Server, _watchdog
from ui import native
from ui.window import open_app_window


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.session = Session(self.temp.name)
        class UI(Handler):
            session = self.session
        self.server = _Server(('127.0.0.1', 0), UI)
        self.serving = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.serving.start()
        self.closed = threading.Event()
        self.server.register_window(self.closed.set)

    def tearDown(self):
        self.session.running = self.session.rechecking = self.session.search.running = False
        self.server.request_shutdown()
        self.server.exit_thread.join(10)
        self.serving.join(5)
        self.server.server_close()
        self.temp.cleanup()

    def post(self, path, body=None):
        request = Request(f'http://127.0.0.1:{self.server.server_port}{path}',
                          data=json.dumps(body or {}).encode(), headers={'Content-Type':'application/json'})
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    def test_quit_waits_for_partial_result_and_rejects_new_work(self):
        stopping, release, replied = threading.Event(), threading.Event(), threading.Event()
        errors = []
        def scan(url, archive, should_stop, **kwargs):
            deadline = time.monotonic() + 10
            while not should_stop() and time.monotonic() < deadline:
                time.sleep(.01)
            assert should_stop()
            stopping.set()
            assert release.wait(10)
            now = datetime.now(timezone.utc)
            return dict(started=now, finished=now, elapsed=.1, pages=[url], findings=[],
                        coverage={}, stopped='user')
        def quit_app():
            try:
                self.assertTrue(self.post('/api/quit')['ok'])
            except Exception as exc:
                errors.append(exc)
            finally:
                replied.set()
        with patch('ui.server.run_scan', side_effect=scan):
            self.assertTrue(self.session.start('http://127.0.0.1/example', 1))
            request = threading.Thread(target=quit_app)
            request.start()
            try:
                self.assertTrue(stopping.wait(5))
                self.assertFalse(replied.is_set())
                self.assertFalse(self.closed.is_set())
                with self.assertRaises(HTTPError) as rejected:
                    self.post('/api/scan', {'url':'http://127.0.0.1/next'})
                self.assertEqual(rejected.exception.code, 409)
            finally:
                release.set()
                request.join(10)
        self.assertFalse(errors, errors)
        self.assertTrue(self.closed.wait(5))
        self.assertIsNone(self.session.error)
        saved = json.loads((Path(self.temp.name)/'last_result.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['stopped'], 'user')
        self.assertEqual(saved['pages'], ['http://127.0.0.1/example'])
        self.assertEqual(verify(Path(self.temp.name)/'runs'/saved['run_id']), [])
        self.assertEqual(Session(self.temp.name).result['pages'], saved['pages'])

    def test_window_close_waits_for_search_and_recheck(self):
        self.session.search.running = self.session.rechecking = True
        self.server.request_shutdown()
        self.assertTrue(self.session.search.stop.wait(2))
        self.assertTrue(self.session.stop_requested)
        self.assertFalse(self.closed.is_set())
        self.session.rechecking = False
        self.assertFalse(self.closed.is_set())
        self.session.search.running = False
        self.assertTrue(self.closed.wait(5))
        first = self.server.exit_thread
        self.server.request_shutdown()
        self.assertIs(self.server.exit_thread, first)

    def test_pagehide_uses_same_shutdown_path(self):
        self.session.bye_at = time.time()-4
        _watchdog(self.session, self.server, bye_grace=0)
        self.assertTrue(self.closed.wait(5))
        self.assertTrue(self.session.closing)

    def test_idle_quit_closes_registered_window(self):
        self.assertTrue(self.post('/api/quit')['ok'])
        self.assertTrue(self.closed.wait(5))

    def test_disconnected_quit_still_closes_window(self):
        def disconnected(*args):
            raise BrokenPipeError('client closed while saving')
        handler = SimpleNamespace(server=self.server, _send=disconnected)
        with self.assertRaises(BrokenPipeError):
            Handler._post(handler, urlparse('/api/quit'), self.session, {})
        self.assertTrue(self.closed.wait(5))


class WindowTests(unittest.TestCase):
    def test_native_x_defers_until_shutdown_finishes(self):
        handlers, closers, requests, destroyed = [], [], [], []
        class Event:
            def __iadd__(self, handler):
                handlers.append(handler)
                return self
        window = SimpleNamespace(events=SimpleNamespace(closing=Event()), destroy=lambda:destroyed.append(True))
        def start():
            self.assertFalse(handlers[0]())
            self.assertEqual(requests, [True])
            self.assertFalse(destroyed)
            closers[0]()
            self.assertNotEqual(handlers[0](), False)
        fake = SimpleNamespace(create_window=lambda *args,**kwargs:window, start=start)
        with patch.dict(sys.modules, {'webview':fake}):
            self.assertTrue(native.run('http://127.0.0.1/', 'test',
                                      on_close=lambda:requests.append(True), register_close=closers.append))
        self.assertEqual(destroyed, [True])

    def test_close_only_owned_edge_process_and_profile(self):
        spawn = subprocess.Popen
        def headless(args, **kwargs):
            # A local endpoint lets us observe the real browser, even when Edge's launcher exits.
            return spawn([args[0], '--headless=new', '--remote-debugging-port=0', *args[1:]], **kwargs)
        def endpoint(window):
            marker = Path(window.profile.name)/'DevToolsActivePort'
            deadline = time.monotonic()+10
            while time.monotonic()<deadline:
                if marker.exists():
                    lines = marker.read_text().splitlines()
                    if lines:
                        url = f'http://127.0.0.1:{int(lines[0])}/json/version'
                        try:
                            with urlopen(url,timeout=1) as response:
                                self.assertIn('Browser', json.load(response))
                            return url
                        except OSError:
                            pass
                time.sleep(.05)
            self.fail('Owned Edge did not expose its local endpoint')
        windows = []
        with patch('ui.window.subprocess.Popen', side_effect=headless):
            try:
                windows = [open_app_window('about:blank'), open_app_window('about:blank')]
                first, other = windows
                self.assertIsNotNone(first.process)
                self.assertIsNotNone(other.process)
                first_url, other_url = endpoint(first), endpoint(other)
                first_profile = Path(first.profile.name)
                other_profile = Path(other.profile.name)
                first.close()
                self.assertIsNotNone(first.process.poll())
                with self.assertRaises(OSError):
                    urlopen(first_url,timeout=1)
                with urlopen(other_url,timeout=1) as response:
                    self.assertIn('Browser',json.load(response))
                self.assertFalse(first_profile.exists())
                self.assertTrue(other_profile.exists())
            finally:
                for window in windows:
                    window.close()


def check_exe(exe):
    """Real packaged GUI backend, local hung page, and headless UI; no native-window claim."""
    from playwright.sync_api import sync_playwright
    from test_scan_control import Fixture
    from regress import _api, _free_port
    out = ROOT/'_regress'/('gui-shutdown-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    out.mkdir()
    target = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=target.serve_forever, daemon=True).start()
    rows = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            for mode in ('idle', 'running', 'reopen'):
                folder = out/('running' if mode=='reopen' else mode)
                folder.mkdir(exist_ok=mode=='reopen')
                log = out/f'{mode}.log'
                with log.open('wb') as stream:
                    port = _free_port()
                    app = subprocess.Popen([str(exe.resolve()), '--no-browser', '--port', str(port), '--out', str(folder)],
                                           stdout=stream, stderr=stream,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    page = browser.new_page(viewport={'width':1200,'height':800})
                    errors = []
                    page.on('pageerror', lambda error:errors.append(str(error)))
                    page.on('dialog', lambda dialog:dialog.accept())
                    try:
                        deadline = time.monotonic()+30
                        while time.monotonic()<deadline:
                            try:
                                _api(port, '/api/status', timeout=1)
                                break
                            except OSError:
                                pass
                            assert app.poll() is None, log.read_text(encoding='utf-8',errors='replace')
                            time.sleep(.1)
                        else:
                            raise AssertionError('packaged GUI startup timeout')
                        page.goto(f'http://127.0.0.1:{port}/')
                        if mode=='running':
                            page.locator('#url').fill(f'http://127.0.0.1:{target.server_port}/')
                            page.locator('#go').click()
                            deadline = time.monotonic()+30
                            while time.monotonic()<deadline:
                                state = _api(port, '/api/status')
                                if state['current'].endswith('/hang') and state['pages_done']>=1:
                                    break
                                assert not state['error'], state
                                time.sleep(.1)
                            else:
                                raise AssertionError('scanner did not reach the local hung page')
                            page.screenshot(path=str(out/'running.png'),full_page=True)
                        if mode=='reopen':
                            saved = _api(port, '/api/result')
                            assert saved['meta']['stopped']=='user', saved['meta']
                            assert saved['meta']['page_count']>=1, saved['meta']
                            page.locator('#runsbox').wait_for(state='visible')
                            page.screenshot(path=str(out/'restored.png'),full_page=True)
                        started = time.monotonic()
                        page.locator('#quit').click()
                        page.locator('#askok').click()       # 화면 안 확인 창에서 [종료]
                        assert app.wait(timeout=15)==0
                        elapsed = time.monotonic()-started
                        assert not errors, errors
                        row = dict(mode=mode, quit_seconds=round(elapsed,3), page_errors=errors)
                        if mode=='running':
                            saved = json.loads((folder/'last_result.json').read_text(encoding='utf-8'))
                            assert saved['stopped']=='user', saved
                            assert saved['pages'] and saved['findings'], saved
                            assert verify(folder/'runs'/saved['run_id'])==[]
                            row.update(pages=len(saved['pages']),findings=len(saved['findings']),stopped=saved['stopped'])
                        rows.append(row)
                    finally:
                        page.close()
                        if app.poll() is None:
                            if port:
                                try:_api(port, '/api/quit', {}, timeout=10)
                                except OSError:pass
                            try:app.wait(timeout=15)
                            except subprocess.TimeoutExpired:app.kill();app.wait()
            browser.close()
        (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(rows,ensure_ascii=False))
        print(out)
    finally:
        target.shutdown()
        target.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args, remaining = parser.parse_known_args()
    if args.exe:
        check_exe(args.exe)
    else:
        unittest.main(argv=[sys.argv[0],*remaining], verbosity=2)
