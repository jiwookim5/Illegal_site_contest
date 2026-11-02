"""테스트 사이트 서버. 실제 게시판처럼 쿼리스트링으로 페이지를 구분한다."""
import html, os, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get("SITE", "testsite")
ROOT = os.path.join(BASE, SITE)

ROUTES = {
    ("/board/list", None): "pages/list.html",
    ("/board/view", "1024"): "pages/view_1024.html",
    ("/board/view", "1180"): "pages/view_1180.html",
    ("/board/view", "1301"): "pages/view_1301.html",
    ("/board/view", "1009"): "pages/view_1009.html",
    ("/widget/notice", None): "pages/widget_notice.html",
    ("/board/extra", None): "pages/extra.html",
}


_routes_file = os.path.join(ROOT, "routes.json")
if os.path.exists(_routes_file):
    import json as _json
    ROUTES = {(path, val or None): v
              for k, v in _json.load(open(_routes_file, encoding="utf-8")).items()
              for path, val in [k.split("|")]}


def render_search(spec, params, method):
    """검색결과 페이지 흉내. 입력값을 {{q}} 자리에 (HTML 이스케이프해서) 반사한다.

    routes.json 값이 객체이면 이 경로를 탄다.
      page    : 템플릿 파일
      reflect : 반사할 파라미터 이름
      method  : "POST" 이면 POST 본문만 반사하고 GET 에는 빈 값
      headers : 추가 응답 헤더 (예: X-Robots-Tag)
      counter : 이 파라미터 값(정수)을 {{n}}, 앞뒤 값을 {{prev}}·{{next}} 에 넣는다 (끝없는 달력 흉내)
    {{sid}} 는 응답마다 새로 만든 값으로 바뀐다 (방문할 때마다 주소가 달라지는 링크 흉내)
    """
    q = ""
    if spec.get("reflect") and method == spec.get("method", "GET"):
        q = params.get(spec["reflect"], [""])[0]
    page = open(os.path.join(ROOT, spec["page"]), encoding="utf-8").read()
    if spec.get("counter"):
        try:
            n = int(params.get(spec["counter"], ["0"])[0])
        except ValueError:
            n = 0
        page = page.replace("{{n}}", str(n)).replace("{{prev}}", str(n - 1)).replace("{{next}}", str(n + 1))
    page = page.replace("{{sid}}", os.urandom(6).hex())
    return page.replace("{{q}}", html.escape(q)).encode("utf-8"), spec.get("headers", {})


PRIMARY_PORT = None      # 점검 대상 누리집 포트. 나머지 포트는 바깥 누리집 흉내


