"""지난 검색 목록·열기 검증: 임시 폴더와 localhost 임시 서버만 쓰고 실제 API·사이트에는 접속하지 않는다."""
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'detector'))
from ui.search_job import SearchJob, RunBusy
from ui.server import Session, Handler
from search_discovery import save

AD = '카지노 가입 보너스 텔레그램 @casino777'
GOOD_OLD = 'example.test_20261019_100000_aaaaaa'
GOOD_NEW = 'example.test_20261019_110000_bbbbbb'
GOOD_NOEXTRA = 'other.test_20261018_090000_cccccc'
CORRUPT = 'example.test_20261019_120000_dddddd'
EMPTY = 'example.test_20261019_130000_eeeeee'


def make_run(target, started, titles, stopped=False):
    results = [dict(url=f'https://{target}/post{i}', status='미검사', sources=[dict(
        engine='google', query=f'site:{target} 카지노', title=t, snippet=t, search_url='https://www.google.com/search?q=x',
        page=1, searched_at=started, evidence={})]) for i, t in enumerate(titles)]
    queries = [dict(engine='google', term='카지노', query=f'site:{target} 카지노', page=1, state='collected', evidence={}),
               dict(engine='google', term='먹튀', query=f'site:{target} 먹튀', page=1, state='collected', evidence={})]
    return dict(target=target, subdomains=False, started_at=started, queries=queries, results=results,
                stopped=stopped, limit_reached=False, notes=[])


def make_records(search_root):
    """정상 3개(제출 파일 있음 2·없음 1), 손상 results.json, results.json 없는 폴더, 폴더가 아닌 파일."""
    search_root.mkdir(parents=True, exist_ok=True)
    for name, run in ((GOOD_OLD, make_run('example.test', '2026-10-19T10:00:00+09:00', [AD])),
                      (GOOD_NEW, make_run('example.test', '2026-10-19T11:00:00+09:00', ['공지사항', '안내'], stopped=True)),
                      (GOOD_NOEXTRA, make_run('other.test', '2026-10-18T09:00:00+09:00', [AD]))):
        save(run, search_root/name)
    (search_root/GOOD_NOEXTRA/'result_extra.json').unlink()
    (search_root/CORRUPT).mkdir()
    (search_root/CORRUPT/'results.json').write_text('{"target": "x", "results": [', encoding='utf-8')
    (search_root/EMPTY).mkdir()
    (search_root/EMPTY/'notes.txt').write_text('results.json 이 없는 폴더', encoding='utf-8')
    (search_root/'stray.json').write_text('{}', encoding='utf-8')


class SearchHistoryJobTests(unittest.TestCase):
    def test_list_runs_returns_only_valid_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = SearchJob(tmp)
            self.assertEqual(job.list_runs(), [])            # search_results 폴더가 아직 없어도 실패하지 않는다
            make_records(job.root)
            runs = job.list_runs()
            self.assertEqual([r['id'] for r in runs], [GOOD_NEW, GOOD_OLD, GOOD_NOEXTRA])
            new, old, noextra = runs
            self.assertEqual(new, dict(id=GOOD_NEW, target='example.test', started_at='2026-10-19T11:00:00+09:00',
                                       queries=2, urls=2, submission=0, has_report=True, stopped=True))
            self.assertEqual((old['urls'], old['submission'], old['stopped']), (1, 1, False))
            self.assertIsNone(noextra['submission'])         # 제출 파일이 없으면 null
            self.assertFalse(any(r['id'] in (CORRUPT, EMPTY) for r in runs))
            # report.html 이 없으면 has_report=False, 파일이 바뀌면 캐시가 아니라 새 값을 읽는다
            (job.root/GOOD_OLD/'report.html').unlink()
            run = make_run('example.test', '2026-10-19T10:00:00+09:00', [AD, '안내', '공지'])
            (job.root/GOOD_OLD/'results.json').write_text(json.dumps(run), encoding='utf-8')
            old = [r for r in job.list_runs() if r['id'] == GOOD_OLD][0]
            self.assertEqual((old['has_report'], old['urls']), (False, 3))
            # 목록에서 손상 파일이 된 기록은 캐시가 남아 있어도 빠진다
            (job.root/GOOD_OLD/'results.json').write_text('not json', encoding='utf-8')
            self.assertNotIn(GOOD_OLD, [r['id'] for r in job.list_runs()])

    def test_list_runs_limit_is_fifty(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = SearchJob(tmp)
            job.root.mkdir(parents=True)
            for i in range(55):
                folder = job.root/f'example.test_20261019_{i:06d}_abcdef'
                folder.mkdir()
                (folder/'results.json').write_text(json.dumps(make_run('example.test', f'2026-10-19T10:{i // 60:02d}:{i % 60:02d}+09:00', [])),
                                                   encoding='utf-8')
            runs = job.list_runs()
            self.assertEqual(len(runs), 50)
            self.assertEqual(runs[0]['started_at'], '2026-10-19T10:00:54+09:00')

    def test_open_run_rejects_path_tricks_and_unknown_or_broken_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = SearchJob(tmp)
            make_records(job.root)
            outside = Path(tmp)/'elsewhere'                  # root 밖에 있는 정상 기록
            save(make_run('example.test', '2026-10-19T09:00:00+09:00', [AD]), outside)
            for bad in ('..', '.', '', None, 123, ['x'], '../elsewhere', '..\\elsewhere', str(outside), str(outside.resolve()),
                        f'{GOOD_OLD}/..', f'{GOOD_OLD}/', f'./{GOOD_OLD}', 'C:\\Windows', 'C:', f'{GOOD_OLD}\\..\\{GOOD_NEW}',
                        f'{GOOD_OLD}\0', 'a..b'):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError):
                        job.open_run(bad)
                    self.assertIsNone(job.folder)
            for missing in ('no_such_folder', EMPTY, 'stray.json'):
                with self.subTest(missing=missing):
                    with self.assertRaises(LookupError):
                        job.open_run(missing)
            with self.assertRaises(ValueError):               # 손상된 기록은 열지 않고 현재 결과도 건드리지 않는다
                job.open_run(CORRUPT)
            self.assertIsNone(job.run)
            self.assertIsNone(job.folder)

    def test_open_run_refuses_while_running_and_fills_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = SearchJob(tmp)
            make_records(job.root)
            job.running = True
            with self.assertRaises(RunBusy):
                job.open_run(GOOD_OLD)
            self.assertIsNone(job.run)
            job.running = False
            self.assertEqual(job.open_run(GOOD_OLD), GOOD_OLD)
            status = job.status()
            self.assertEqual(status['count'], 1)
            self.assertEqual(len(status['queries']), 2)
            self.assertTrue(status['report'])
            self.assertFalse(status['resumable'])
            sub = status['submission']
            self.assertEqual(sub['count'], 1)
            self.assertEqual(sub['types'], {'SEARCH_INDEXED_AD': 1})
            self.assertEqual(Path(sub['file']), (job.root/GOOD_OLD/'result_extra.json'))
            self.assertIs(sub['merged'], False)
            self.assertEqual(job.artifact('report.html'), (job.root/GOOD_OLD/'report.html').resolve())
            # 다른 기록으로 바꿔 열면 그 기록으로 교체된다
            job.open_run(GOOD_NEW)
            self.assertEqual((job.status()['count'], job.status()['submission']['count']), (2, 0))
            # 열린 검색의 대기 질의는 이어서 회수할 수 있다
            job.run['queries'][0].update(state='pending', search_id='sid')
            self.assertTrue(job.status()['resumable'])


