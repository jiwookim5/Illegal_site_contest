"""모의 API와 localhost만 사용하는 검색 보조 도구 검사."""
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from search_discovery import merge_hits, recheck, save, target_host, in_scope, search_state, search_url, EXTRACT_JS
from search_providers import APIError, SearchPending, api_page, collect_api, query_plan, wait_search, resume_searches


def query():
    return dict(engine="google", query="site:example.test 카지노", term="카지노", page=1,
                searched_at="2026-10-15T10:00:00+09:00", search_url="https://www.google.com/search?q=x", evidence={})


class SearchTests(unittest.TestCase):
    def test_archive_comparison_detects_unmatched_html_and_unsaved_json(self):
        from compare_serp_archive import compare
        data = {'search_metadata': {'id': 'one'}, 'organic_results': [
            {'link': 'https://example.test/a', 'redirect_link': 'https://www.google.com/url?url=TOKEN'},
            {'link': 'https://example.test/b'}]}
        markup = '<a href="/goto?url=TOKEN"><h3>A</h3></a><a href="https://example.test/missing"><h3>Missing</h3></a>'
        result = compare(data, markup, {'search_id': 'one', 'hits': [{'href': 'https://example.test/a'}]})
        self.assertTrue(result['evidence_search_id_matches'])
        self.assertEqual(result['matched_html_count'], 1)
        self.assertEqual(result['unmatched_html_count'], 1)
        self.assertEqual(result['json_missing_from_saved'], ['https://example.test/b'])

    def test_google_includes_omitted_results_and_preserves_notice(self):
        from search_discovery import search_url
        def fetch(url, headers):
            self.assertEqual(parse_qs(urlsplit(url).query)['filter'], ['0'])
            return {'search_metadata': {'status': 'Success'}, 'organic_results': [],
                    'search_parameters': {'filter': '0', 'api_key': 'PRIVATE'},
                    'dmca_messages': {'messages': [{'content': '<b>일부 항목 생략</b>'}]}}
        _, _, evidence = api_page('google', 'site:example.test x', 1, {'SERPAPI_API_KEY': 'PRIVATE'}, fetch, include_omitted=True)
        self.assertEqual(evidence['provider_notices'], ['일부 항목 생략'])
        self.assertNotIn('PRIVATE', json.dumps(evidence))
        self.assertEqual(parse_qs(urlsplit(search_url('google', 'x', include_omitted=True)).query)['filter'], ['0'])
        self.assertNotIn('filter', parse_qs(urlsplit(search_url('google', 'x')).query))

    def test_sitelinks_pagination_counts_and_query_error_isolation(self):
        calls = []
        def fetch(url, headers):
            p = parse_qs(urlsplit(url).query)
            calls.append(p)
            if p['q'][0].endswith('bad'):
                raise APIError('failed query')
            offset = int(p['start'][0])
            items = [{'link': 'https://example.test/a', 'sitelinks': {
                'inline': [{'link': 'https://example.test/b?x=1&x=2'}],
                'expanded': [{'link': 'https://other.test/out'}, {'link': 'https://example.test/a'}]}}] if offset == 0 else [
                    {'link': 'https://example.test/c'}] if offset == 10 else []
            return {'search_metadata': {'status': 'Success'}, 'organic_results': items}
        with tempfile.TemporaryDirectory() as folder:
            run = collect_api('example.test', ['bad', 'good'], ['google'], folder,
                              {'SERPAPI_API_KEY': 'fake'}, pages=5, fetch=fetch, progress=lambda _: None)
            self.assertEqual(len(run['results']), 3)
            self.assertEqual([q['page'] for q in run['queries']], [1, 1, 2, 3])
            q = run['queries'][1]
            self.assertEqual((q['returned_links'], q['sitelinks'], q['new_urls'], q['excluded_links'], q['duplicate_or_limited_links']), (4, 3, 2, 1, 1))
            self.assertEqual(run['queries'][-1]['end_reason'], '정상 무결과')
            self.assertEqual(run['results'][1]['sources'][0]['link_kind'], 'sitelink')
            self.assertIn('진행/종료 이유', (Path(folder)/'report.html').read_text(encoding='utf-8'))

    def test_repeated_page_stops_and_page_limit_is_explicit(self):
        def fetch(*_):
            return {'search_metadata': {'status': 'Success'}, 'organic_results': [{'link': 'https://example.test/a'}]}
        with tempfile.TemporaryDirectory() as folder:
            for pages, reason, count in [(5, '동일 URL 집합 반복', 2), (1, '설정한 페이지 한도 도달', 1)]:
                run = collect_api('example.test', ['x'], ['google'], folder,
                                  {'SERPAPI_API_KEY': 'fake'}, pages=pages, fetch=fetch, progress=lambda _: None)
                self.assertEqual(len(run['queries']), count)
                self.assertEqual(run['queries'][-1]['end_reason'], reason)

    def test_http_failure_preserves_provider_job_id(self):
        import io
        from unittest.mock import patch
        from urllib.error import HTTPError
        from search_providers import fetch_json
        body = json.dumps({'search_metadata': {'id': 'job1', 'status': 'Error'},
                           'error': 'secret'}).encode()
        failure = HTTPError('https://serpapi.com/search.json', 503, 'failure', {}, io.BytesIO(body))
        statuses = []
        with patch('search_providers.urllib.request.urlopen', side_effect=failure):
            with self.assertRaises(APIError) as caught:
                wait_search({}, 'secret', fetch_json, on_status=lambda **s: statuses.append(s))
        self.assertEqual(statuses[0]['search_id'], 'job1')
        self.assertEqual(statuses[0]['provider_status'], 'Error')
        self.assertNotIn('secret', str(caught.exception))

    def test_async_submission_and_archive_only_polling(self):
        calls, statuses = [], []
        def fetch(url, headers):
            calls.append(url)
            return {'search_metadata': {'id': 'job1', 'status': 'Processing' if len(calls) < 3 else 'Success'}}
        result = wait_search({'api_key': 'secret'}, 'secret', fetch,
                             on_status=lambda **s: statuses.append(s), poll_interval=0)
        self.assertEqual(result['search_metadata']['status'], 'Success')
        self.assertEqual(parse_qs(urlsplit(calls[0]).query)['async'], ['true'])
        self.assertNotIn('no_cache', calls[0])
        self.assertTrue(all(urlsplit(u).path == '/searches/job1.json' for u in calls[1:]))
        self.assertEqual(statuses[0]['search_id'], 'job1')

    def test_async_pending_cancelled_error_and_network(self):
        pending = lambda *_: {'search_metadata': {'id': 'job1', 'status': 'Processing'}}
        with self.assertRaises(SearchPending) as caught:
            wait_search({}, 'secret', pending, wait_seconds=0)
        self.assertEqual(caught.exception.state, 'pending')
        with self.assertRaises(SearchPending) as caught:
            wait_search({}, 'secret', pending, should_stop=lambda: True)
        self.assertEqual(caught.exception.state, 'cancelled')
        with self.assertRaises(APIError):
            wait_search({}, 'secret', lambda *_: {'search_metadata': {'id': 'job1', 'status': 'Error'}})
        calls = []
        def disconnected(url, headers):
            calls.append(url)
            if len(calls) > 1:
                raise APIError('network')
            return pending()
        with self.assertRaises(SearchPending):
            wait_search({}, 'secret', disconnected, poll_interval=0)
        self.assertEqual(len(calls), 2)

    def test_saved_job_resume_does_not_submit(self):
        from unittest.mock import patch
        real_wait = wait_search
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            def fetch(url, headers):
                calls.append(url)
                if len(calls) == 1:
                    return {'search_metadata': {'id': 'job1', 'status': 'Processing'}}
                saved = json.loads((Path(folder) / 'results.json').read_text(encoding='utf-8'))
                self.assertEqual(saved['queries'][0]['search_id'], 'job1')
                if len(calls) == 2:
                    raise APIError('temporary failure')
                return {'search_metadata': {'id': 'job1', 'status': 'Success'},
                        'organic_results': [{'link': 'https://example.test/a?x=1&x=2'}]}
            with patch('search_providers.wait_search', side_effect=lambda *a, **kw: real_wait(*a, **kw, poll_interval=0)):
                run = collect_api('example.test', ['x'], ['google'], folder,
                                  {'SERPAPI_API_KEY': 'secret'}, fetch=fetch, progress=lambda _: None)
                self.assertEqual(run['queries'][0]['state'], 'pending')
                resume_searches(run, folder, {'SERPAPI_API_KEY': 'secret'}, fetch=fetch, progress=lambda _: None)
            self.assertEqual(run['queries'][0]['state'], 'collected')
            self.assertEqual(len(run['results']), 1)
            self.assertEqual(sum(urlsplit(u).path == '/search.json' for u in calls), 1)
            self.assertNotIn('secret', (Path(folder) / 'results.json').read_text(encoding='utf-8'))

    def test_transport_errors_are_distinct_and_do_not_expose_key(self):
        from unittest.mock import patch
        from urllib.error import URLError
        from search_providers import fetch_json
        for error, expected in ((TimeoutError('secret'), '시간 초과'),
                                (URLError('secret'), '네트워크 연결 실패'),
                                (ValueError('secret'), '응답 형식 오류')):
            with patch('search_providers.urllib.request.urlopen', side_effect=error):
                with self.assertRaises(APIError) as caught:
                    fetch_json('https://serpapi.com/search.json?api_key=secret', {})
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn('secret', str(caught.exception))

    def test_exact_url_and_multiple_sources(self):
        run = {"results": [], "limit_reached": False}
        urls = ["https://example.test/post?a=1&a=2", "https://example.test/post?a=2&a=1",
                "https://example.test/post?a=%ED%85%8C", "http://example.test/post?a=1&a=2"]
        hits = [{"href": u, "title": "ordinary", "snippet": ""} for u in urls]
        hits.append({"href": "https://example.test.evil.test/post", "title": "카지노"})
        self.assertEqual(merge_hits(run, hits, query(), "example.test", False), 4)
        q = dict(query(), term="다른단어", query="site:example.test 다른단어")
        merge_hits(run, hits[:1], q, "example.test", False)
        self.assertEqual([r["url"] for r in run["results"]], urls)
        self.assertEqual(len(run["results"][0]["sources"]), 2)

    def test_domain_and_dorks(self):
        self.assertEqual(query_plan('google', 'www.gimhae.go.kr', ['먹튀검증', '가입머니']),
                         [('먹튀검증', 'site:www.gimhae.go.kr 먹튀검증'),
                          ('가입머니', 'site:www.gimhae.go.kr 가입머니')])
        # 네이버 검색은 제거했다. 예전 설정 파일에 남은 항목이 있어도 지원하지 않는 엔진으로 거절한다
        with self.assertRaises(ValueError):
            query_plan('naver', 'example.test', ['x'])
        with self.assertRaises(ValueError):
            search_url('naver', 'x')
        self.assertEqual(target_host("https://www.Example.test/a"), "www.example.test")
        self.assertTrue(in_scope("https://bbs.example.test/a", "example.test", True))
        self.assertFalse(in_scope("javascript:alert(1)", "example.test", True))
        self.assertFalse(in_scope("https://u:p@example.test/a", "example.test"))
        plan = query_plan("google", "example.test", ["가입 코드"],
                          {"google": ["site:{domain} intitle:{term}"]})
        self.assertEqual(plan, [("가입 코드", "site:example.test intitle:가입 코드")])
        with self.assertRaises(ValueError):
            query_plan("google", "example.test", ["x"], {"google": ["{term}"]})

    def test_api_contract_and_secrets(self):
        calls = []
        def fetch(url, headers):
            calls.append((parse_qs(urlsplit(url).query), headers))
            return {"search_metadata": {"status": "Success", "id": "test-id"},
                    "search_parameters": {"api_key": "PRIVATE"},
                    "organic_results": [{"link": "https://example.test/a", "title": "<b>제목</b>", "snippet": "요약"}],
                    "serpapi_pagination": {"next": "https://serpapi.com/private?api_key=PRIVATE"}}
        hits, more, evidence = api_page("google", "site:example.test 카지노", 2, {"SERPAPI_API_KEY": "PRIVATE"}, fetch)
        self.assertEqual(calls[0][0]["engine"], ["google"])
        self.assertEqual(calls[0][0]["start"], ["10"])
        self.assertEqual(calls[0][0]["q"], ["site:example.test 카지노"])
        self.assertTrue(more)
        self.assertEqual(hits[0]["title"], "제목")
        self.assertNotIn("PRIVATE", json.dumps(evidence))
        with self.assertRaises(APIError):
            api_page("google", "x", 1, {})
        with self.assertRaises(APIError):
            api_page("google", "x", 1, {"SERPAPI_API_KEY": "PRIVATE"},
                     lambda *_: {"search_metadata": {"status": "Success"}, "changed_results": []})
        with self.assertRaises(ValueError):
            api_page("naver", "x", 1, {"SERPAPI_API_KEY": "PRIVATE"}, fetch)

    def test_pipeline_keeps_engine_evidence_and_all_sources(self):
        from unittest.mock import patch
        from search_assist import pipeline
        def mocked(host, terms, engines, folder, keys, **kwargs):
            def fetch(url, headers):
                return {"search_metadata": {"status": "Success", "id": engines[0]},
                        "organic_results": [{"link": "https://example.test/a?q=1&q=2", "title": "카지노"}]}
            return collect_api(host, terms, engines, folder, {"SERPAPI_API_KEY": "fake"}, fetch=fetch, **kwargs)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dorks = root / "dorks.json"
            dorks.write_text(json.dumps({"google": ["site:{domain} {term}"]}), encoding="utf-8")
            with patch("search_assist.collect_api", side_effect=mocked):
                run, saved = pipeline("example.test", ["카지노", "슬롯"], ["google"], 1, "api", root / "missing.env",
                                      dorks, root / "runs", inspect=False, progress=lambda _: None)
            self.assertEqual(len(run["results"]), 1)
            self.assertEqual(len(run["results"][0]["sources"]), 2)
            for source in run["results"][0]["sources"]:
                self.assertTrue((saved / source["evidence"]["api"]).is_file())
            for q in run["queries"]:
                self.assertTrue((saved / q["evidence"]["api"]).is_file())

    def test_api_pagination_outside_domain_and_errors(self):
        calls = []
        def fetch(url, headers):
            p = parse_qs(urlsplit(url).query)
            calls.append(p)
            n = int(p.get("start", [0])[0])
            return {"search_metadata": {"status": "Success"},
                    "organic_results": [{"link": "https://other.test/a" if n == 0 else "https://example.test/a"}],
                    "serpapi_pagination": {"next": "not-followed"} if n == 0 else {}}
        with tempfile.TemporaryDirectory() as folder:
            run = collect_api("example.test", ["카지노"], ["google"], folder,
                              {"SERPAPI_API_KEY": "SECRET"}, pages=2, fetch=fetch, progress=lambda _: None)
            self.assertEqual(len(run["results"]), 1)
            self.assertEqual(len(calls), 2)
            self.assertEqual(run["queries"][0]["state"], "no_target_results")
            error_run = collect_api("example.test", ["카지노"], ["google"], folder, {}, progress=lambda _: None)
            self.assertEqual(error_run["queries"][0]["state"], "error")
            with self.assertRaises(ValueError):
                collect_api("example.test", ["카지노"], ["naver"], folder, {}, progress=lambda _: None)

    def test_export_and_blocked(self):
        run = {"target": "example.test", "results": [], "queries": []}
        q = query()
        q["state"] = "collected"
        run["queries"].append(q)
        merge_hits(run, [{"href": "https://example.test/a", "title": "=1+1", "snippet": "<script>alert(1)</script>"}], q, "example.test", False)
        with tempfile.TemporaryDirectory() as folder:
            save(run, folder)
            text = (Path(folder) / "report.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert", text)
            with (Path(folder) / "review.csv").open(encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.reader(fp))
            self.assertEqual(rows[1][10], "'=1+1")
        self.assertEqual(search_state("https://www.google.com/sorry/", "", 200), "blocked")
        self.assertEqual(search_state("https://www.google.com/search", "검색결과가 없습니다", 200), "no_results")
        self.assertEqual(search_state("https://www.google.com/search", "새 레이아웃", 200), "needs_review")