class Handler(BaseHTTPRequestHandler):
    def send_dynamic(self, spec, params, method):
        # delay: 느린 서버 흉내(초). status: 오류 응답 흉내 (본문은 템플릿 그대로)
        if spec.get("delay"):
            time.sleep(spec["delay"])
        if spec.get("status", 200) >= 400:
            self.send_error(spec["status"])
            return
        body, headers = render_search(spec, params, method)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urlparse(self.path)
        # 점검 도구가 보내면 안 되는 요청(삭제 등)이 왔는지 시험에서 확인할 수 있게 남긴다
        with open(os.path.join(ROOT, "_posted.log"), "a", encoding="utf-8") as fp:
            fp.write(self.path + "\n")
        spec = ROUTES.get((u.path, None))
        if isinstance(spec, dict) and spec.get("post_page"):
            # 댓글 목록처럼 POST 로 조각을 돌려주는 경로
            body = open(os.path.join(ROOT, spec["post_page"]), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not isinstance(spec, dict):
            self.send_error(405)
            return
        n = int(self.headers.get("Content-Length") or 0)
        params = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        self.send_dynamic(spec, params, "POST")

    def do_GET(self):
        u = urlparse(self.path)
        u = u._replace(path=unquote(u.path))      # 한글 경로(/게시판/…)는 퍼센트 인코딩으로 들어온다
        # 크롤러에게만 다른 내용을 주는 페이지 (클로킹 탐지 시험용)
        if u.path == "/board/cloak":
            ua = self.headers.get("User-Agent", "")
            if "Googlebot" in ua:
                body = ("<!DOCTYPE html><html lang=ko><head><meta charset=utf-8>"
                        "<title>민원 안내</title></head><body><h2>민원 안내</h2>"
                        "<p>카지노 먹튀검증 안전놀이터 순위 안내 텔레그램 @promo_777</p>"
                        "</body></html>")
            else:
                body = ("<!DOCTYPE html><html lang=ko><head><meta charset=utf-8>"
                        "<title>민원 안내</title></head><body><h2>민원 안내</h2>"
                        "<p>증명서 발급은 1층 민원실에서 가능합니다.</p></body></html>")
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        qs = parse_qs(u.query)
        val = None
        for k in ("id", "no", "seq", "pid", "atchFileId", "nttId", "pageIndex"):  # 사이트마다 파라미터 이름이 다르다
            if k in qs:
                val = qs[k][0]
                break
        rel = None
        # 여러 포트로 띄우면 포트마다 다른 누리집이다 (routes.json 의 ":8779/경로|" 꼴)
        for path in (f":{self.server.server_address[1]}{u.path}", u.path):
            rel = ROUTES.get((path, val))
            if rel is None and val is not None:
                rel = ROUTES.get((path, None))   # 페이지 번호 등이 붙어도 같은 화면인 경로
            if rel is not None:
                break
        if self.server.server_address[1] != PRIMARY_PORT:
            # 바깥 누리집 흉내에 온 요청. 연계 링크 확인을 끈 실행에서는 0건이어야 한다
            with open(os.path.join(ROOT, "_ext_get.log"), "a", encoding="utf-8") as fp:
                fp.write(f"{self.server.server_address[1]}{self.path}\n")
        if isinstance(rel, dict) and rel.get("redirect"):
            # 옛 주소·짧은 주소가 실제 글로 넘겨지는 경우 (리다이렉트 중복 방문 시험용)
            self.send_response(rel.get("status", 302))
            self.send_header("Location", rel["redirect"])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if isinstance(rel, dict):
            self.send_dynamic(rel, qs, "GET")
            return
        if rel is None and u.path == "/robots.txt":
            rel = "robots.txt"
        if rel is None and (u.path.startswith(("/css/", "/files/"))):
            rel = u.path.lstrip("/")
        if rel is None:
            self.send_error(404)
            return
        full = os.path.join(ROOT, rel)
        if not os.path.exists(full):
            self.send_error(404)
            return
        if full.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif full.endswith(".txt"):
            ctype = "text/plain; charset=utf-8"
        elif full.endswith((".pdf", ".hwp", ".hwpx")):
            ctype = {"pdf": "application/pdf", "hwp": "application/x-hwp",
                     "hwpx": "application/hwp+zip"}[full.rsplit(".", 1)[1]]
        elif full.endswith(".euckr.html"):
            ctype = "text/html; charset=euc-kr"
        elif full.endswith(".nocharset.html"):
            ctype = "text/html"          # 문자 집합은 페이지 안 meta 로만 알린다
        else:
            ctype = "text/html; charset=utf-8"
        body = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if "/files/" in full.replace(os.sep, "/"):
            self.send_header("Content-Disposition",
                             f'attachment; filename="{os.path.basename(full)}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # 포트를 여럿 주면 모두 띄운다. 연계 링크 시험에서 포트마다 다른 바깥 누리집을 흉내 낸다.
    import threading
    ports = [int(a) for a in sys.argv[1:]] or [8765]
    PRIMARY_PORT = ports[0]
    for extra in ports[1:]:
        threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", extra), Handler).serve_forever,
                         daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", ports[0]), Handler).serve_forever()
