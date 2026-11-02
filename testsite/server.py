"""로컬 함정 테스트 사이트.

주최 측 평가 사이트를 흉내 낸 합성 사이트다. 필수 4종 정답과 함께
"정상적인 숨김/특수문자"(오탐 유도 함정)를 섞어 두었다.
정답셋은 testsite/answers.json (BASE 는 실행 시 주소로 치환).

  python testsite/server.py            # http://127.0.0.1:8000/
  python testsite/server.py --port 8100
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

CSS = """
body { font-family: sans-serif; background: #ffffff; color: #222; margin: 0; }
.wrap { max-width: 960px; margin: 0 auto; padding: 16px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.skip { position: absolute; left: -9999px; }
.gnb .sub { display: none; }
.menu-open .gnb .sub { display: block; }
.fade { opacity: 0; }
.ghost { color: #ffffff; }
.card { background: #f4f6f8; padding: 12px; }
.card .same { color: #f4f6f8; }
.tiny { font-size: 1px; }
.board-list td { padding: 4px 8px; border-bottom: 1px solid #ddd; }
"""


def layout(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title>
<style>{CSS}</style>
<script>
function toggleAllMenu(el) {{ el.setAttribute('aria-expanded', String(document.body.classList.toggle('menu-open'))); }}
function selectCampaignTab(button, index) {{
  document.querySelectorAll('.tab-nav button').forEach((el, i) => el.setAttribute('aria-selected', String(i === index)));
  document.querySelectorAll('.tabs .tab-panel').forEach((el, i) => el.style.display = i === index ? '' : 'none');
}}
function toggleAccordion(button) {{
  var panel = document.querySelector('.acc-body');
  var open = panel.style.display === 'none';
  panel.style.display = open ? '' : 'none'; button.setAttribute('aria-expanded', String(open));
}}
</script></head><body>
<a class="skip" href="#content">본문 바로가기</a>
<header class="wrap"><nav class="gnb"><ul>
  <li><a href="/">홈</a><ul class="sub"><li><a href="/about">기관소개</a></li><li>조직도</li></ul></li>
  <li><a href="/board/list">공지사항</a></li>
  <li><a href="/logout">로그아웃</a></li>
  <li><a href="javascript:void(0);" aria-expanded="false" onclick="toggleAllMenu(this)">전체메뉴</a></li>
  <li><a href="https://www.external-example.com/">외부 링크</a></li>
</ul></nav></header>
<main id="content" class="wrap">{body}</main>
<footer class="wrap"><p>（주）행정테크 · 대표전화 ０２－１２３４－５６７８</p></footer>
</body></html>"""


POSTS = {
    1024: ("시스템 점검 안내", """
<div class="notice-board">
  <p>10월 정기 점검이 진행됩니다.</p>
  <span class="visually-hidden">ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ 코드 LUCKY7</span>
  <span class="sr-only">새창 열림</span>
</div>"""),
    1180: ("주민 참여 프로그램 모집", """
<div class="article-body">
  <p class="desc">참여를 원하시는 분은 신청서를 제출하세요.
    <span style="color: transparent">먹튀검증 안전놀이터 상담 텔레그램 @promo_777</span></p>
  <iframe src="/widget/notice" width="400" height="120"></iframe>
  <p>도박 중독 예방 캠페인에 많은 참여 바랍니다. 상담전화 1336.</p>
</div>"""),
    1201: ("청사 이전 안내", """
<div class="article-body">
  <p>청사가 이전합니다.</p>
  <p class="ghost">메이저사이트 첫충 20% 매충 10% 지급</p>
  <div class="card"><span class="same">스포츠토토 롤링 없는 꽁머니 지급</span> 안내문입니다.</div>
  <div style="display:none"><p>카지노 가입코드 WIN77 즉시 환전</p></div>
  <span class="tiny">바카라 사이트 추천 bmm7.top</span>
  <p class="fade">슬롯 무료체험 텔레 @slot_king</p>
  <p>이벤트: cаsinо 보너스 100% 지급</p>
  <p class="ghost">ｍｅｇａ－ＢＥＴ 첫충 30％ 지급</p>
  <p lang="ru">Привет, добро пожаловать</p>
</div>
<div class="comments">
  <div class="comment"><span class="writer">김민원</span><p>ㅋㅋㅋ 좋은 정보 감사합니다 ㅠㅠ</p></div>
  <div class="comment"><span class="writer">익명</span><p>ㅁㅓㄱㅌㅟ ㄱㅓㅁㅈㅡㅇ 된 ㅅㅏㅇㅣㅌㅡ 여기</p></div>
</div>"""),
    1202: ("위젯 안내", """
<div class="article-body">
  <p>관련 위젯입니다.</p>
  <iframe src="/widget/outer"></iframe>
</div>"""),
    1300: ("정상 게시글", """
<div class="article-body">
  <p>불법 도박 사이트 신고는 사이버수사대로 해주세요.</p>
  <p style="display:none">관리자 메모: 게시글 검수 완료</p>
</div>"""),
}
PAGE_SIZE = 3


def board_list(page: int) -> str:
    ids = sorted(POSTS)
    if not 1 <= page <= (len(ids) + PAGE_SIZE - 1) // PAGE_SIZE:
        raise ValueError("page outside board range")
    chunk = ids[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    # 목록에서는 부가 파라미터(page=)가 붙은 URL 로, 홈에서는 id 만 있는 URL 로 연결한다.
    # 같은 게시글이 두 URL 로 발견될 때 한 번만(파라미터가 적은 URL 로) 보고하는지 검증.
    rows = "".join(
        f'<tr><td class="num">{i}</td><td class="title">'
        f'<a href="/board/view?id={i}&amp;page={page}">{POSTS[i][0]}</a></td></tr>'
        for i in chunk)
    if page == 1:  # 목록 제목에 닮은꼴 위장 광고 한 줄
        rows += ('<tr><td class="num">999</td><td class="title">'
                 '<a href="/board/view?id=1300">ｍｅｇａ－ＢＥＴ 첫충 30％ 지급</a></td></tr>')
    pages = (len(ids) + PAGE_SIZE - 1) // PAGE_SIZE
    # 1페이지는 /board/list 로 연결 (?page=1 은 채점상 다른 페이지로 취급되므로 정답 모호성 방지)
    nav = " ".join(f'<a href="/board/list{"" if p == 1 else f"?page={p}"}">{p}</a>' for p in range(1, pages + 1))
    return layout("공지사항", f'<h1>공지사항</h1><table class="board-list"><tbody>{rows}</tbody></table>'
                            f'<div class="paging">{nav}</div>')


# ---------------------------------------------------------------- 오탐 유도 페이지
# 도박을 "주제로" 다루는 정상 콘텐츠를 탭·아코디언·모달·스크린리더 전용 영역에 숨겨 둔다.
# 각 페이지에는 진짜 광고도 1건씩 섞어서, 오탐만 줄이고 정탐을 놓치지 않는지 함께 본다.
EXTRA_PAGES = {
    "/policy/campaign": ("불법도박 예방 캠페인", """
<div class="tabs">
  <ul class="tab-nav" role="tablist">
    <li><button type="button" role="tab" aria-selected="true" onclick="selectCampaignTab(this,0)">예방 수칙</button></li>
    <li><button type="button" role="tab" aria-selected="false" onclick="selectCampaignTab(this,1)">신고 안내</button></li>
    <li><button type="button" role="tab" aria-selected="false" onclick="selectCampaignTab(this,2)">신고 포상</button></li>
    <li><button type="button" role="tab" aria-selected="false" onclick="selectCampaignTab(this,3)">상담</button></li>
  </ul>
  <div class="tab-panel on"><p>건전한 사이버 문화를 함께 만들어요.</p></div>
  <div class="tab-panel" style="display:none"><p>사설토토 먹튀 피해 예방 수칙 안내</p></div>
  <div class="tab-panel" style="display:none"><p>불법 스포츠토토 신고 시 포상금 지급</p></div>
  <div class="tab-panel" style="display:none"><p>도박문제 상담 1336, 슬롯머신 중독 치유 프로그램 무료 상담</p></div>
</div>
<div class="ticker"><span class="skip">먹튀검증 사이트 이용 주의: 경찰청 단속 강화</span></div>
<p class="ghost">먹튀 신고 없는 메이저사이트 텔레그램 @major77</p>"""),
    "/recruit": ("채용·공시", """
<div class="accordion">
  <button type="button" aria-expanded="false" onclick="toggleAccordion(this)">채용 공고</button>
  <div class="acc-body" style="display:none"><p>강원랜드 카지노 딜러 채용 공고</p><p>한국마사회 경마 배당률 공시</p></div>
</div>
<div class="carousel"><div class="slide" style="transform: translateX(-2000px)">스포츠토토（주） 사회공헌 보고서</div></div>
<p>주주총회 안내: 2025년 주주 배당금 지급 안내</p>"""),
    "/contact": ("찾아오시는 길", """
<div class="sr-only">담당자 hong@korea.kr 기관코드 B551011</div>
<a class="skip" href="#parking">주차 슬롯 예약 바로가기</a>
<section id="parking" tabindex="-1"><h2>주차 안내</h2><p>방문객 주차 및 예약 안내는 대표전화로 문의해 주세요.</p></section>
<div class="modal" style="display:none">
  <p>행복주택 오피스텔 입주자 모집 공고</p><p>쿠폰 코드 WELCOME2026 입력 시 할인</p><p>환전 수수료 우대 이벤트</p>
</div>
<p class="tiny">어린이 놀이터 안전점검 추천 업체</p>
<p class="ghost">안전놀이터 첫충 30％ 즉시 지급</p>"""),
    # 추가 탐지 유형(result_extra.json) — 필수 4종에는 해당하지 않아 result.json 정답은 없다.
    # 각 광고 옆에 같은 기법을 쓴 정상 문구를 둬서 오탐 여부를 함께 본다.
    "/notice/seo": ("검색 최적화 안내", """
<style>
.seo .gen-ad::after { content: "\\BC14\\CE74\\B77C  사이트 추천 gen77.top"; }
.seo .gen-ok::before { content: "새창 열림"; }
.seo .lowc, .seo .lowc-ok { color: #f2f2f2; }
.seo .dim { opacity: 0.12; }
</style>
<div class="seo">
  <p class="zw">카​지​노 가입코드 ZW777 텔레 @zw_bet</p>
  <p class="zw-ok">공공​데이터 포털 이용 안내</p>
  <span class="gen-ad"></span>
  <span class="gen-ok"></span>
  <p class="lowc">메이저사이트 첫충 10% 지급 텔레 @lowc_bet</p>
  <p class="lowc-ok">개인정보처리방침</p>
  <p class="dim">슬롯사이트 꽁머니 지급 텔레 @dim_bet</p>
  <img class="seo-img" alt="토토사이트 추천 꽁머니 지급 텔레 @alt_bet" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">
  <img class="seo-img-ok" alt="청사 전경 사진" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">
  <a class="title-ad" href="/about" title="카지노사이트 첫충 지급 텔레 @title_bet">기관소개 바로가기</a>
  <a class="title-ok" href="/about" title="새창 열림">기관소개</a>
</div>"""),
}

WIDGETS = {
    "/widget/notice": '<div class="wrap"><span class="hidden-link" style="position:absolute; left:-9999px">'
                      '무료 슬롯 체험 바로가기</span><p>공지 위젯</p></div>',
    "/widget/outer": '<div class="outer"><p>외부 위젯</p><iframe src="/widget/inner"></iframe></div>',
    "/widget/inner": '<div class="inner"><p>내부 위젯</p><em style="display:none">홀덤 파워볼 총판 모집</em></div>',
}


# ---------------------------------------------------------------- 전자정부식 JS 게시판
# 공공 사이트에 흔한 패턴: <a href> 없이 자바스크립트 함수·폼 전송으로 이동한다.
#   2001  href="javascript:fn_view('2001')"      → 함수 안에서 URL 조립 (클릭해야 알 수 있음)
#   2002  href="#" onclick="fn_view(2002)"       → 같은 방식
#   2003  <tr onclick="location.href='...'">     → 속성 안에 URL 문자열 (정적 추출 가능)
#   2004  2페이지에만 있음, 페이지 이동은 fn_link_page(2) → GET 폼 전송
#   2005  fn_view_post(2005) → POST 폼 전송 (URL 로 표현 불가 → 수집 보고서에 "POST 전용"으로 남아야 함)
EGOV_POSTS = {
    2001: ("민원 처리 결과 안내", '<div class="bbs-view"><p>처리 결과를 안내합니다.</p>'
                                '<div class="hide-box" style="display:none"><p>바카라 사이트 가입코드 BK777</p></div></div>'),
    2002: ("정보공개 청구 안내", '<div class="bbs-view"><p>정보공개 청구 방법입니다.</p>'
                               '<p class="w">토토사이트 첫충 15% 텔레 @egov_bet</p></div>'),
    2003: ("주민등록 발급 안내", '<div class="bbs-view"><p>발급 절차입니다.</p>'
                               '<span class="t">카지노 무료 체험 winwin.top</span></div>'),
    2004: ("2페이지 게시글", '<div class="bbs-view"><p>두 번째 페이지의 글입니다.</p>'
                           '<p class="reply">ㅇㅏㄴㅈㅓㄴㄴㅗㄹㅇㅣㅌㅓ ㅊㅜㅊㅓㄴ</p></div>'),
    2005: ("POST 전용 게시글", '<div class="bbs-view"><p>POST 로만 열리는 글입니다.</p></div>'),
}
EGOV_CSS = ".bbs-view .w { color: #fff; } .bbs-view .t { font-size: 0; }"
EGOV_POST_ONLY = {2005}
EGOV_SCRIPT = """<script>
function fn_view(id) { location.href = '/egov/view?nttId=' + id; }
function fn_view_post(id) { var f = document.getElementById('postForm'); f.nttId.value = id; f.submit(); }
function fn_link_page(n) { var f = document.getElementById('listForm'); f.pageIndex.value = n; f.submit(); }
function fn_ready() { alert('준비 중입니다.'); }
</script>"""


def egov_list(page: int) -> str:
    if page not in (1, 2):
        raise ValueError("page outside eGov board range")
    if page == 1:
        rows = """
<tr><td class="subject"><a href="javascript:fn_view('2001')">민원 처리 결과 안내</a></td></tr>
<tr><td class="subject"><a href="#" onclick="fn_view(2002); return false;">정보공개 청구 안내</a></td></tr>
<tr onclick="location.href='/egov/view?nttId=2003'"><td class="subject">주민등록 발급 안내</td></tr>
<tr><td class="subject"><a href="#none" onclick="fn_view_post(2005); return false;">POST 전용 게시글</a></td></tr>
<tr><td class="subject"><a href="javascript:void(0);" onclick="fn_ready();">준비 중인 메뉴</a></td></tr>"""
    else:
        rows = '<tr><td class="subject"><a href="javascript:fn_view(\'2004\')">2페이지 게시글</a></td></tr>'
    return layout("전자민원 게시판", f"""<h1>전자민원 게시판</h1>{EGOV_SCRIPT}
<form id="listForm" method="get" action="/egov/list"><input type="hidden" name="pageIndex" value="{page}"></form>
<form id="postForm" method="post" action="/egov/viewPost"><input type="hidden" name="nttId" value=""></form>
<table class="bbs"><tbody>{rows}</tbody></table>
<div class="paging"><a href="#none" onclick="fn_link_page(1); return false;">1</a>
<a href="#none" onclick="fn_link_page(2); return false;">2</a></div>""")


def egov_view(ntt_id: int) -> str:
    title, body = EGOV_POSTS[ntt_id]
    return layout(title, f"<style>{EGOV_CSS}</style><h1>{title}</h1>{body}")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 <= length <= 1_000_000:
                raise ValueError("invalid form length")
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            ntt_id = int(form.get("nttId", ["0"])[0])
        except (ValueError, UnicodeError):
            self.send_error(400, "Invalid form parameters")
            return
        if urlsplit(self.path).path == "/egov/viewPost" and ntt_id in EGOV_POSTS:
            self._send(egov_view(ntt_id))
        else:
            self.send_error(404)

    def do_GET(self):  # noqa: N802
        try:
            self._get()
        except ValueError:
            self.send_error(400, "Invalid numeric parameter or page range")

    def _get(self):
        parts = urlsplit(self.path)
        qs = parse_qs(parts.query)
        path = parts.path.rstrip("/") or "/"
        if path == "/":
            recent = "".join(f'<li><a href="/board/view?id={i}">{t}</a></li>' for i, (t, _) in sorted(POSTS.items()))
            menu = "".join(f'<li><a href="{p}">{t}</a></li>' for p, (t, _) in EXTRA_PAGES.items())
            html = layout("테스트 기관", f'<h1>테스트 기관 홈</h1><p><a href="/board/list">공지사항 바로가기</a></p>'
                                       f'<p><a href="/egov/list">전자민원 게시판</a></p>'
                                       f'<h2>최근 게시물</h2><ul class="recent">{recent}</ul><ul class="menu">{menu}</ul>'
                                       f'<ul class="old"><li><a href="/old-notice">(구) 공지</a></li>'
                                       f'<li><a href="/broken">통계 서비스</a></li></ul>')
        elif path == "/egov/list":
            html = egov_list(int(qs.get("pageIndex", ["1"])[0]))
        elif path == "/egov/view":
            ntt_id = int(qs.get("nttId", ["0"])[0])
            if ntt_id not in EGOV_POSTS or ntt_id in EGOV_POST_ONLY:
                self.send_error(404)
                return
            html = egov_view(ntt_id)
        elif path == "/broken":
            self.send_error(500, "Internal Server Error")
            return
        elif path in EXTRA_PAGES:
            title, body = EXTRA_PAGES[path]
            html = layout(title, f"<h1>{title}</h1>{body}")
        elif path == "/about":
            html = layout("기관소개", "<h1>기관소개</h1><p>정상 페이지입니다.</p>")
        elif path == "/board/list":
            html = board_list(int(qs.get("page", ["1"])[0]))
        elif path == "/board/view" and int(qs.get("id", ["0"])[0]) in POSTS:
            title, body = POSTS[int(qs["id"][0])]
            html = layout(title, f"<h1>{title}</h1>{body}")
        elif path in WIDGETS:
            html = f'<!doctype html><html><head><meta charset="utf-8"></head><body>{WIDGETS[path]}</body></html>'
        elif path == "/logout":
            html = layout("로그아웃", "<p>크롤러가 이 페이지를 방문하면 안 됩니다.</p>")
        else:
            self.send_error(404)
            return
        self._send(html)

    def _send(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def serve(port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    port = ap.parse_args().port
    print(f"테스트 사이트: http://127.0.0.1:{port}/  (Ctrl+C 종료)")
    serve(port).serve_forever()
