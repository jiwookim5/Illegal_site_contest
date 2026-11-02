"""Local contract, timer and fair-crawl regression tests; no external requests."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from playwright.sync_api import sync_playwright
from findings import walk_frame
from frontier import FairQueue
from run_archive import RunArchive, RunClock, verify
from session import BrowserSession, LAZY_HOOK, WAIT_PAINT, DELAY_LEFT
from urls import page_key, clean_url

class ExecutionTests(unittest.TestCase):
    def test_all_query_values_and_case_are_preserved(self):
        base = 'https://example.org/Board/View'
        for tail in ('?page=2', '?x=', '?utm_source=page2', ';jsessionid=other'):
            self.assertNotEqual(page_key(base), page_key(base + tail))
            self.assertEqual(clean_url(base + tail), base + tail)
        self.assertNotEqual(page_key(base), page_key(base.lower()))
        from score import norm_url
        for tail in ('?x=', '?utm_source=page2', ';jsessionid=other'):
            self.assertNotEqual(norm_url(base, ''), norm_url(base + tail, ''))
        self.assertEqual(page_key(base+'/?b=2&a=1#x'), page_key(base+'?a=1&b=2'))

    def test_continuous_board_work_cannot_starve_normal_pages(self):
        q = FairQueue(['http://local/home', 'http://local/board/view?id=1'])
        seen = []
        for n in range(12):
            seen.append(q.popleft())
            q.append('http://local/board/view?id='+str(n+2))
        self.assertIn('http://local/home', seen[:4])
        self.assertIn('board', seen[0])

    def test_crawler_visits_distinct_query_values_and_normal_link_before_cap(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from scan import scan
        class Local(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                if self.path == '/':
                    body='<a href="/normal">일반 안내</a>'+''.join(
                        f'<a href="/board/view?utm_source={n}">게시글</a>' for n in range(1,9))
                else:
                    body='<p style="display:none">카지노 가입 보너스</p>'
                data=('<html><body>'+body+'</body></html>').encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Local)
        Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            res=scan(base+'/',max_pages=5,respect_robots=False,primary_only=True)
            self.assertIn(base+'/normal',res['pages'])
            self.assertEqual(len(res['findings']),4)
            self.assertEqual(sum('utm_source=' in r['url'] for r in res['findings']),3)
            self.assertGreater(res['coverage']['left_count'],0)
            self.assertEqual(res['coverage']['failed_count'],0)
        finally:server.shutdown();server.server_close()

    def test_total_time_includes_preparation_and_saving_and_preserves_engine(self):
        with tempfile.TemporaryDirectory() as out:
            clock = RunClock()
            time.sleep(.12)
            archive = RunArchive(out, 'http://localhost/', {}, clock=clock)
            now = datetime.now(timezone.utc)
            res = dict(started=now, finished=now, elapsed=.01, pages=[], findings=[], coverage={})
            seal = archive._seal
            def slow_seal(*args):
                if not args: time.sleep(.15)
                return seal(*args)
            with patch.object(archive, '_seal', side_effect=slow_seal):
                archive.finish(res)
            observed = time.monotonic()-clock.begin
            self.assertGreaterEqual(res['elapsed'], .27)
            self.assertEqual(res['engine_elapsed'], .01)
            self.assertLess(observed-res['elapsed'], 1)
            self.assertEqual(verify(archive.path), [])

    def test_gui_clock_starts_before_previous_result_loading(self):
        from ui.server import Session
        with tempfile.TemporaryDirectory() as out:
            session=Session(out)
            now=datetime.now(timezone.utc)
            res=dict(started=now,finished=now,elapsed=.01,pages=['http://localhost/'],findings=[],coverage={})
            def load_previous(*args):
                time.sleep(.2)
                return None
            with patch.object(session,'_read_result',side_effect=load_previous), patch('ui.server.run_scan',return_value=res):
                self.assertTrue(session.start('http://localhost/',1))
                deadline=time.monotonic()+10
                while session.running and time.monotonic()<deadline:time.sleep(.01)
                self.assertFalse(session.running)
                self.assertIsNone(session.error)
                self.assertGreaterEqual(session.result['elapsed'],.2)
                self.assertEqual(session.result['engine_elapsed'],.01)

    def test_invalid_submission_is_never_published_as_success(self):
        with tempfile.TemporaryDirectory() as out:
            archive = RunArchive(out, 'http://localhost/', {})
            now = datetime.now(timezone.utc)
            res = dict(started=now, finished=now, elapsed=1, pages=[], coverage={}, findings=[
                dict(url='http://localhost/', location='', evidence_text='카지노 가입 보너스', technique='OFFSCREEN')])
            with self.assertRaisesRegex(ValueError, '결과 파일 형식 검증 실패'):
                archive.finish(res)
            self.assertFalse((Path(out)/'result.json').exists())

    def test_cancelled_paint_timer_is_removed_but_real_timers_remain(self):
        with sync_playwright() as p:
            s = BrowserSession(p)
            try:
                s.page.goto('about:blank')
                s.page.set_content('<html><body></body></html>')
                s.page.evaluate('window.__hwonhiTrack = true')
                s.page.evaluate(WAIT_PAINT)
                self.assertLess(s.page.evaluate(DELAY_LEFT), 100)
                s.page.evaluate("""() => {
                    const id=setInterval(()=>{},1000); clearTimeout(id);
                    setTimeout(()=>{document.body.innerHTML='<p id="ad" style="display:none">카지노 가입 보너스</p>'},350);
                }""")
                self.assertGreater(s.page.evaluate(DELAY_LEFT), 100)
                s.react()
                rows=[]; walk_frame(s.page.main_frame,'','http://local/',rows,set(),primary_only=True)
                self.assertEqual([r['technique'] for r in rows], ['OFFSCREEN'])
                target=s.page.locator(rows[0]['location'])
                self.assertEqual(target.count(), 1)
                self.assertEqual(target.get_attribute('id'), 'ad')
            finally: s.close()

    def test_interval_chains_and_split_text_retain_main_findings(self):
        with sync_playwright() as p:
            s=BrowserSession(p)
            try:
                s.page.goto('about:blank')
                s.page.evaluate("""() => {
                    window.__hwonhiTrack=true;
                    let n=0; const id=setInterval(()=>{
                        if (++n===3) { clearInterval(id); setTimeout(()=>{
                            document.body.innerHTML='<p id="ad"><span>ㅋㅏ</span><span>ㅈㅣ</span><span>ㄴㅗ 가입 보너스</span></p>';
                        },100); }
                    },100);
                }""")
                s.react()
                rows=[]; walk_frame(s.page.main_frame,'','http://local/',rows,set(),primary_only=True)
                self.assertTrue(any(r['technique']=='JAMO' for r in rows),rows)
                self.assertTrue(all(r['technique'] in {'JAMO','HOMOGLYPH','TRANSPARENT','OFFSCREEN'} for r in rows))
            finally: s.close()

if __name__=='__main__': unittest.main(verbosity=2)
