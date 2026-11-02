"""검색 범위(scope)·오류 구분·진행 정보 검증. 모의 API만 쓰고 실제 키·사이트에는 접속하지 않는다."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from search_discovery import registrable_domain
from search_providers import APIError, api_page, collect_api, retry_errors as real_retry
from search_submission import document
from ui.search_job import SearchJob

KEY = 'fake-test-key'
AD = '카지노 가입 보너스 텔레그램 @casino777'


def ok(*urls):
    return {'search_metadata': {'status': 'Success', 'id': 'job'},
            'organic_results': [{'link': u, 'title': AD, 'snippet': '신규 가입 보너스 지급'} for u in urls]}


class RegistrableDomainTests(unittest.TestCase):
    def test_table(self):
        for host, expected in [
                ('www.yangyang.go.kr', 'yangyang.go.kr'), ('edu.yangyang.go.kr', 'yangyang.go.kr'),
                ('lll.gm.go.kr', 'gm.go.kr'), ('a.b.c.gm.go.kr', 'gm.go.kr'), ('yangyang.go.kr', 'yangyang.go.kr'),
                ('www.school.ac.kr', 'school.ac.kr'), ('x.or.kr', 'x.or.kr'), ('www.x.or.kr', 'x.or.kr'),
                ('www.kbs.co.kr', 'kbs.co.kr'), ('a.b.hs.kr', 'b.hs.kr'), ('w.example.pe.kr', 'example.pe.kr'),
                ('www.naver.com', 'naver.com'), ('a.b.example.com', 'example.com'), ('example.com', 'example.com'),
                ('www.example.kr', 'example.kr'), ('bbs.example.kr', 'example.kr'),
                ('www.example.co.uk', 'example.co.uk'), ('x.y.example.com.au', 'example.com.au'),
                ('127.0.0.1', '127.0.0.1'), ('192.168.0.10', '192.168.0.10'), ('localhost', 'localhost'),
                ('intranet', 'intranet'), ('go.kr', 'go.kr'), ('WWW.Example.Com.', 'example.com'),
                ('xn--abc.go.kr', 'xn--abc.go.kr'), ('', '')]:
            with self.subTest(host=host):
                self.assertEqual(registrable_domain(host), expected)
        # 이미 등록 도메인이면 다시 적용해도 같다
        for host in ('www.yangyang.go.kr', 'a.b.example.com', 'www.x.or.kr'):
            self.assertEqual(registrable_domain(registrable_domain(host)), registrable_domain(host))


class Harness:
    """검색 작업을 모의 API 로 끝까지 실행하는 도구."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'search.env').write_text(f'SERPAPI_API_KEY={KEY}', encoding='utf-8')
        self.job = SearchJob(self.tmp.name)
        self.job.config = self.root
        self.hosts = []        # 수집기에 넘어온 질의 도메인
        self.fetch = lambda url, headers: ok()
        real = collect_api

        def mocked(host, terms, engines, folder, keys, **kwargs):
            self.hosts.append(host)
            return real(host, terms, engines, folder, {'SERPAPI_API_KEY': KEY}, fetch=lambda u, h: self.fetch(u, h), **kwargs)
        self.patch = patch('search_assist.collect_api', side_effect=mocked)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def go(self, **body):
        body = dict(dict(site='https://www.yangyang.go.kr/main', terms='카지노', pages=1, engines=['google']), **body)
        self.assertTrue(self.job.start(body))
        self.job.thread.join(30)
        self.assertFalse(self.job.running)
        self.assertEqual(self.job.error, '')
        return self.job.status()


