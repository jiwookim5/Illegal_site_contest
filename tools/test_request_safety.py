"""일반 href 탐색이 상태 변경 링크를 요청하지 않는지 실제 브라우저로 검증한다."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from scan import scan
from urls import is_state_change_url


class RequestSafetyTests(unittest.TestCase):
    def test_action_urls_and_reading_urls(self):
        for path in ("/delete", "/logout", "/boardDelete.do", "/deleteBoard.do", "/DELETE.do",
                     "/%64elete", "/%2564elete", "/board?mode=delete", "/board?action=logout",
                     "/?c=5&bid=notice&p=1&mod=delete&uid=156", "/?m=bbs&bid=notice&a=scrap&uid=99",
                     "/?m=bbs&bid=free&a=singo&uid=3", "/?c=5&bid=notice&mod=write"):
            with self.subTest(path=path):
                self.assertTrue(is_state_change_url("http://localhost" + path))
        for path in ("/board/view", "/comment/list", "/reply/list", "/updates", "/model",
                     "/article?mode=read", "/search?q=delete", "/board?title=logout",
                     "/?m=bbs&bid=notice&uid=178", "/?c=5&bid=notice&p=2", "/?a=list"):
            with self.subTest(path=path):
                self.assertFalse(is_state_change_url("http://localhost" + path))

    def test_crawl_does_not_send_forbidden_gets(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                html = ('<a href="/delete">삭제</a><a href="/logout">로그아웃</a>'
                        '<a href="/board?mode=delete">처리</a><a href="/boardDelete.do">동작</a>'
                        '<a href="/article">게시글</a>') if self.path == "/" else (
                        '<p style="color:transparent">카지노 가입코드 WIN77 텔레그램 @test_bet</p>')
                data = ('<!doctype html><meta charset="utf-8">' + html).encode()
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
        try:
            res = scan(f"http://127.0.0.1:{server.server_port}/", max_pages=10)
            self.assertIn("/article", received)
            self.assertFalse([url for url in received if is_state_change_url("http://localhost" + url)], received)
            self.assertTrue(any(f["technique"] == "TRANSPARENT" and f["url"].endswith("/article")
                                for f in res["findings"]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
