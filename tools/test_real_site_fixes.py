"""실제 누리집 점검(2026-10-20)에서 드러난 엔진 문제의 재현 시험."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
import scan as scan_mod
from scan import scan

AD = '<div class="board_view"><p>먹튀검증 꽁머니 첫충 메이저사이트 토토사이트 총정리</p></div>'


def serve(handler_body):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            code, html = handler_body(self.path)
            data = ('<!doctype html><meta charset="utf-8">' + html).encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class RealSiteFixTests(unittest.TestCase):
    def run_site(self, body, **kwargs):
        server, thread = serve(body)
        try:
            return scan(f"http://127.0.0.1:{server.server_port}/post?no=107", max_pages=1,
                        respect_robots=False, **kwargs)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_iframe_pointing_at_own_page_keeps_findings(self):
        # gen.go.kr 배너모음: 메일 전송용 <iframe src=""> 의 주소가 페이지 자신으로 풀려,
        # 'iframe 으로 이미 본 페이지'로 여겨 이 페이지의 검출이 모두 지워졌다
        for frame in ('<iframe name="mailform" src="" style="display:none"></iframe>',
                      '<iframe src="#" style="display:none"></iframe>'):
            with self.subTest(frame=frame):
                res = self.run_site(lambda path: (200, AD + frame))
                self.assertTrue(res["findings"], frame)

    def test_failed_page_is_retried_after_a_gap(self):
        # 잠시 막는 서버: 처음 요청은 실패, 간격을 둔 다시 열기는 성공해야 한다
        calls = []

        def body(path):
            calls.append(time.monotonic())
            return (503, "잠시 후") if len(calls) == 1 else (200, AD)
        old = scan_mod.RETRY_GAP_SEC
        scan_mod.RETRY_GAP_SEC = 2
        try:
            res = self.run_site(body)
        finally:
            scan_mod.RETRY_GAP_SEC = old
        self.assertEqual(len(res["pages"]), 1, res["coverage"]["failed"])
        self.assertGreaterEqual(calls[1] - calls[0], 1.9)
        self.assertTrue(res["findings"])

    def test_retry_comes_before_a_long_queue(self):
        # 광주교육청: 첫 열기에 실패한 글 61쪽이 대기열 맨 뒤에서 기다리다 시간 상한까지 다시 열리지 못했다.
        # 다시 열 때가 되면 남은 대기열보다 먼저 열어야 한다
        calls = []
        links = "".join(f'<a href="/p{i}">{i}</a>' for i in range(40))

        def body(path):
            if path.startswith("/post"):
                calls.append(path)
                return (503, "잠시 후") if len(calls) == 1 else (200, AD)
            if path.startswith("/p"):
                time.sleep(0.15)
                return 200, "<p>공지</p>"
            return 404, ""
        old = scan_mod.RETRY_GAP_SEC
        scan_mod.RETRY_GAP_SEC = 1
        try:
            server, thread = serve(lambda path: (200, '<a href="/post?no=107">글</a>' + links) if path == "/" else body(path))
            try:
                res = scan(f"http://127.0.0.1:{server.server_port}/", max_pages=100, respect_robots=False)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        finally:
            scan_mod.RETRY_GAP_SEC = old
        pages = res["pages"]
        post = next(i for i, u in enumerate(pages) if "/post" in u)
        last_p = max(i for i, u in enumerate(pages) if re.search(r"/p\d+$", u))
        self.assertLess(post, last_p, pages)
        self.assertTrue(res["findings"])

    def test_text_directly_in_body_is_scanned(self):
        # 태그 없이 body 바로 아래 넣은 글은 어느 하위 요소의 글에도 들지 않아 통째로 빠졌다
        disguised = "카ㅈ1노 첫충 40% 가입코드 VIP 텔레 @casino777"
        for html in (f"<body>{disguised}</body>", f"<body><p>공지사항</p>{disguised}<p>문의</p></body>",
                     f'<body style="position:relative;left:-9999px">{disguised}</body>'):
            with self.subTest(html=html[:40]):
                res = self.run_site(lambda path: (200, html))
                self.assertIn(("HOMOGLYPH", "body"), {(f["technique"], f["location"]) for f in res["findings"]})

    def test_evidence_of_same_selector_in_two_iframes_is_kept_apart(self):
        # 사진 이름을 iframe 경로를 뺀 선택자로 만들어, 두 iframe 의 div.ad 사진이 하나로 덮어써졌다
        import tempfile
        frames = {"/f1": '<div class="ad" style="position:absolute;left:-9999px">카지노 첫충 가입코드 텔레 @one1111</div>',
                  "/f2": '<div class="ad" style="position:absolute;left:-9999px">토토사이트 꽁머니 지급 텔레 @two2222</div>'}
        page = '<p>공지</p><iframe src="/f1"></iframe><iframe src="/f2"></iframe>'
        with tempfile.TemporaryDirectory() as out:
            res = self.run_site(lambda path: (200, frames.get(path, page)), evidence_dir=out)
            rows = [f for f in res["findings"] if f["technique"] == "OFFSCREEN"]
            self.assertEqual(len(rows), 2, rows)
            images = [res["evidence"][f["evidence_key"]]["image"] for f in rows]
            self.assertTrue(all(images), images)
            self.assertEqual(len(set(images)), 2, images)

    def test_attachment_that_cannot_be_read_is_recorded(self):
        # 해석하지 못한 첨부를 '광고 문단 없음'과 같게 돌려줘, 못 본 것이 깨끗한 것처럼 보였다
        import attachments
        from findings import classify
        from politeness import Politeness
        kind, hits, _, _ = attachments.inspect(b"%PDF-1.4\n\x00\x01 not a pdf", classify)
        self.assertEqual((kind, hits), ("PDF", None))

        class Resp:
            def __init__(self, status, body):
                self.status, self.ok, self._body, self.headers = status, status < 400, body, {}
            def body(self):
                return self._body

        class Request:
            def get(self, href, **kw):
                return Resp(500, b"") if "down" in href else Resp(200, b"%PDF-1.4\n\x00\x01 not a pdf")
        scanner = attachments.AttachmentScanner(Request(), Politeness(enabled=False), classify)
        rows = scanner.check("http://x/post", [{"href": "http://x/a.pdf", "text": "a.pdf", "selector": "a"},
                                               {"href": "http://x/down.hwp", "text": "b.hwp", "selector": "a"}])
        self.assertEqual(rows, [])
        self.assertEqual([u["href"] for u in scanner.unread], ["http://x/a.pdf", "http://x/down.hwp"])

    def test_recheck_does_not_mark_done_after_login_redirect(self):
        # 로그인 화면으로 넘겨진 글을 '광고가 사라짐'으로 보고 조치완료로 저장했다
        from recheck import recheck

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/post?no=1"):
                    self.send_response(302)
                    self.send_header("Location", "/login.do")
                    self.end_headers()
                    return
                data = ('<!doctype html><meta charset="utf-8">'
                        + ("<form>아이디 비밀번호 로그인</form>" if self.path.startswith("/login") else "<p>정상 글</p>")).encode()
                self.send_response(200)
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
        row = {"technique": "OFFSCREEN", "location": "div.board_view > p", "evidence_text": "먹튀검증 꽁머니 첫충"}
        try:
            out = recheck([dict(row, url=base + "/post?no=1"), dict(row, url=base + "/post?no=2")],
                          politeness={"enabled": False})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(out, {0: "unknown", 1: "gone"})

    def test_alert_dialogs_are_dismissed(self):
        # 로그인 안내 알림창을 띄우는 페이지 (gen.go.kr 은 알림창을 닫다 드라이버가 죽어 정체됐다)
        hidden = '<div style="position:absolute;left:-9999px">' + AD + "</div>"
        res = self.run_site(lambda path: (200, "<script>alert('로그인해 주세요.'); confirm('계속할까요?')</script>"
                                               + hidden + "<script>setTimeout(() => alert('다시'), 50)</script>"))
        self.assertEqual(len(res["pages"]), 1, res["coverage"]["failed"])
        self.assertTrue(res["findings"])

    def test_stalled_page_is_skipped_and_scan_continues(self):
        # 교육부 누리집: 팝업 하나가 응답하지 않아 정체로 점검 전체가 끝났다.
        # 정체한 페이지만 실패로 적고 저장된 지점부터 새 작업으로 이어 가야 한다
        import tempfile
        from unittest.mock import patch
        import scan_worker
        from run_archive import RunArchive
        pages = {"/": '<a href="/hang">팝업</a> <a href="/after">다음</a>',
                 "/hang": "<p>멈춤</p><script>while (true) {}</script>",
                 "/after": '<div style="position:absolute;left:-9999px">' + AD + "</div>"}
        server, thread = serve(lambda path: (200, pages.get(path, "")) if path in pages else (404, ""))
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with tempfile.TemporaryDirectory() as out, \
                    patch.object(scan_worker, "STAGE_LIMIT", 4), patch.object(scan_worker, "CANCEL_GRACE", .5):
                archive = RunArchive(out, base + "/", {})
                res = scan_worker.run_scan(base + "/", archive, respect_robots=False, primary_only=True,
                                           max_pages=10, time_limit=120)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(res.get("stall_skips"), [base + "/hang"])
        self.assertNotEqual(res.get("stopped"), "stalled")
        self.assertIn(base + "/after", res["pages"])
        self.assertTrue(res["findings"])
        stalled = [f for f in res["coverage"]["failed"] if f["reason"] == "stalled"]
        self.assertEqual([f["url"] for f in stalled], [base + "/hang"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
