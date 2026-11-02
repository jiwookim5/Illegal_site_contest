"""검색 API 키 설정: 모의 계정 확인과 로컬 GUI만 사용한다."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from search_providers import store_key, load_keys, key_status
from ui.server import Session, Handler


class KeyTests(unittest.TestCase):
    def test_atomic_storage_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SERPAPI_API_KEY': ''}):
            path = Path(tmp) / 'search.env'
            path.write_text('# keep\nOTHER=abc\nSERPAPI_API_KEY=old-key-123\nSERPAPI_API_KEY=duplicate\n', encoding='utf-8')
            store_key(path, 'new-test-key-123')
            self.assertEqual(path.read_text().count('SERPAPI_API_KEY='), 1)
            self.assertIn('OTHER=abc', path.read_text())
            self.assertEqual(load_keys(path)['SERPAPI_API_KEY'], 'new-test-key-123')
            before = path.read_bytes()
            with patch('search_providers.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    store_key(path, 'another-test-key')
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(tmp).glob('.search-key-*')), [])
            for bad in ('', 'secret\nOTHER=bad', 'invalid"secret', None):
                if bad is None:
                    continue
                with self.assertRaises(ValueError):
                    store_key(path, bad)
            os.environ['SERPAPI_API_KEY'] = 'environment-key'
            self.assertTrue(key_status(path)['environment'])
            with self.assertRaises(ValueError):
                store_key(path, None)
            os.environ.pop('SERPAPI_API_KEY')
            store_key(path, None)
            self.assertFalse(key_status(path)['registered'])
            self.assertIn('OTHER=abc', path.read_text())

    def test_gui_save_mask_reload_delete_and_request_guards(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SERPAPI_API_KEY': ''}):
            session = Session(tmp)
            session.search.config = Path(tmp)
            class H(Handler):
                def log_message(self, *args): pass
            H.session = session
            server = ThreadingHTTPServer(('127.0.0.1', 0), H)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            def health(keys):
                configured = bool(keys['SERPAPI_API_KEY'])
                return dict(overall='ok' if configured else 'not_configured', providers=[dict(
                    id='serpapi', name='Google', engines=['google'],
                    state='ok' if configured else 'not_configured', message='정상 · 남은 검색 42회' if configured else '키 없음')])
            try:
                with patch('ui.search_job.check_health', side_effect=health), sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width':1200, 'height':1000})
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(base)
                    page.locator('#apihealth').click()
                    page.wait_for_function("document.getElementById('keystate').textContent.includes('등록된 키가 없습니다')")
                    self.assertEqual(page.locator('#search-key').get_attribute('type'), 'password')
                    secret = 'test-secret-not-real-123'
                    page.locator('#search-key').fill(secret)
                    page.locator('#keyshow').click()
                    self.assertEqual(page.locator('#search-key').get_attribute('type'), 'text')
                    page.locator('#keysave').click()
                    page.wait_for_function("document.getElementById('keymessage').textContent.includes('저장 및 연결 확인이 완료')")
                    self.assertEqual(page.locator('#search-key').input_value(), '')
                    self.assertEqual(page.locator('#search-key').get_attribute('type'), 'password')
                    self.assertIn(secret, (Path(tmp)/'search.env').read_text())
                    for route in ('/api/search/key', '/api/search/health', '/api/search/status'):
                        self.assertNotIn(secret, page.request.get(base+route).text())
                    endpoint = base + '/api/search/key'
                    self.assertEqual(page.request.post(endpoint, data={'action':'delete'}, headers={'Origin':'https://outside.test'}).status, 403)
                    self.assertEqual(page.request.post(endpoint, data={'action':'delete'}).status, 403)
                    headers = {'Origin':base}
                    session.search.running = True
                    self.assertEqual(page.request.post(endpoint, data={'action':'delete'}, headers=headers).status, 409)
                    # localhost 별칭은 Origin 검사를 통과하고(작업 중이라 409), 이름만 비슷한 외부 주소는 막힌다.
                    port = base.rsplit(':', 1)[1].rstrip('/')
                    self.assertEqual(page.request.post(endpoint, data={'action':'delete'}, headers={'Origin':f'http://localhost:{port}'}).status, 409)
                    self.assertEqual(page.request.post(endpoint, data={'action':'delete'}, headers={'Origin':f'http://localhost.evil.test:{port}'}).status, 403)
                    session.search.running = False
                    bad = page.request.post(endpoint, data={'action':'save','key':'secret\nINJECT=x'}, headers=headers)
                    self.assertEqual(bad.status, 400)
                    self.assertNotIn('INJECT', bad.text())
                    page.reload()
                    page.locator('#apihealth').click()
                    page.wait_for_function("!document.getElementById('keydelete').disabled")
                    self.assertEqual(page.locator('#search-key').input_value(), '')
                    evidence = Path(__file__).resolve().parents[1] / '_regress' / 'search-key-ui.png'
                    evidence.parent.mkdir(exist_ok=True)
                    page.screenshot(path=str(evidence))
                    page.locator('#keydelete').click()
                    page.wait_for_function("document.getElementById('keystate').textContent.includes('등록된 키가 없습니다')")
                    self.assertNotIn(secret, (Path(tmp)/'search.env').read_text())
                    self.assertFalse(errors, errors)
                    browser.close()
            finally:
                server.shutdown(); server.server_close(); worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
