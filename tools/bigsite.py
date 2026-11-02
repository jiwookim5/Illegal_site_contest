"""대규모 누리집을 흉내 내는 시험용 서버.

수천 페이지 규모에서 검출 시간이 30분 상한 안에 들어오는지 확인하기 위한 것이다.
실제 공공 사이트에 부하를 주지 않고 재현 가능한 측정을 하려고 즉석 생성한다.
"""
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

POSTS = 2000          # 전체 게시글 수
PER_PAGE = 20
AD_EVERY = 37         # 몇 개마다 숨은 광고를 심을지
LATENCY = 0.0         # 응답마다 넣는 지연(초). 실제 공공 서버의 응답 시간을 흉내 낸다

CSS = """<style>
body{font-family:sans-serif;margin:0;color:#222}.wrap{max-width:900px;margin:0 auto;padding:16px}
table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ddd;padding:7px}
.sr{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
.hide1{display:none}.hide2{opacity:0}.hide3{font-size:0}
</style>"""

FILLER = ("본 공고는 관련 법령에 따라 게시되었습니다. 자세한 내용은 담당 부서로 문의하시기 바랍니다. " * 6)

ADS = [
    ('<div class="hide1">온라인 카지노 가입쿠폰 즉시지급 bit.ly/aaaa</div>', "OFFSCREEN"),
    ('<span class="hide2">ㅌㅗㅌㅗ ㅅㅏㅇㅣㅌㅡ ㅊㅜㅊㅓㄴ</span>', "TRANSPARENT+JAMO"),
    ('<p class="hide3">에볼루션 바카라 무료머니 지급</p>', "OFFSCREEN"),
    ('<h3>ｍｅｇａ－ＢＥＴ 첫충 30％ 지급</h3>', "HOMOGLYPH"),
]


def list_page(page):
    start = (page - 1) * PER_PAGE + 1
    rows = []
    for i in range(start, min(start + PER_PAGE, POSTS + 1)):
        rows.append(f'<tr><td>{i}</td><td><a href="/big/view?id={i}">{i}번 공고 안내</a></td>'
                    f'<td>2026-01-01</td></tr>')
    nav = []
    if page > 1:
        nav.append(f'<a href="/big/list?page={page - 1}">이전</a>')
    if start + PER_PAGE <= POSTS:
        nav.append(f'<a href="/big/list?page={page + 1}">다음</a>')
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            f'<title>공지 {page}쪽</title>{CSS}</head><body>'
            f'<a href="#m" class="sr">본문 바로가기</a><div class="wrap"><main id="m">'
            f'<h1>공지사항 ({page}쪽)</h1><table><tbody>{"".join(rows)}</tbody></table>'
            f'<p>{" ".join(nav)}</p></main></div></body></html>')


def view_page(pid):
    ad = ADS[(pid // AD_EVERY) % len(ADS)][0] if pid % AD_EVERY == 0 else ""
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            f'<title>{pid}번 공고</title>{CSS}</head><body>'
            f'<a href="#m" class="sr">본문 바로가기</a><div class="wrap"><main id="m">'
            f'<h2>{pid}번 공고 안내</h2><p class="body">{FILLER}</p>{ad}'
            f'<p><a href="/big/list?page=1">목록</a></p></main></div></body></html>')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if LATENCY:
            time.sleep(LATENCY)
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path == "/big/list":
            body = list_page(int(qs.get("page", ["1"])[0]))
        elif u.path == "/big/view":
            body = view_page(int(qs.get("id", ["1"])[0]))
        else:
            self.send_error(404)
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # 사용법: python bigsite.py [포트] [응답 지연 ms]
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8800
    LATENCY = int(sys.argv[2]) / 1000 if len(sys.argv) > 2 else 0.0
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
