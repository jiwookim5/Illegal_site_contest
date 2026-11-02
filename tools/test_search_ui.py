"""검색 UI 통합 검증: localhost와 모의 API만 사용한다."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from uuid import uuid4
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'detector'))
from playwright.sync_api import sync_playwright
from ui.server import Session, Handler
from search_discovery import new_folder, save
from search_providers import collect_api


class SearchUITests(unittest.TestCase):
    def test_existing_screen_search_stop_resume_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'search.env').write_text('SERPAPI_API_KEY=fake-test-key', encoding='utf-8')
            session = Session(tmp)
            session.search.config = root
            class H(Handler):
                def log_message(self, *args): pass
            H.session = session
            server = ThreadingHTTPServer(('127.0.0.1',0), H)
            worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
            calls = []
            def pipeline(**args):
                calls.append(args)
                folder = new_folder(args['output'], args['site'])
                def fetch(*_):
                    return {'search_metadata':{'status':'Success','id':'test-id'},
                            'organic_results':[{'link':'https://example.test/post?q=1&q=2','title':'<script>bad</script>',
                                              'snippet':'카지노 가입 보너스 텔레그램 @casino777'}]}
                run = collect_api(args['site'],args['terms'],args['engines'],folder,
                                  {'SERPAPI_API_KEY':'fake-test-key'},pages=1,fetch=fetch,progress=args['progress'])
                if len(calls)==2:
                    args['progress']('중지 시험 대기')
                    while not args['should_stop']():
                        threading.Event().wait(.05)
                    run['queries'][0].update(state='pending',search_id='test-id')
                    save(run,folder)
                return run,folder
            def resume(run, folder, *args):
                run['queries'][0]['state']='collected'
                save(run,folder)
            # 상태 확인도 외부 API 대신 모의 응답만 쓴다
            health_calls = []
            def health(keys, *args):
                health_calls.append(keys)
                return {'overall':'ok','providers':[
                    {'id':'serpapi','name':'구글 (SerpApi)','engines':['google'],'state':'ok','message':'정상 · 남은 검색 99회','searches_left':99}]}
            # 추가 탐색은 결과 화면에서 들어간다. 광고 낱말을 미리 채우는지 보려고 결과 하나를 넣어 둔다
            from datetime import datetime
            now = datetime.now().astimezone()
            session.entry_url = 'https://example.test/board'
            session.result = dict(started=now, finished=now, elapsed=1, pages=['https://example.test/board'], coverage={},
                                  entry_url='https://example.test/board', evidence={}, findings=[dict(
                                      url='https://example.test/board', location='div', technique='OFFSCREEN',
                                      evidence_text='꽁머니 지급', normalized='꽁머니지급', reason='화면 밖', keywords=['꽁머니'],
                                      judgement={'level':'high','label':'확실','reasons':['불법 은어 키워드: 꽁머니'],'terms':['꽁머니']})])
            try:
                with patch('ui.search_job.pipeline',side_effect=pipeline), patch('ui.search_job.resume_searches',side_effect=resume), \
                        patch('ui.search_job.check_health',side_effect=health), sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='msedge',headless=True)
                    page=browser.new_page(viewport={'width':1200,'height':1000})
                    errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
                    base=f'http://127.0.0.1:{server.server_port}'
                    page.goto(base)
                    # 새 탭은 시작 화면부터 보인다. 결과를 연 것과 같게 불러온다
                    page.evaluate("load()")
                    page.locator('#body').wait_for(state='visible')
                    self.assertTrue(page.locator('#search-assist').is_hidden())
                    page.wait_for_function("document.getElementById('apihealth').dataset.state === 'ok'")
                    self.assertIn('정상', page.locator('#apihealthtext').inner_text())
                    page.locator('#apihealth').click()
                    self.assertIn('남은 검색 99회', page.locator('#healthlist').inner_text())
                    page.locator('#healthdlg .dlg-close').click()
                    self.assertEqual(page.locator('#search-daum').count(), 0)
                    self.assertEqual(page.locator('#search-naver').count(), 0)   # 네이버 검색은 제거했다
                    self.assertEqual(page.locator('#rows .lv.high').inner_text(), '확실')
                    page.locator('#search-open').click()
                    page.locator('#searchstage').wait_for(state='visible')
                    self.assertEqual(page.locator('#search-site').input_value(), 'example.test')
                    # 광고단어는 유형별 고정 단어를 고르게 하고, 직접 입력은 접힌 고급 칸에 둔다
                    page.wait_for_function("document.querySelectorAll('#search-grouplist input').length === 7")
                    self.assertEqual(page.locator('#search-grouplist input:checked').count(), 7)
                    self.assertIn('먹튀', page.locator('#search-grouplist').inner_text())
                    self.assertFalse(page.locator('#search-foundrow').is_hidden())
                    self.assertIn('꽁머니', page.locator('#search-foundwords').inner_text())
                    self.assertEqual(page.locator('#search-terms').input_value(), '')
                    self.assertFalse(page.locator('#search-advanced').evaluate('d => d.open'))
                    self.assertIn('검색 단어 25개', page.locator('#search-estimate').inner_text())
                    self.assertIn('최대 50회', page.locator('#search-estimate').inner_text())
                    # 유형을 모두 끄면(찾은 단어도 끄면) 시작할 수 없다
                    page.locator('#search-grouplist input').evaluate_all("els => els.forEach(e => e.click())")
                    page.locator('#search-found').uncheck()
                    self.assertTrue(page.locator('#search-go').is_disabled())
                    page.locator('#search-grouplist input').evaluate_all("els => els.forEach(e => e.click())")
                    page.locator('#search-found').check()
                    # 직접 입력은 고정 단어에 더해진다 (중복은 한 번만 센다)
                    page.locator('#search-advanced summary').click()
                    page.locator('#search-terms').fill('가입머니\n먹튀')
                    self.assertIn('검색 단어 26개', page.locator('#search-estimate').inner_text())
                    page.locator('#search-terms').fill('')
                    page.locator('#search-site').fill('')
                    page.locator('#search-copy').click()
                    self.assertEqual(page.locator('#search-site').input_value(), 'example.test')
                    self.assertFalse(page.locator('#search-inspect').is_checked())
                    evidence = Path(__file__).resolve().parents[1] / '_regress' / ('search-ui-' + uuid4().hex[:8])
                    evidence.mkdir(parents=True)
                    page.screenshot(path=str(evidence / 'search-panel.png'), full_page=True)
                    print('Search UI evidence:', evidence)
                    page.locator('#search-go').click()
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('저장 URL 1건')")
                    self.assertEqual(calls[0]['site'],'example.test')
                    self.assertEqual(len(calls[0]['terms']), 25)
                    self.assertTrue({'먹튀', '꽁머니', '조건만남', 'slotgacor'} <= set(calls[0]['terms']))
                    self.assertFalse(calls[0]['inspect'])
                    # 검색이 끝나면 제출 파일에 반영한 건수·유형·위치를 화면에 보여 준다
                    page.wait_for_function("!document.getElementById('search-submission').hidden")
                    # 모의 API는 25개 질의에 같은 결과를 돌려주므로 검색 위치별로 25건이 된다
                    self.assertIn('광고 25건을 반영', page.locator('#search-submission-head').inner_text())
                    self.assertIn('검색 제목·요약 노출 25건', page.locator('#search-submission-types').inner_text())
                    self.assertIn('result_extra.json', page.locator('#search-submission-file').inner_text())
                    self.assertTrue((root/'result_extra.json').exists())
                    with page.expect_popup() as popup: page.locator('#search-report').click()
                    report=popup.value;report.wait_for_load_state()
                    self.assertIn('example.test/post',report.locator('body').inner_text())
                    self.assertEqual(page.request.get(base+'/api/search/files/%2e%2e/search.env').status,404)
                    self.assertNotIn('fake-test-key',page.request.get(base+'/api/search/status').text())
                    page.locator('#search-go').click()
                    page.wait_for_function("document.getElementById('search-log').textContent.includes('중지 시험 대기')")
                    self.assertEqual(page.request.post(base+'/api/scan',data={'url':'http://127.0.0.1/'}).status,409)
                    for action in ('open', 'delete'):
                        self.assertEqual(page.request.post(base+'/api/runs/'+action, data={'run_id':'invalid'}).status,409)
                    page.locator('#search-stop').click()
                    page.wait_for_function("!document.getElementById('search-resume').disabled")
                    page.locator('#search-resume').click()
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('미완료 페이지 0건')")
                    self.assertEqual(session.search.run['queries'][0]['state'],'collected')
                    self.assertEqual(page.request.post(base+'/api/search/start',data={'site':'example.test','terms':'','engines':['google']}).status,400)
                    page.locator('#search-back').click()
                    page.locator('#body').wait_for(state='visible')
                    # 상태 확인은 5분 동안 저장해 둔 결과를 쓰고, 다시 확인을 누를 때만 새로 묻는다
                    self.assertEqual(len(health_calls), 1)
                    self.assertTrue(page.request.get(base+'/api/search/health').json()['cached'])
                    self.assertNotIn('fake-test-key', page.request.get(base+'/api/search/health?refresh=1').text())
                    self.assertEqual(len(health_calls), 2)
                    # 키가 없으면 검색 화면에서 시작할 수 없고, 설정 창으로 바로 이어지는 버튼이 나온다
                    def no_key(keys, *args):
                        return {'overall':'not_configured','providers':[
                            {'id':'serpapi','name':'구글 (SerpApi)','engines':['google'],'state':'not_configured','message':'키 없음'}]}
                    session.search.health_cache = None      # 저장된 정상 결과를 비워 새로 묻게 한다
                    with patch('ui.search_job.check_health', side_effect=no_key):
                        page.reload()
                        page.evaluate("load()")
                        page.locator('#body').wait_for(state='visible')
                        page.wait_for_function("document.getElementById('apihealth').dataset.state === 'not_configured'")
                    page.evaluate("document.getElementById('searchstage').hidden = false")
                    self.assertFalse(page.locator('#search-keynote').is_hidden())
                    self.assertTrue(page.locator('#search-go').is_disabled())
                    page.locator('#search-keyopen').click()
                    self.assertTrue(page.locator('#healthdlg').evaluate('d => d.open'))
                    page.locator('#healthdlg .dlg-close').click()
                    self.assertFalse(errors,errors)
                    browser.close()
            finally:
                session.search.stop.set()
                if session.search.thread:session.search.thread.join(5)
                server.shutdown();server.server_close();worker.join()

    def test_progress_error_table_and_scope_with_mock_status(self):
        """백엔드 계약대로 만든 모의 상태를 주입해 진행 막대·단어 표·오류 표·검색 범위를 확인한다."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Session(tmp)
            class H(Handler):
                def log_message(self, *args): pass
            H.session = session
            server = ThreadingHTTPServer(('127.0.0.1', 0), H)
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            terms = ['먹튀', '꽁머니', '조건만남', '슬롯']
            running = {
                'running': True, 'stopping': False, 'error': None, 'logs': ['[1] 먹튀 1페이지'], 'count': 3, 'resumable': False,
                'report': False, 'submission': None,
                'queries': [
                    {'term': '먹튀', 'page': 1, 'state': 'collected', 'error': '', 'end_reason': '정상', 'target_links': ['a', 'b']},
                    {'term': '먹튀', 'page': 2, 'state': 'no_target_results', 'error': '', 'end_reason': '정상 무결과', 'target_links': []},
                    {'term': '꽁머니', 'page': 1, 'state': 'error', 'error': 'boom', 'end_reason': 'API 오류로 해당 질의 종료', 'target_links': []},
                    {'term': '조건만남', 'page': 2, 'state': 'processing', 'error': '', 'end_reason': '처리 중', 'target_links': ['c']},
                ],
                'progress': {'terms': terms, 'words_total': 4, 'words_done': 1, 'queries_done': 3, 'started_at': '2026-10-19T10:00:00+09:00',
                             'elapsed_sec': 245, 'finished': False,
                             'current': {'term': '조건만남', 'page': 2, 'query': 'site:yangyang.go.kr 조건만남', 'state': 'processing'}},
                'errors': [{'term': '꽁머니', 'page': 1, 'state': 'error', 'reason': 'provider_error', 'detail': 'HTTP 500 <b>bad</b>'},
                           {'term': '슬롯', 'page': 3, 'state': 'error', 'reason': 'end_of_results', 'detail': ''}],
                'scope': {'scope': 'domain', 'query_host': 'yangyang.go.kr', 'entry_host': 'www.yangyang.go.kr', 'subdomains': True},
            }
            done = json.loads(json.dumps(running))
            done['running'] = False
            done['queries'][3].update(state='collected', page=1)
            done['progress'].update(words_done=4, queries_done=5, elapsed_sec=570, finished=True, current=None)
            done['progress']['terms'] = terms
            idle = {'running': False, 'stopping': False, 'error': None, 'logs': [], 'count': 0, 'queries': [],
                    'submission': None, 'report': False, 'resumable': False}
            mock = {'status': idle}
            starts = []
            def on_status(route):
                route.fulfill(status=200, content_type='application/json', body=json.dumps(mock['status'], ensure_ascii=False))
            def on_start(route):
                starts.append(route.request.post_data_json)
                route.fulfill(status=200, content_type='application/json', body='{"ok":true}')
            def healthy(keys, *args):
                return {'overall': 'ok', 'providers': [{'id': 'serpapi', 'name': '구글 (SerpApi)', 'engines': ['google'], 'state': 'ok', 'message': '정상'}]}
            try:
                with patch('ui.search_job.check_health', side_effect=healthy), sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 1200, 'height': 1000})
                    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                    page.route('**/api/search/status', on_status)
                    page.route('**/api/search/start', on_start)
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.evaluate("setStage('search')")
                    page.wait_for_function("document.querySelectorAll('#search-grouplist input').length === 7")
                    # 상세 설정은 접혀 있고, 기본 화면에는 시작 단추만 보인다
                    self.assertFalse(page.locator('#search-options').evaluate('d => d.open'))
                    self.assertTrue(page.locator('#search-stop').is_hidden())
                    self.assertTrue(page.locator('#search-resume').is_hidden())
                    page.locator('#search-options summary').click()
                    # 검색 범위: 기본은 등록 도메인 전체이고 하위 도메인 칸은 숨겨져 체크된 채 잠긴다
                    self.assertTrue(page.locator('#search-subsrow').is_hidden())
                    self.assertTrue(page.locator('#search-scope-domain').is_checked())
                    self.assertTrue(page.locator('#search-subs').is_disabled())
                    self.assertTrue(page.locator('#search-subs').is_checked())
                    page.locator('#search-site').fill('www.yangyang.go.kr')
                    self.assertIn('site:yangyang.go.kr', page.locator('#search-scopenote').inner_text())
                    page.locator('#search-site').fill('https://news.example.co.kr/a?b=1')
                    self.assertIn('site:example.co.kr', page.locator('#search-scopenote').inner_text())
                    page.locator('#search-site').fill('a.b.example.com')
                    self.assertIn('site:example.com ', page.locator('#search-scopenote').inner_text())
                    page.locator('#search-site').fill('www.yangyang.go.kr')
                    page.locator('#search-scope-host').check()
                    self.assertTrue(page.locator('#search-subsrow').is_visible())      # 입력한 주소만일 때만 묻는다
                    self.assertFalse(page.locator('#search-subs').is_disabled())
                    self.assertFalse(page.locator('#search-subs').is_checked())
                    self.assertIn('site:www.yangyang.go.kr', page.locator('#search-scopenote').inner_text())
                    page.locator('#search-subs').check()
                    page.wait_for_function("!document.getElementById('search-go').disabled")
                    page.locator('#search-go').click()
                    page.wait_for_timeout(300)
                    self.assertEqual(starts[-1]['scope'], 'host')
                    self.assertTrue(starts[-1]['subdomains'])
                    page.locator('#search-scope-domain').check()
                    self.assertTrue(page.locator('#search-subs').is_disabled() and page.locator('#search-subs').is_checked())
                    page.locator('#search-go').click(); page.wait_for_timeout(300)
                    self.assertEqual(starts[-1]['scope'], 'domain')
                    page.locator('#search-scope-host').check()
                    self.assertTrue(page.locator('#search-subs').is_checked())      # 직전에 고른 값을 기억한다
                    page.locator('#search-scope-domain').check()

                    mock['status'] = running
                    # 진행 중: 막대·문구·현재 질의·단어 표·오류 표
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('1/4 단어')")
                    status = page.locator('#search-status').inner_text()
                    self.assertIn('질의 3건', status)
                    self.assertRegex(status, r'경과 4분 \d\d초')
                    self.assertEqual(page.locator('#search-bar').get_attribute('aria-valuenow'), '25')
                    cur = page.locator('#search-current').inner_text()
                    self.assertIn('지금: site:yangyang.go.kr 조건만남 · 2페이지 · 검색 서비스 처리 중', cur)
                    rows = page.locator('#search-termrows tr')
                    self.assertEqual(rows.count(), 4)
                    texts = [rows.nth(i).inner_text().split() for i in range(4)]
                    self.assertEqual([t[1:3] for t in texts][:1], [['완료', '2건']])
                    self.assertEqual(texts[1][1], '오류')
                    self.assertEqual(texts[2][1:3], ['진행', '중'])
                    self.assertEqual(texts[3][1], '대기')
                    self.assertEqual(page.locator('#search-errors').is_hidden(), False)
                    self.assertEqual(page.locator('#search-errcount').inner_text(), '2')
                    err = page.locator('#search-errrows tr')
                    self.assertIn('제공자 응답 오류', err.nth(0).inner_text())
                    self.assertIn('결과 끝', err.nth(1).inner_text())
                    self.assertFalse(page.locator('#search-errrows details').first.evaluate('d => d.open'))
                    self.assertFalse(page.locator('#search-logbox').evaluate('d => d.open'))
                    self.assertIn('상세 로그 보기', page.locator('#search-logbox summary').inner_text())
                    self.assertIn('[1] 먹튀', page.locator('#search-log').text_content())
                    self.assertIn('최근 검색: site:yangyang.go.kr', page.locator('#search-scopenote').inner_text())
                    self.assertTrue(page.locator('#search-fields').evaluate('f => f.disabled'))
                    # 접어 둔 '자세히'는 1.5초 폴링에도 펼친 채로 남고, HTML 은 글자 그대로 보인다
                    page.locator('#search-errrows summary').first.click()
                    self.assertIn('<b>bad</b>', page.locator('#search-errrows pre').first.inner_text())
                    # 서버 값이 갱신되는 사이에도 경과 시간이 1초 단위로 이어서 올라간다
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('경과 4분 06초')", timeout=5000)
                    self.assertTrue(page.locator('#search-errrows details').first.evaluate('d => d.open'))
                    # 좁은 화면에서도 가로로 넘치지 않는다
                    page.set_viewport_size({'width': 375, 'height': 2600})
                    over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    self.assertLessEqual(over, 0)
                    self.assertLessEqual(page.evaluate("document.getElementById('searchstage').scrollWidth - document.getElementById('searchstage').clientWidth"), 0)
                    evidence = Path(__file__).resolve().parents[1] / '_regress' / ('search-progress-' + uuid4().hex[:8])
                    evidence.mkdir(parents=True)
                    page.screenshot(path=str(evidence / 'narrow-running.png'))
                    page.set_viewport_size({'width': 1200, 'height': 2000})
                    page.screenshot(path=str(evidence / 'wide-running.png'))
                    print('Search progress evidence:', evidence)

                    # 끝난 뒤: 완료 문구와 가득 찬 막대, 현재 질의 줄은 사라진다
                    mock['status'] = done
                    page.wait_for_function("document.getElementById('search-status').textContent.includes('완료 · 총 9분 30초')")
                    self.assertIn('저장 URL 3건', page.locator('#search-status').inner_text())
                    self.assertEqual(page.locator('#search-bar').get_attribute('aria-valuenow'), '100')
                    self.assertTrue(page.locator('#search-current').is_hidden())
                    self.assertFalse(page.locator('#search-fields').evaluate('f => f.disabled'))
                    self.assertTrue(page.locator('#search-subs').is_disabled())
                    page.screenshot(path=str(evidence / 'wide-done.png'))

                    # 옛 응답(진행·오류·범위 필드 없음)이 와도 깨지지 않는다
                    mock['status'] = idle
                    page.wait_for_function("document.getElementById('search-status').textContent === '저장 URL 0건 · 오류/미완료 페이지 0건'")
                    self.assertTrue(page.locator('#search-progress').is_hidden())
                    self.assertTrue(page.locator('#search-errors').is_hidden())
                    self.assertFalse(errors, errors)
                    browser.close()
            finally:
                server.shutdown(); server.server_close(); worker.join()

    def test_saved_run_list_open_and_confirmed_delete(self):
        from datetime import datetime, timezone
        from run_archive import result_dir, verify
        with tempfile.TemporaryDirectory() as tmp:
            session = Session(tmp)
            now = datetime.now(timezone.utc)
            result = dict(started=now, finished=now, elapsed=.1, pages=['http://localhost/'],
                          findings=[], coverage={}, evidence={}, snapshots={})
            with patch('ui.server.run_scan', return_value=result):
                session.entry_url = 'http://localhost/first'
                session._run(session.entry_url, 1)
                first = result_dir(tmp, session.result)
                session.entry_url = 'http://localhost/second'
                session._run(session.entry_url, 1)
                second = result_dir(tmp, session.result)
            class H(Handler):
                def log_message(self, *args): pass
            H.session = session
            server = ThreadingHTTPServer(('127.0.0.1', 0), H)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width':1200, 'height':1000})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    base = f'http://127.0.0.1:{server.server_port}'
                    page.goto(base)
                    page.locator('#start').wait_for(state='visible')
                    page.wait_for_function("document.querySelectorAll('#runlist [data-open]').length === 2")
                    page.locator(f'[data-open="{first.name}"]').click()
                    page.locator('#body').wait_for(state='visible')
                    self.assertEqual(session.result['run_id'], first.name)
                    page.locator('#again').click()
                    page.locator(f'[data-del="{second.name}"]').wait_for()
                    page.locator(f'[data-del="{second.name}"]').click()
                    self.assertIn('되돌릴 수 없습니다', page.locator('#askmsg').inner_text())
                    page.locator('#askcancel').click()
                    self.assertTrue(second.exists())
                    page.locator(f'[data-del="{second.name}"]').click()
                    page.locator('#askok').click()
                    page.wait_for_function("document.querySelectorAll('#runlist [data-open]').length === 1")
                    self.assertFalse(second.exists())
                    self.assertTrue(first.exists())
                    self.assertEqual(verify(first), [])
                    self.assertEqual(session.result['run_id'], first.name)
                    self.assertEqual(page.request.get(base+'/api/runs').json()['runs'][0]['run_id'], first.name)
                    self.assertFalse(errors, errors)
                    browser.close()
            finally:
                server.shutdown();server.server_close();worker.join()


if __name__=='__main__':unittest.main(verbosity=2)
