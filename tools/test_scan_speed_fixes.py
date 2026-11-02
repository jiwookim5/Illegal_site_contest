"""서울시 실사이트 재검증에서 나온 대기·탐색 문제의 회귀 시험.

- 열 때 건 넘기기 배너 타이머를 '더보기'·스크롤마다 다시 기다리지 않는다
- 속성만 바꾸는 반복 타이머는 열 때도 두 번만 기다리고, 조용히 세다가 글을 넣는 타이머는 끝까지 기다린다
- 앞서 시작된 끝나지 않는 요청은 동작 뒤 대기에 넣지 않는다
- logOut.do·signOut.do 는 상태 변경 주소다
- 회원 메뉴가 로그인 화면으로 넘어가면 그 화면을 분석하지 않는다
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from playwright.sync_api import sync_playwright
import js_links as js_mod
from findings import walk_frame
from scan import scan
from session import BrowserSession, DELAY_LEFT, REACT_LEFT, Inflight, wait_reactions
from urls import is_state_change_url

CAROUSEL = """<script>setInterval(function () {
  var s = document.getElementById('slides'); s.className = s.className === 'a' ? 'b' : 'a';
}, 300);</script>"""
SILENT_CLOCK = "<script>var n = 0; setInterval(function () { n++; }, 200);</script>"
LATE_FOURTH = """<script>var n = 0, t = setInterval(function () {
  if (++n === 4) { clearInterval(t); var p = document.createElement('p'); p.id = 'ad';
    p.style.cssText = 'position:absolute;left:-9999px'; p.textContent = '카지노 가입 보너스 텔레그램 @late4';
    document.body.appendChild(p); }
}, 400);</script>"""
PAGES = {
    "/carousel": "<div id='slides' class='a'>공지</div>" + CAROUSEL,
    "/late": "<div>공지 내용</div>" + LATE_FOURTH,
    "/clock": "<button id='more'>더보기</button>" + SILENT_CLOCK + """<script>
      document.getElementById('more').onclick = function () { setTimeout(function () {
        var p = document.createElement('p'); p.id = 'ad'; p.style.display = 'none';
        p.textContent = '카지노 가입 보너스'; document.body.appendChild(p); }, 300); };</script>""",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = PAGES.get(self.path.split("?")[0])
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        data = ('<!doctype html><html><head><meta charset="utf-8"></head><body>' + body + "</body></html>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Server:
    def __init__(self, handler):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class TimerWaitTests(unittest.TestCase):
    def test_decorative_interval_stops_delaying_but_late_insertion_is_kept(self):
        with Server(Handler) as base, sync_playwright() as p:
            s = BrowserSession(p)
            try:
                s.page.goto(base + "/carousel")
                time.sleep(1.0)            # 세 번 넘김: 속성만 바뀌므로 두 번 뒤부터 기다리지 않는다
                self.assertEqual(s.page.evaluate(DELAY_LEFT), 0)
                s.open(base + "/late")     # 조용히 세다가 네 번째(1.6초)에 넣는다
                rows = []
                walk_frame(s.page.main_frame, "", base + "/late", rows, set(), primary_only=True)
                self.assertTrue(rows, "네 번째 반복에 넣은 광고를 놓쳤다")
                target = s.page.locator(rows[0]["location"])
                self.assertEqual(target.get_attribute("id"), "ad")
            finally:
                s.close()

    def test_reaction_wait_ignores_load_timers_but_waits_for_action_timers(self):
        with Server(Handler) as base, sync_playwright() as p:
            s = BrowserSession(p)
            try:
                s.page.goto(base + "/clock")
                s.page.wait_for_load_state("load")
                self.assertGreater(s.page.evaluate(DELAY_LEFT), 0)     # 열 때 건 시계는 계속 남아 있다
                js_mod.track_on(s.page)
                self.assertEqual(s.page.evaluate(REACT_LEFT), 0)       # 동작 뒤 대기에는 넣지 않는다
                s.page.evaluate("document.getElementById('more').click()")
                self.assertGreater(s.page.evaluate(REACT_LEFT), 100)   # 누른 뒤 건 타이머는 기다린다
                start = time.monotonic()
                s.react()
                self.assertLess(time.monotonic() - start, 1.2)
                rows = []
                walk_frame(s.page.main_frame, "", base + "/clock", rows, set(), primary_only=True)
                self.assertTrue(any(r["technique"] == "OFFSCREEN" for r in rows), rows)
            finally:
                s.close()

    def test_requests_started_before_the_action_are_not_awaited(self):
        class Page:
            frames = []
            clock = 0
            def evaluate(self, *a): return 0
            def wait_for_timeout(self, ms): self.clock += ms / 1000
        inflight = Inflight()
        inflight.add("held-since-load")
        inflight.mark()
        page = Page()
        with patch("session.time.monotonic", side_effect=lambda: page.clock):
            wait_reactions(page, inflight, 60)
        self.assertLess(page.clock, 0.1)
        inflight.add("started-by-click")
        with patch("session.time.monotonic", side_effect=lambda: page.clock):
            wait_reactions(page, inflight, 60)
        self.assertGreaterEqual(page.clock, 1.9)


class DeferredWaitTests(unittest.TestCase):
    """열 때 타이머를 기다리지 않고 펼치기·판정과 함께 기다려도, 기다린 뒤의 화면으로 판정한다."""

    def test_reload_between_wait_and_evaluate_is_reanalyzed(self):
        session = BrowserSession.__new__(BrowserSession)
        session.timer_deadline = time.monotonic() + 2
        session.opened_url = 'http://127.0.0.1/self'
        session.page = Mock(url=session.opened_url)
        session.navs = session._navs_at_watch = 1
        session.timeout_ms = 2000
        session._wait_timers = Mock(side_effect=RuntimeError('Execution context was destroyed, most likely because of a navigation'))
        session._wait_ready = Mock()
        session.settle = Mock()
        self.assertEqual(session.finish_timers(), 'navigated')
        session.page.wait_for_load_state.assert_called_once_with('domcontentloaded', timeout=2000)
        session._wait_ready.assert_called_once()

    def run_site(self, pages):
        class Site(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                html = pages.get(self.path)
                if html is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = ('<!doctype html><html><head><meta charset="utf-8"></head><body>' + html + "</body></html>").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        with Server(Site) as base:
            return base, scan(base + "/", max_pages=10, respect_robots=False, primary_only=True)

    def test_silent_fourth_tick_insert_late_hide_and_delayed_redirect(self):
        base, res = self.run_site({
            "/": '<a href="/late">a</a><a href="/hide">b</a><a href="/go">c</a><a href="/self">d</a>',
            "/late": "<div>공지</div>" + LATE_FOURTH,
            # 판정할 때는 보이던 광고를 0.8초 뒤에 숨긴다. 숨긴 뒤의 화면으로 판정해야 한다
            "/hide": ('<p id="ad">카지노 가입코드 WIN77 텔레그램 @hide_late</p><script>setTimeout(function () {'
                      ' document.getElementById("ad").style.cssText = "position:absolute;left:-9999px"; }, 800);</script>'),
            # 0.5초 뒤 같은 누리집의 다른 주소로 넘긴다. 넘어간 주소의 페이지로 판정한다
            "/go": "<p>이동 중</p><script>setTimeout(function () { location.href = '/dest'; }, 500);</script>",
            "/dest": '<p style="color:transparent">카지노 가입코드 WIN77 텔레그램 @dest_ad</p>',
            # 판정하는 사이에 같은 주소를 다시 불러온다. 다시 불러온 화면으로 끝까지 판정해야 한다
            # 처음 화면에는 광고가 없고, 다시 불러온 화면에만 있다
            "/self": ('<p id="slot">공지</p><script>if (!sessionStorage.again) { sessionStorage.again = 1;'
                      ' setTimeout(function () { location.replace(location.href); }, 300); } else {'
                      ' document.getElementById("slot").outerHTML = "<p style=\\"color:transparent\\">'
                      '카지노 가입코드 WIN77 텔레그램 @self_reload</p>"; }</script>'),
        })
        by_url = {}
        for f in res["findings"]:
            by_url.setdefault(f["url"].split(base)[-1], set()).add(f["technique"])
        self.assertIn("OFFSCREEN", by_url.get("/late", set()), res["findings"])
        self.assertIn("OFFSCREEN", by_url.get("/hide", set()), res["findings"])
        self.assertIn("TRANSPARENT", by_url.get("/dest", set()), res["findings"])
        pages = {p.split(base)[-1] for p in res["pages"]}
        self.assertIn("/dest", pages)
        self.assertNotIn("/go", pages)
        self.assertIn("TRANSPARENT", by_url.get("/self", set()), res["findings"])
        self.assertEqual(res["coverage"]["failed_count"], 0, res["coverage"]["failed"])


class ProbeFormRestoreTests(unittest.TestCase):
    def test_earlier_filter_click_does_not_change_later_page_links_and_no_reload(self):
        pages = {"/list": """
          <form id="f" method="get" action="/list"><input type="hidden" name="siteId" value="21">
            <input type="hidden" name="fetchStart" value="1"></form>
          <script>function fn_link_page(n) { var f = document.getElementById('f'); f.fetchStart.value = n; f['sub' + 'mit'](); }</script>
          <span onclick="document.querySelector('[name=siteId]').value='30'" style="cursor:pointer">1개월</span>
          <span onclick="fn_link_page(2)" style="cursor:pointer">2</span>
          <span onclick="fn_link_page(3)" style="cursor:pointer">3</span>"""}

        class Site(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                data = ('<!doctype html><meta charset="utf-8"><body>' + pages["/list"] + "</body>").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        with Server(Site) as base, sync_playwright() as p:
            s = BrowserSession(p)
            try:
                s.open(base + "/list")
                reloads = []
                goto = s.page.goto
                s.page.goto = lambda *a, **k: reloads.append(a) or goto(*a, **k)
                found = js_mod.discover(s.page, s.ctx, s.guard, set())
            finally:
                s.close()
        tails = {u.split(base)[-1] for u in found}
        self.assertIn("/list?siteId=21&fetchStart=2", tails, found)
        self.assertIn("/list?siteId=21&fetchStart=3", tails, found)
        self.assertFalse([u for u in tails if "siteId=30" in u], found)
        self.assertEqual(reloads, [])


class MemberMenuTests(unittest.TestCase):
    def test_camel_case_logout_and_signout_are_state_changes(self):
        for path in ("/member/userlogin/logOut.do", "/signOut.do", "/user/LogOut.do", "/logoutOk.do"):
            with self.subTest(path=path):
                self.assertTrue(is_state_change_url("https://www.example.go.kr" + path))
        for path in ("/member/info/mySeoul.do", "/board/logView.do", "/outlook/list.do"):
            with self.subTest(path=path):
                self.assertFalse(is_state_change_url("https://www.example.go.kr" + path))

    def test_member_menu_redirected_to_login_is_not_analyzed(self):
        received = []
        ad = '<p style="color:transparent">카지노 가입코드 WIN77 텔레그램 @login_ad</p>'

        class Site(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                received.append(self.path)
                if self.path.startswith("/member/info/"):
                    self.send_response(302)
                    self.send_header("Location", "/member/userlogin/loginCheck.do")
                    self.end_headers()
                    return
                pages = {
                    "/": ('<a href="/member/info/mySeoul.do">마이서울</a><a href="/member/info/myQna.do">내 문의</a>'
                          '<a href="/member/userlogin/logOut.do">로그아웃</a><a href="/board/view">게시글</a>'),
                    "/member/userlogin/loginCheck.do": "<form><input type='password'></form>" + ad,
                    "/board/view": ad,
                }
                html = pages.get(self.path)
                if html is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = ('<!doctype html><meta charset="utf-8">' + html).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        with Server(Site) as base:
            res = scan(base + "/", max_pages=10, respect_robots=False)
        self.assertNotIn("/member/userlogin/logOut.do", received)
        self.assertEqual({p.split(base)[-1] for p in res["pages"]}, {"/", "/board/view"})
        self.assertEqual(res["coverage"]["login_redirect_count"], 2)
        self.assertFalse([f for f in res["findings"] if "login" in f["url"].lower()], res["findings"])
        self.assertTrue(any(f["url"].endswith("/board/view") for f in res["findings"]))
        # 회원 폴더의 둘째 주소는 게시글 뒤로 미룬다
        self.assertLess(received.index("/board/view"), received.index("/member/info/myQna.do"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
