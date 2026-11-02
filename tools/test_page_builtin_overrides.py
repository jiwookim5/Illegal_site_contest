"""브라우저 기본 Map·Object.keys·Date 를 덮어쓴 페이지에서도 추출 결과를 읽는지 확인한다.

2026-10-19 gb.go.kr/gbsafe/main.tc 에서 페이지 라이브러리가 Map 을 바꿔 Playwright 결과가 모두
None 이 되었고, 점검 전체가 '본문 확장 결과를 읽지 못했습니다'로 멈췄다 (browser._install_json_fallback).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector"))

from playwright.sync_api import sync_playwright  # noqa: E402

import browser  # noqa: E402
import js_links as js_mod  # noqa: E402
from session import EXPAND_PROBE  # noqa: E402

OVERRIDE = """<script>
// 오래된 라이브러리가 하던 것처럼 기본 객체를 자기 구현으로 바꾼다
window.Map = function () { this.items = {}; };
Map.prototype.put = function (k, v) { this.items[k] = v; };
Object.keys = function (a) { var r = []; for (var k in a) r.push(k); return r; };
window.Date = function () { return 0; };
</script>"""
PAGE = OVERRIDE + """<p>공지 내용을 확인해 주세요.
<span id="ad" style="position:absolute;left:-9999px">안전놀이터 가입쿠폰 지급 텔레 @abcd1234</span></p>"""


class BuiltinOverrideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = browser.launch_browser(cls.pw)[0]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self, html):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_content(html)
        return page

    def test_wrapper_is_installed(self):
        from playwright._impl._frame import Frame
        self.assertTrue(getattr(Frame.evaluate, "_json_fallback", False),
                        "playwright 내부 구조가 바뀌어 Frame.evaluate 를 감싸지 못함")

    def test_objects_survive_overridden_map(self):
        page = self.page(PAGE)
        self.assertFalse(page.evaluate("() => /native code/.test(String(Map))"))
        self.assertEqual(page.evaluate("({a: [1, 2], b: {c: '가'}})"), {"a": [1, 2], "b": {"c": "가"}})
        self.assertEqual(page.evaluate("(x) => x.items.length", {"items": [1, 2, 3]}), 3)
        self.assertEqual(page.evaluate("async () => [1, 'x']"), [1, "x"])
        self.assertIsNone(page.evaluate("() => undefined"))
        self.assertEqual(page.evaluate("'문자열'"), "문자열")

    def test_expand_probe_and_extraction_read_the_page(self):
        page = self.page(PAGE)
        probe = page.evaluate(EXPAND_PROBE, js_mod.MORE_LIMIT)
        self.assertIsInstance(probe, dict)
        text = page.evaluate("() => [...document.querySelectorAll('span')].map(s => s.textContent)")
        self.assertIn("안전놀이터", text[0])

    def test_element_handle_arguments_keep_original_path(self):
        page = self.page(PAGE)
        handle = page.query_selector("#ad")
        self.assertEqual(page.evaluate("(el) => el.id", handle), "ad")

    def test_normal_pages_return_values_unchanged(self):
        page = self.page("<p>정상</p>")
        self.assertEqual(page.evaluate("() => ({n: 1, s: 'x', l: [true, null]})"), {"n": 1, "s": "x", "l": [True, None]})
        self.assertEqual(page.evaluate("() => 'plain'"), "plain")


class Site:
    """경로별 HTML 을 돌려주는 로컬 시험 서버."""

    def __init__(self, pages):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = pages.get(self.path.split("?")[0])
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = ('<!doctype html><html><head><meta charset="utf-8"></head><body>' + body
                        + "</body></html>").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


AD = '<span style="position:absolute;left:-9999px">안전놀이터 가입쿠폰 지급 텔레 @{}</span>'
SITE = {
    "/": '<a href="/broken">재난안전</a> <a href="/legacy">옛 화면</a> <a href="/after">공지</a>',
    "/broken": "<p>공지</p>" + AD.format("broken01"),
    "/legacy": OVERRIDE + "<p>공지</p>" + AD.format("legacy01"),
    "/after": "<p>공지</p>" + AD.format("after001"),
}


class PageFailureIsolationTest(unittest.TestCase):
    def run_scan(self):
        from unittest.mock import patch
        from scan import scan
        from session import BrowserSession
        expand = BrowserSession.expand

        def failing_expand(ses):
            # 2026-10-19 처럼 페이지 하나에서 엔진 예외가 난다
            if ses.page.url.endswith("/broken"):
                raise RuntimeError("본문 확장 결과를 읽지 못했습니다")
            return expand(ses)

        with Site(SITE) as base, patch.object(BrowserSession, "expand", failing_expand):
            return base, scan(base + "/", max_pages=10, respect_robots=False, primary_only=True)

    def test_one_failing_page_does_not_stop_the_scan(self):
        base, res = self.run_scan()
        found = {f["url"].split(base)[-1] for f in res["findings"]}
        # 실패한 페이지 뒤의 페이지도 끝까지 점검하고, Map 을 덮어쓴 페이지의 광고도 잡는다
        self.assertIn("/after", found, res["findings"])
        self.assertIn("/legacy", found, res["findings"])
        failed = {f["url"].split(base)[-1]: f for f in res["coverage"]["failed"]}
        self.assertIn("/broken", failed)
        self.assertIn("본문 확장 결과", failed["/broken"]["detail"])
        self.assertIsNone(res.get("stopped"))


if __name__ == "__main__":
    unittest.main()
