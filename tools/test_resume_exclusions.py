"""Integration contracts for archived exclusions and continuation, using localhost only."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import json
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'detector'))
from test_scan_exclusions import Fixture
from scan import scan
from run_archive import RunArchive, verify
from ui.server import Session


class ResumeExclusionTests(unittest.TestCase):
    def setUp(self):
        Fixture.requests.clear()
        Fixture.removed.clear()
        class Local(Fixture):
            def do_GET(self):
                if self.path != '/link-only':
                    return super().do_GET()
                self.requests.append(self.path)
                body = b'<a href="/review?id=1">link</a>'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(body)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Local)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.rules = [dict(url=self.base + '/review?id=1', reason='Reviewed fixture')]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_resume_preserves_excluded_pages_and_does_not_reopen_them(self):
        options = dict(primary_only=True, respect_robots=False, excluded_urls=self.rules)
        first = scan(self.base + '/', max_pages=1, **options)
        self.assertGreater(first['resume_state']['pending'], 0)
        self.assertIn(self.base + '/', first['coverage']['excluded_pages'])
        second = scan(self.base + '/', resume_state=json.loads(json.dumps(first['resume_state'])), **options)
        self.assertEqual(second['resume_state']['pending'], 0)
        self.assertIsNone(second['stopped'])
        self.assertNotIn('/review?id=1', Fixture.requests)
        self.assertIn('/review?id=2', Fixture.requests)
        self.assertIn(self.base + '/', second['coverage']['excluded_pages'])
        self.assertEqual(second['coverage']['excluded_count'], 1)
        self.assertEqual(Fixture.requests.count('/'), 1)
        # Changing scope silently during a continuation would invalidate the old evidence.
        with self.assertRaisesRegex(ValueError, '설정'):
            scan(self.base + '/', resume_state=first['resume_state'], primary_only=True,
                 respect_robots=False, excluded_urls=[])

    def test_link_to_excluded_page_does_not_disable_parent_comparison(self):
        result = scan(self.base + '/link-only', excluded_urls=self.rules, respect_robots=False)
        self.assertEqual(result['coverage']['excluded_count'], 1)
        self.assertEqual(result['coverage']['excluded_pages'], [])
        self.assertEqual(result['resume_state']['pending'], 0)
        self.assertNotIn('/review?id=1', Fixture.requests)

    def test_excluded_entry_and_index_are_not_permanently_pending(self):
        url = self.rules[0]['url']
        result = scan(url, index_urls=[url], excluded_urls=self.rules, respect_robots=False)
        self.assertEqual(result['resume_state']['pending'], 0)
        self.assertEqual(result['coverage']['left_count'], 0)
        self.assertIsNone(result['stopped'])
        self.assertEqual(result['pages'], [])
        self.assertNotIn('/review?id=1', Fixture.requests)

    def test_redirect_to_excluded_page_is_not_resumable_failure(self):
        result = scan(self.base + '/redirect', excluded_urls=self.rules, respect_robots=False)
        self.assertEqual(result['resume_state']['pending'], 0)
        self.assertEqual(result['coverage']['failed_count'], 0)
        self.assertEqual(result['pages'], [])
        self.assertEqual(result['findings'], [])

    def test_restarted_session_uses_archived_rules_then_new_scan_uses_current_rules(self):
        with tempfile.TemporaryDirectory() as out:
            session = Session(out)
            session.review_store.set_exclusion(self.rules[0]['url'], 'Reviewed fixture')
            saved_rules = session.review_store.exclusions()
            opts = dict(max_pages=1, primary_only=True, respect_robots=False, excluded_urls=saved_rules)
            first = scan(self.base + '/', **opts)
            archive = RunArchive(out, self.base + '/', opts)
            archive.finish(first)
            original_manifest = (archive.path / 'manifest.json').read_bytes()
            session.review_store.set_exclusion(self.rules[0]['url'])
            session.review_store.set_exclusion(self.base + '/review?id=2', 'New exclusion')
            restarted = Session(out)
            Fixture.requests.clear()
            self.assertTrue(restarted.start_resume(archive.id, 60))
            deadline = time.monotonic() + 60
            while restarted.running and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertFalse(restarted.running)
            self.assertIsNone(restarted.error)
            self.assertIn('/review?id=2', Fixture.requests)
            self.assertNotIn('/review?id=1', Fixture.requests)
            child = Path(out) / 'runs' / restarted.result['run_id']
            meta = json.loads((child / 'run.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['options']['excluded_urls'], saved_rules)
            self.assertEqual(restarted.result['coverage']['excluded_count'], 1)
            self.assertIn(self.base + '/', restarted.result['coverage']['excluded_pages'])
            self.assertEqual((archive.path / 'manifest.json').read_bytes(), original_manifest)
            self.assertEqual(verify(archive.path), [])
            self.assertEqual(verify(child), [])
            Fixture.requests.clear()
            self.assertTrue(restarted.start(self.base + '/', 10, time_limit=60))
            deadline = time.monotonic() + 60
            while restarted.running and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertFalse(restarted.running)
            self.assertIsNone(restarted.error)
            self.assertIn('/review?id=1', Fixture.requests)
            self.assertNotIn('/review?id=2', Fixture.requests)


if __name__ == '__main__':
    unittest.main(verbosity=2)