class ScopeTests(Harness, unittest.TestCase):
    def queries_of(self, status):
        return [q['query'] for q in status['queries']]

    def test_domain_scope_is_default_and_includes_subdomains(self):
        self.fetch = lambda url, headers: ok('https://www.yangyang.go.kr/a', 'https://edu.yangyang.go.kr/b',
                                              'https://other.test/c')
        status = self.go()
        self.assertEqual(self.queries_of(status), ['site:yangyang.go.kr 카지노'])
        self.assertEqual(status['scope'], dict(scope='domain', query_host='yangyang.go.kr',
                                               entry_host='www.yangyang.go.kr', subdomains=True))
        self.assertEqual({r['url'] for r in self.job.run['results']},
                         {'https://www.yangyang.go.kr/a', 'https://edu.yangyang.go.kr/b'})
        self.assertEqual(status['count'], 2)

    def test_host_scope_keeps_old_behavior(self):
        self.fetch = lambda url, headers: ok('https://www.yangyang.go.kr/a', 'https://edu.yangyang.go.kr/b')
        status = self.go(scope='host')
        self.assertEqual(self.queries_of(status), ['site:www.yangyang.go.kr 카지노'])
        self.assertEqual(status['scope'], dict(scope='host', query_host='www.yangyang.go.kr',
                                               entry_host='www.yangyang.go.kr', subdomains=False))
        self.assertEqual([r['url'] for r in self.job.run['results']], ['https://www.yangyang.go.kr/a'])
        # 하위 도메인은 기존 subdomains 옵션이 정한다 (www 의 하위 이름만 포함되고 형제 edu 는 아니다)
        self.fetch = lambda url, headers: ok('https://www.yangyang.go.kr/a', 'https://edu.yangyang.go.kr/b',
                                              'https://x.www.yangyang.go.kr/c')
        status = self.go(scope='host', subdomains=True)
        self.assertTrue(status['scope']['subdomains'])
        self.assertEqual(len(self.job.run['results']), 2)

    def test_invalid_scope_rejected_before_anything_starts(self):
        for value in ('all', '', 'Domain', 5, ['domain']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.job.start(dict(site='example.test', terms='카지노', engines=['google'], scope=value))
        self.assertFalse(self.job.running)
        self.assertEqual(self.hosts, [])
        self.assertIsNone(self.job.status()['scope'])

    def test_status_before_any_search(self):
        status = SearchJob(self.tmp.name).status()
        self.assertIsNone(status['scope'])
        self.assertIsNone(status['progress'])
        self.assertEqual(status['errors'], [])

    def test_submission_keeps_entry_address_and_merges_with_existing_file(self):
        self.fetch = lambda url, headers: ok('https://edu.yangyang.go.kr/b')
        baseline_run = dict(target='www.yangyang.go.kr', started_at='2026-10-19T09:00:00+09:00',
                            finished_at='2026-10-19T09:05:00+09:00', results=[])
        baseline = document(baseline_run)
        baseline['findings'] = [dict(id='e_001', url='https://www.yangyang.go.kr/x', is_violation=True, location='div',
                                     evidence_text='본 점검 결과', technique='ETC', extra_finding='VISIBLE_AD')]
        existing = self.root / 'result_extra.json'
        existing.write_text(json.dumps(baseline), encoding='utf-8')
        status = self.go()
        self.assertEqual(self.job.run['target'], 'yangyang.go.kr')
        self.assertEqual(self.job.run['entry_host'], 'www.yangyang.go.kr')
        folder_doc = json.loads((self.job.folder / 'result_extra.json').read_text(encoding='utf-8'))
        self.assertEqual(folder_doc['meta']['entry_url'], 'https://www.yangyang.go.kr')
        self.assertEqual(len(folder_doc['findings']), 1)
        self.assertTrue(status['submission']['merged'])
        merged = json.loads(existing.read_text(encoding='utf-8'))
        self.assertEqual([f['url'] for f in merged['findings']],
                         ['https://www.yangyang.go.kr/x', 'https://edu.yangyang.go.kr/b'])
        self.assertEqual(merged['meta']['entry_url'], baseline['meta']['entry_url'])

    def test_legacy_run_without_entry_host_uses_target(self):
        run = dict(target='example.test', started_at='2026-10-19T09:00:00+09:00', results=[])
        self.assertEqual(document(run)['meta']['entry_url'], 'https://example.test')
        self.assertEqual(document(dict(run, entry_host='www.example.test'))['meta']['entry_url'],
                         'https://www.example.test')
        # 진행 중이 아닌 예전 검색(범위 정보 없음)은 입력한 호스트만 본 것으로 보인다
        self.job.run = dict(run, subdomains=True)
        self.assertEqual(self.job.status()['scope'], dict(scope='host', query_host='example.test',
                                                          entry_host='example.test', subdomains=True))


class ClassificationTests(unittest.TestCase):
    KEYS = {'SERPAPI_API_KEY': KEY}

    def test_fully_empty_is_end_of_results_not_error(self):
        data = {'search_metadata': {'status': 'Success'}, 'search_information': {'organic_results_state': 'Fully empty'}}
        hits, more, evidence = api_page('google', 'site:example.test x', 1, self.KEYS, lambda *_: data)
        self.assertEqual((hits, more), ([], False))
        self.assertIn('Fully empty', evidence['end_hint'])
        self.assertEqual(evidence['response_shape']['organic_results_state'], 'Fully empty')

    def test_missing_field_on_later_page_without_error_is_end_of_results(self):
        page2 = {'search_metadata': {'status': 'Success'}, 'search_information': {'organic_results_state': 'Results for exact spelling'}}
        with tempfile.TemporaryDirectory() as folder:
            def fetch(url, headers):
                return ok('https://example.test/a') | {'serpapi_pagination': {'next': 'x'}} \
                    if parse_qs(urlsplit(url).query)['start'] == ['0'] else page2
            run = collect_api('example.test', ['카지노'], ['google'], folder, self.KEYS, pages=3, fetch=fetch,
                              progress=lambda _: None)
            self.assertEqual([q['state'] for q in run['queries']], ['collected', 'no_results'])
            self.assertTrue(run['queries'][1]['end_reason'].startswith('결과 끝'))
            self.assertEqual(run['queries'][1]['error_detail']['page'], 2)
            self.assertIn('search_information', run['queries'][1]['error_detail']['keys'])
            self.assertEqual(run['queries'][1]['error'], '')

    def test_fully_empty_first_page_through_collector(self):
        data = {'search_metadata': {'status': 'Success'}, 'search_information': {'organic_results_state': 'Fully empty'}}
        with tempfile.TemporaryDirectory() as folder:
            run = collect_api('example.test', ['카지노'], ['google'], folder, self.KEYS, pages=2,
                              fetch=lambda *_: data, progress=lambda _: None)
            self.assertEqual([q['state'] for q in run['queries']], ['no_results'])
            self.assertIn('Fully empty', run['queries'][0]['end_reason'])

    def test_unknown_shape_stays_error_with_safe_detail(self):
        secret = 'https://serpapi.com/search?api_key=' + KEY
        cases = [
            # 1페이지에서 결과 필드가 없고 비었다는 표시도 없다
            (1, {'search_metadata': {'status': 'Success'}, 'weird': 1,
                 'search_parameters': {'api_key': KEY}}, 'API 응답에 검색 결과 필드가 없습니다'),
            # 2페이지라도 알 수 없는 error 문구가 있으면 끝으로 보지 않는다
            (2, {'search_metadata': {'status': 'Success'}, 'error': f'Unknown {KEY} failure {secret} ' + 'x' * 400},
             '검색 결과 해석 오류'),
            (1, {'search_metadata': {'status': 'Success'}, 'organic_results': 'changed'}, '형식이 변경'),
        ]
        for page, data, message in cases:
            with self.subTest(message=message):
                with self.assertRaises(APIError) as caught:
                    api_page('google', 'x', page, self.KEYS, lambda *_: data)
                self.assertIn(message, str(caught.exception))
                detail = caught.exception.detail
                self.assertEqual(detail['page'], page)
                self.assertIsInstance(detail.get('keys'), list)
                self.assertIn('search_metadata', detail['keys'])
                text = json.dumps(detail, ensure_ascii=False)
                self.assertNotIn(KEY, text)
                self.assertNotIn('https://', text)
                self.assertLessEqual(len(detail.get('error', '')), 200)
        self.assertIn('weird', cases[0][1])
        with self.assertRaises(APIError) as caught:
            api_page('google', 'x', 1, self.KEYS, lambda *_: cases[0][1])
        self.assertIn('weird', caught.exception.detail['keys'])

    def test_provider_failure_records_status_only(self):
        failed = {'search_metadata': {'id': 'job', 'status': 'Error'}, 'error': f'oops {KEY}'}
        with self.assertRaises(APIError) as caught:
            api_page('google', 'x', 1, self.KEYS, lambda *_: failed)
        self.assertEqual(caught.exception.detail['provider_status'], 'Error')
        self.assertNotIn(KEY, json.dumps(caught.exception.detail))


class ProgressAndErrorTests(Harness, unittest.TestCase):
    TERMS = '가가\n나나\n다다'

    def test_errors_and_final_progress(self):
        def fetch(url, headers):
            query = parse_qs(urlsplit(url).query)
            if query['q'][0].endswith('나나'):       # 1페이지부터 알 수 없는 모양
                return {'search_metadata': {'status': 'Success'}, 'search_parameters': {'api_key': KEY},
                        'error': f'Bad {KEY} {url}'}
            if query['start'] == ['0']:
                return ok('https://www.yangyang.go.kr/' + query['q'][0][-2:]) | {'serpapi_pagination': {'next': 'x'}}
            return {'search_metadata': {'status': 'Success'}, 'search_information': {'organic_results_state': 'Fully empty'}}
        self.fetch = fetch
        status = self.go(terms=self.TERMS, pages=2)
        self.assertEqual([(q['term'], q['page'], q['state']) for q in status['queries']],
                         [('가가', 1, 'collected'), ('가가', 2, 'no_results'), ('나나', 1, 'error'),
                          ('다다', 1, 'collected'), ('다다', 2, 'no_results')])
        self.assertEqual([(e['term'], e['page'], e['state']) for e in status['errors']], [('나나', 1, 'error')])
        error = status['errors'][0]
        self.assertTrue(error['reason'])
        self.assertIn('search_metadata', error['detail']['keys'])
        self.assertEqual(set(error), {'term', 'page', 'state', 'reason', 'detail'})
        self.assertNotIn(KEY, json.dumps(status, ensure_ascii=False))
        progress = status['progress']
        self.assertEqual(progress['terms'], ['가가', '나나', '다다'])
        self.assertEqual((progress['words_total'], progress['words_done'], progress['queries_done']), (3, 3, 5))
        self.assertTrue(progress['finished'])
        self.assertIsNone(progress['current'])
        self.assertGreaterEqual(progress['elapsed_sec'], 0)
        self.assertTrue(progress['started_at'])
        # 끝난 뒤에는 경과 시간이 멈춘다
        self.assertEqual(self.job.status()['progress']['elapsed_sec'], progress['elapsed_sec'])

    def test_progress_while_running_then_reset_on_next_search(self):
        gate, reached = threading.Event(), threading.Event()
        calls = []

        def fetch(url, headers):
            query = parse_qs(urlsplit(url).query)
            calls.append(query['q'][0])
            if query['q'][0].endswith('나나'):
                reached.set()
                gate.wait(20)
            if query['start'] == ['0']:
                return ok('https://www.yangyang.go.kr/' + query['q'][0][-2:]) | {'serpapi_pagination': {'next': 'x'}}
            return ok()
        self.fetch = fetch
        self.assertTrue(self.job.start(dict(site='www.yangyang.go.kr', terms=self.TERMS, pages=2, engines=['google'])))
        try:
            self.assertTrue(reached.wait(20))
            status = self.job.status()
            progress = status['progress']
            self.assertTrue(status['running'])
            self.assertFalse(progress['finished'])
            self.assertEqual((progress['words_total'], progress['words_done'], progress['queries_done']), (3, 1, 2))
            self.assertEqual(progress['current']['term'], '나나')
            self.assertEqual(progress['current']['page'], 1)
            self.assertEqual(progress['current']['query'], 'site:yangyang.go.kr 나나')
            self.assertEqual(progress['current']['state'], 'processing')   # 응답 전 질의를 오류로 보이지 않게
            self.assertEqual(status['errors'], [])         # 진행 중인 질의는 오류로 세지 않는다
            self.assertEqual(len(status['queries']), 3)
            self.assertEqual(status['scope']['query_host'], 'yangyang.go.kr')
        finally:
            gate.set()
            self.job.thread.join(30)
        done = self.job.status()['progress']
        self.assertEqual((done['words_done'], done['finished']), (3, True))
        # 새 검색은 진행 정보를 처음부터 다시 센다
        gate.clear()
        reached.clear()
        self.assertTrue(self.job.start(dict(site='www.yangyang.go.kr', terms='가가\n나나', pages=1, engines=['google'])))
        try:
            self.assertTrue(reached.wait(20))
            fresh = self.job.status()['progress']
            self.assertEqual((fresh['terms'], fresh['words_done'], fresh['queries_done'], fresh['finished']),
                             (['가가', '나나'], 1, 1, False))
        finally:
            gate.set()
            self.job.thread.join(30)

    def test_word_is_not_done_while_next_page_follows(self):
        job = self.job
        job.plan = dict(terms=['가가', '나나'], started_at='2026-10-19T10:00:00+09:00', started=0, ended=0)
        record = dict(term='가가', page=1, query='q', state='collected', end_reason='다음 페이지 진행')
        job.live = [record]
        self.assertEqual(job.status()['progress']['words_done'], 0)
        record['end_reason'] = '설정한 페이지 한도 도달'
        self.assertEqual(job.status()['progress']['words_done'], 1)
        record.update(state='cancelled', end_reason='사용자 중지')
        self.assertEqual(job.status()['progress']['words_done'], 0)


class RetryTests(Harness, unittest.TestCase):
    def test_retry_requests_only_error_queries(self):
        calls = []
        broken = {'search_metadata': {'status': 'Success'}, 'weird': 1}

        def first(url, headers):
            term = parse_qs(urlsplit(url).query)['q'][0]
            return broken if term.endswith('나나') else ok('https://www.yangyang.go.kr/' + term[-2:])
        self.fetch = first
        status = self.go(terms='가가\n나나', pages=1)
        self.assertEqual([e['term'] for e in status['errors']], ['나나'])
        self.assertEqual(len(self.job.run['results']), 1)

        def second(url, headers):
            calls.append(parse_qs(urlsplit(url).query)['q'][0])
            return ok('https://edu.yangyang.go.kr/new')
        self.fetch = second
        with patch('ui.search_job.retry_errors',
                   side_effect=lambda run, folder, keys, progress, stop: real_retry(
                       run, folder, {'SERPAPI_API_KEY': KEY}, progress, stop, fetch=second)):
            self.assertTrue(self.job.retry_errors())
            self.job.thread.join(30)
        self.assertEqual(self.job.error, '')
        self.assertEqual(calls, ['site:yangyang.go.kr 나나'])
        after = self.job.status()
        self.assertEqual(after['errors'], [])
        self.assertEqual([q['state'] for q in after['queries']], ['collected', 'collected'])
        self.assertNotIn('error_detail', after['queries'][1])
        self.assertEqual(after['count'], 2)
        self.assertTrue(Path(self.job.folder / after['queries'][1]['evidence']['api']).is_file())
        with self.assertRaises(ValueError):          # 더 이상 오류 질의가 없다
            self.job.retry_errors()

    def test_retry_guards(self):
        with self.assertRaises(ValueError):
            self.job.retry_errors()                  # 검색 결과 없음
        self.job.running = True
        self.assertFalse(self.job.retry_errors())
        self.job.running = False


if __name__ == '__main__':
    unittest.main(verbosity=2)