class HealthTests(unittest.TestCase):
    """검색 API 상태 확인. 모의 응답만 쓰고 키는 결과에 남기지 않는다."""

    def test_states_and_key_never_in_result(self):
        from search_providers import check_health, load_keys
        seen = []
        def probe(response):
            def call(url, headers):
                self.assertTrue(url.startswith('https://serpapi.com/account.json?'))
                seen.append(url)
                return response
            return call
        keys = {'SERPAPI_API_KEY': 'SECRET-SERP', 'KAKAO_REST_API_KEY': 'SECRET-IGNORED'}
        for response, state in [((200, {'total_searches_left': 42}), 'ok'),
                                ((401, {}), 'auth_failed'), ((429, None), 'quota_exhausted'),
                                ((200, {'total_searches_left': 0}), 'quota_exhausted'),
                                ((0, None), 'network_error')]:
            result = check_health(keys, probe(response))
            self.assertEqual(len(result['providers']), 1)
            self.assertEqual(result['providers'][0]['state'], state)
            self.assertNotIn('SECRET', json.dumps(result))
        seen.clear()
        result = check_health({'KAKAO_REST_API_KEY': 'ignored'}, probe((200, {})))
        self.assertEqual(result['overall'], 'not_configured')
        self.assertEqual(seen, [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'search.env'
            path.write_text('KAKAO_REST_API_KEY=ignored', encoding='utf-8')
            self.assertNotIn('KAKAO_REST_API_KEY', load_keys(path))
        for call in (lambda: api_page('daum', 'x', 1, keys, lambda *_: self.fail('network call')),
                     lambda: query_plan('daum', 'example.test', ['x'])):
            with self.assertRaises(ValueError):
                call()

    def test_job_caches_until_refresh(self):
        from ui.search_job import SearchJob
        with tempfile.TemporaryDirectory() as tmp:
            job = SearchJob(tmp)
            job.config = Path(tmp)
            calls = []

            def probe(url, headers):
                calls.append(url)
                return 200, {"total_searches_left": 3}
            (Path(tmp) / "search.env").write_text("SERPAPI_API_KEY=x", encoding="utf-8")
            first = job.health(probe=probe)
            self.assertFalse(first["cached"])
            self.assertTrue(job.health(probe=probe)["cached"])
            self.assertEqual(len(calls), 1)
            job.health(force=True, probe=probe)
            self.assertEqual(len(calls), 2)


class LocalBrowserTests(unittest.TestCase):
    def test_recheck_deleted_blocked_reflected_and_hidden(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                path = urlsplit(self.path).path
                status = {"/gone": 404, "/removed": 410, "/blocked": 403, "/error": 500}.get(path, 200)
                value = parse_qs(urlsplit(self.path).query).get("q", [""])[0]
                body = "정상 기관 안내"
                if path == "/reflected":
                    body = value
                elif path == "/soft":
                    body = "삭제된 게시물입니다."
                elif path == "/hidden":
                    body = '<p style="color:transparent">카지노 가입코드 WIN77 텔레그램 @test_bet</p>'
                data = ('<!doctype html><meta charset="utf-8"><title>게시글</title><body>' + body + '</body>').encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        suffix = "?" + urlencode({"q": "카지노 가입코드 WIN77"})
        paths = ["/gone", "/removed", "/blocked", "/error", "/soft", "/normal", "/hidden", "/reflected"+suffix,
                 "/normal"+suffix, "/delete"]
        run = {"target": "127.0.0.1", "queries": [], "results": [dict(url=base+p, status="미검사", sources=[dict(query(), title="카지노", snippet="")]) for p in paths]}
        try:
            with tempfile.TemporaryDirectory() as folder:
                recheck(run, folder, progress=lambda _: None, polite=False)
                states = [r["status"] for r in run["results"]]
                self.assertEqual(states, ["삭제 응답", "삭제 응답", "확인 불가", "확인 불가", "삭제 안내 의심",
                                          "현재 광고 미탐지", "광고 탐지", "파라미터 반영", "파라미터 문구만 존재", "확인 불가"])
                self.assertTrue(run["results"][6]["findings"])
                self.assertNotIn("/delete", received)
                self.assertEqual(run["results"][7]["url"], base + paths[7])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_search_dom_extraction(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            try:
                page = browser.new_page()
                page.set_content('<div class="g"><a href="https://example.test/a?q=x"><h3>카지노</h3></a><p>검색 요약</p></div>')
                hits = page.evaluate(EXTRACT_JS)
                self.assertEqual(hits[0]["href"], "https://example.test/a?q=x")
                self.assertIn("검색 요약", hits[0]["snippet"])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