class SearchHistoryUITests(unittest.TestCase):
    def serve(self, tmp):
        session = Session(tmp)
        class H(Handler):
            def log_message(self, *args): pass
        H.session = session
        server = ThreadingHTTPServer(('127.0.0.1', 0), H)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        return session, server, worker

    def test_endpoints_are_guarded(self):
        import urllib.request
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as tmp:
            session, server, worker = self.serve(tmp)
            make_records(session.search.root)
            base = f'http://127.0.0.1:{server.server_port}'
            def call(path, data=None, origin=None, ctype='application/json'):
                headers = {'Content-Type': ctype}
                if origin:
                    headers['Origin'] = origin
                req = urllib.request.Request(base + path, None if data is None else json.dumps(data).encode(),
                                             headers if data is not None else {}, method='GET' if data is None else 'POST')
                try:
                    with urllib.request.urlopen(req) as r:
                        return r.status, json.loads(r.read())
                except HTTPError as exc:
                    return exc.code, json.loads(exc.read())
            try:
                code, body = call('/api/search/runs')
                self.assertEqual(code, 200)
                self.assertEqual([r['id'] for r in body['runs']], [GOOD_NEW, GOOD_OLD, GOOD_NOEXTRA])
                open_path = '/api/search/runs/open'
                self.assertEqual(call(open_path, {'run_id': GOOD_OLD})[0], 403)                          # Origin 없음
                self.assertEqual(call(open_path, {'run_id': GOOD_OLD}, 'http://evil.example')[0], 403)   # 다른 Origin
                self.assertEqual(call(open_path, {'run_id': GOOD_OLD}, base, 'text/plain')[0], 403)
                self.assertIsNone(session.search.folder)
                self.assertEqual(call(open_path, {'run_id': '../x'}, base)[0], 400)
                self.assertEqual(call(open_path, {}, base)[0], 400)
                self.assertEqual(call(open_path, {'run_id': 'nothing_here'}, base)[0], 404)
                self.assertEqual(call(open_path, {'run_id': CORRUPT}, base)[0], 400)
                session.search.running = True
                self.assertEqual(call(open_path, {'run_id': GOOD_OLD}, base)[0], 409)
                self.assertIsNone(session.search.folder)
                session.search.running = False
                self.assertEqual(call(open_path, {'run_id': GOOD_OLD}, base), (200, {'ok': True, 'run_id': GOOD_OLD}))
                self.assertEqual(session.search.folder.name, GOOD_OLD)
                code, status = call('/api/search/status')
                self.assertEqual((status['count'], status['report'], status['submission']['count']), (1, True, 1))
            finally:
                server.shutdown(); server.server_close(); worker.join()

    def test_screen_lists_opens_and_refreshes(self):
        from playwright.sync_api import sync_playwright
        from datetime import datetime
        health = {'overall': 'ok', 'providers': [{'id': 'serpapi', 'name': '구글 (SerpApi)', 'engines': ['google'],
                                                  'state': 'ok', 'message': '정상 · 남은 검색 99회'}]}
        with tempfile.TemporaryDirectory() as tmp:
            session, server, worker = self.serve(tmp)
            make_records(session.search.root)
            now = datetime.now().astimezone()
            session.entry_url = 'https://example.test/board'
            session.result = dict(started=now, finished=now, elapsed=1, pages=['https://example.test/board'], coverage={},
                                  entry_url='https://example.test/board', evidence={}, findings=[])
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with patch('ui.search_job.check_health', return_value=health), sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 1200, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(base)
                    page.evaluate('load()')
                    page.locator('#body').wait_for(state='visible')
                    page.wait_for_function("document.querySelector('#search-history-summary').textContent.includes('(3건)')")
                    # 메모리에 열린 검색이 없고 지난 검색이 있으면 검색 단계를 열 때 목록이 펼쳐져 있다
                    page.locator('#search-open').click()
                    page.locator('#searchstage').wait_for(state='visible')
                    page.wait_for_function("document.getElementById('search-history').open")
                    self.assertIn('지난 검색 보기 (3건)', page.locator('#search-history-summary').inner_text())
                    rows = page.locator('#search-history-list li')
                    self.assertEqual(rows.count(), 3)
                    first = rows.nth(0).inner_text()
                    for text in ('example.test', '질의 2건', '수집 URL 2건', '제출 반영 0건', '보고서 있음', '중지됨'):
                        self.assertIn(text, first)
                    self.assertIn('제출 반영 없음', rows.nth(2).inner_text())
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('저장 URL 0건')")
                    self.assertTrue(page.locator('#search-report').is_hidden())
                    # 열기 → 기존 상태 표시가 그 기록의 값으로 바뀐다
                    page.locator(f'button[data-run="{GOOD_OLD}"]').click()
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('저장 URL 1건')")
                    page.wait_for_function("!document.getElementById('search-submission').hidden")
                    self.assertIn('1건', page.locator('#search-submission-head').inner_text())
                    self.assertIn('result_extra.json', page.locator('#search-submission-file').inner_text())
                    self.assertTrue(page.locator('#search-report').is_visible())
                    self.assertEqual(session.search.folder.name, GOOD_OLD)
                    self.assertEqual(page.locator(f'button[data-run="{GOOD_OLD}"]').inner_text(), '열려 있음')
                    with page.expect_popup() as popup:
                        page.locator('#search-report').click()
                    report = popup.value
                    report.wait_for_load_state()
                    self.assertIn('example.test/post0', report.locator('body').inner_text())
                    report.close()
                    # 새로고침 뒤에는 열린 검색이 있으니 목록을 자동으로 펼치지 않는다(건수는 보인다)
                    page.reload()
                    page.evaluate('load()')
                    page.locator('#body').wait_for(state='visible')
                    page.locator('#search-open').click()
                    page.locator('#searchstage').wait_for(state='visible')
                    page.wait_for_function("document.querySelector('#search-history-summary').textContent.includes('(3건)')")
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('저장 URL 1건')")
                    self.assertFalse(page.locator('#search-history').evaluate('d => d.open'))
                    # 진행 중에는 열기 버튼이 잠기고, 끝나면 새 기록이 목록에 나타난다
                    page.locator('#search-history summary').click()
                    session.search.running = True
                    page.wait_for_function("[...document.querySelectorAll('#search-history-list button')].every(b => b.disabled)")
                    save(make_run('example.test', '2026-10-19T14:00:00+09:00', [AD]), session.search.root/'example.test_20261019_140000_ffffff')
                    session.search.running = False
                    page.wait_for_function("document.querySelector('#search-history-summary').textContent.includes('(4건)')")
                    page.wait_for_function("[...document.querySelectorAll('#search-history-list button')].every(b => !b.disabled)")
                    # 대상 이름 같은 문자열은 이스케이프된다
                    evil = session.search.root/'example.test_20261019_150000_999999'
                    run = make_run('example.test', '2026-10-19T15:00:00+09:00', [])
                    run['target'] = '<img src=x onerror=window.pwned=1>'
                    evil.mkdir()
                    (evil/'results.json').write_text(json.dumps(run), encoding='utf-8')
                    page.evaluate("document.getElementById('search-history').open = false; document.getElementById('search-history').open = true")
                    page.wait_for_function("document.querySelector('#search-history-summary').textContent.includes('(5건)')")
                    self.assertEqual(page.locator('#search-history-list img').count(), 0)
                    self.assertIn('<img src=x', page.locator('#search-history-list').inner_text())
                    self.assertIsNone(page.evaluate('window.pwned'))
                    self.assertFalse(errors, errors)
                    browser.close()
            finally:
                server.shutdown(); server.server_close(); worker.join()


if __name__ == '__main__':
    unittest.main(verbosity=2)
