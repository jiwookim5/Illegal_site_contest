"""문맥 오탐·스크롤 댓글·쿼리 값이 다른 게시글 주소를 독립적인 로컬 사례로 검사한다."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import json
import tempfile
import threading
import unittest
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from findings import classify, walk_frame
from scan import scan
from report import write as write_report
from session import BrowserSession
from playwright.sync_api import sync_playwright


class ContextTests(unittest.TestCase):
    def test_benign_contexts_in_visible_and_hidden_text(self):
        samples = [
            "도서 추천: 『창가의 토토』 독후 활동 안내",
            "주차 슬롯 예약 바로가기", "메모리 슬롯 확장 이벤트",
            "환전 수수료 우대 이벤트", "담당자 park@dept.go.kr 기관코드 TEST123",
            "담당자 hong@korea.kr 기관코드 B551011",
            "사설토토 먹튀 피해 예방 수칙 안내",
            "ㅂㅏㅋㅏㄹㅏ 불법 광고 예방 교육 자료입니다.",
            "ｃａｓｉｎｏ 불법 홍보를 신고하는 방법 안내입니다.",
            "청소년 도박 예방 교육: 첫충, 꽁머니 지급, 바카라, 홀덤, 파워볼 광고에 속지 마세요.",
        ]
        for text in samples:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)["is_ad"])

    def test_benign_words_do_not_hide_independent_advertising(self):
        samples = [
            "도박 예방 안내 카지노 가입코드 BONUS88 지금 가입",
            "청소년 예방 교육 바카라 꽁머니 지급 t.me/bet_991",
            "ｃａｓｉｎｏ 불법 도박 신고 안내 첫충 지급 텔레그램 @join_918",
            "『창가의 토토』 추천. 토토 가입코드 START77 텔레 @start_778",
            "주차 슬롯 안내. 슬롯사이트 첫충 보너스 50% 지급",
            "환전 수수료 우대. 카지노 환전 가입코드 JOIN88",
            "담당자 notice@go.kr 가입코드 CASINO88 텔레그램 @bet_718",
            "카지노 상담 join@go.kr.example.com",
            "꽁타 구글검색 - 토토사이트 사기, 먹튀 뿌리를 뽑아라!",
        ]
        for text in samples:
            with self.subTest(text=text):
                self.assertTrue(classify(text)["is_ad"])


class DrugSlangTests(unittest.TestCase):
    """필로폰(시원한술·찬술)·케타민(케이)·LSD 판매 글. 공공 누리집 첨부파일 스팸 검색 결과 제목에서 옮겼다."""

    ADS = [
        "케이구하는곳 (텔@PPONGPark) 케이삽니다99",
        "수원LSD팝니다 【텔@jj8385】 수원LSD팝니다 수원LSD팝니다 수원LSD팝니다--LQ089.",
        "시원한술구입방법 (텔레@PPONGPARK) 시원한술구입Ψ",
        "대전찬술삽니다 【텔@Lucifer6974】 대전찬술삽니다 대전찬술삽니다 대전찬술삽니다--dvdFU 대전찬술삽니다",
        # 이미 잡히던 것과 문자 위장 변형도 계속 잡혀야 한다
        "찬술구하는곳 (●텔@PPONGPαɾƙ) 찬술구하는곳88",
        "시원한술구매 >텔@𝙋𝙋𝙊𝙉𝙂𝙋𝙖𝙧𝙠< 시원한술판매T7",
        "시원한술삽니다 ❯●텔@ⓅⓅⓄⓃⒼⓅⒶⓇⓀ❮ 시원한술파는곳ω",
    ]
    NORMAL = [
        # 은어와 같은 낱말이 일상어로 쓰인 글 (판매 낱말·전화번호가 붙어도 텔레그램 아이디가 없으면 광고가 아니다)
        "여름 축제에서 시원한 술 한 잔과 함께하는 지역 먹거리 행사 안내",
        "시원한 술 판매 부스 운영 안내 (문의 033-670-2777)",
        "찬술을 마시면 속이 쓰릴 수 있으니 주의하세요 보건소 건강 상담",
        "케이블TV 구매 안내 문의 카톡 상담", "케이뱅크 구매 한도 안내",
        "케이 구하는 곳 안내 케이스 구매 문의 카톡",
        # 영문 낱말이 아닌 곳에 들어 있는 lsd, LSD 를 학술적으로 다룬 글
        "bills due 안내 문의 카톡 상담", "환각제 LSD의 의학적 이용 연구 동향 논문 소개",
        # 은어 자체를 설명하는 예방 교육·단속 안내 (텔레그램 아이디를 달았어도 예방 문구가 있으면 면제)
        "청소년 마약 예방 교육: 시원한술, 찬술은 필로폰의 은어입니다. 속지 마세요.",
        "마약류 은어 안내: 찬술·시원한술은 필로폰, 케이는 케타민을 뜻합니다. 의심되면 112 신고",
        "마약 예방 교육 안내: 찬술삽니다 텔@abcd1234 같은 글은 신고하세요",
    ]

    def test_examples_are_ads_in_hidden_and_visible_text(self):
        for text in self.ADS:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertTrue(classify(text, strict=strict)["is_ad"])

    def test_everyday_words_and_prevention_notices_are_not_ads(self):
        for text in self.NORMAL:
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    self.assertFalse(classify(text, strict=strict)["is_ad"])


class JudgementTests(unittest.TestCase):
    """판정 등급(확실·의심·경계)은 광고 여부를 바꾸지 않고 사람 검토 순서만 돕는다."""

    def test_match_detail_keeps_verdict_and_explains_score(self):
        import lexicon
        from normalize import normalize
        for text in ("먹튀검증 토토사이트 가입코드 abc123 텔레 @casino77", "사설토토 먹튀 피해 예방 수칙 안내",
                     "주차 슬롯 예약 바로가기", "토토사이트", "바카라 가입 보너스 즉시 지급 www.bet77.com"):
            for strict in (False, True):
                with self.subTest(text=text, strict=strict):
                    norm = normalize(text)
                    detail = lexicon.match_detail(norm, raw=text, strict=strict)
                    self.assertEqual((detail["is_ad"], detail["evidence"]), lexicon.match(norm, raw=text, strict=strict))
                    if detail["is_ad"]:
                        self.assertGreaterEqual(detail["score"], detail["threshold"])
                    elif detail["score"] is not None and detail["score"] >= detail["threshold"]:
                        self.assertTrue(detail["exempt"])       # 보이는 글 기준에서 막힌 이유가 남는다
        prevention = lexicon.match_detail(normalize("사설토토 먹튀 피해 예방 수칙 안내"), raw="사설토토 먹튀 피해 예방 수칙 안내")
        self.assertFalse(prevention["is_ad"])
        self.assertTrue(prevention["caps"] or prevention["penalties"])

    def test_levels_follow_wording_and_concealment(self):
        from judgement import judge
        hidden = classify("먹튀검증 토토사이트 가입코드 abc123 텔레 @casino77")
        self.assertEqual(judge(hidden, ["opacity:0"])["level"], "high")
        barely = classify("토토사이트", strict=True)
        self.assertTrue(barely["is_ad"])
        low = judge(barely)
        self.assertEqual((low["level"], low["label"]), ("low", "경계"))
        self.assertIn("판정 기준을 겨우 넘음", low["reasons"])
        # 같은 글이어도 숨겨 두었으면 숨김이 근거가 되어 경계가 아니다
        self.assertNotEqual(judge(barely, ["화면 밖 좌표"])["level"], "low")
        self.assertEqual(judge(hidden, ["opacity:0"], basis="segment")["level"], "low")
        self.assertIn("토토사이트", judge(hidden)["terms"])

    def test_attachment_keeps_strongest_grade_in_either_paragraph_order(self):
        import io
        import zipfile
        from types import SimpleNamespace
        from attachments import AttachmentScanner
        from judgement import judge
        high = "꽁머니 텔레 @abc123"
        mid = "카지노 가입 보너스 지급"
        self.assertLess(classify(high)["score"]["score"], classify(mid)["score"]["score"])
        self.assertEqual(judge(classify(mid))["level"], "mid")
        expected = judge(classify(high))
        self.assertEqual(expected["level"], "high")
        for paragraphs in ((high, mid), (mid, high)):
            with self.subTest(paragraphs=paragraphs):
                buffer = io.BytesIO()
                body = ''.join(f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>' for text in paragraphs)
                with zipfile.ZipFile(buffer, 'w') as doc:
                    doc.writestr('word/document.xml',
                                 '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                 f'<w:body>{body}</w:body></w:document>')
                response = SimpleNamespace(ok=True, headers={}, body=buffer.getvalue)
                request = SimpleNamespace(get=lambda *a, **kw: response)
                manners = SimpleNamespace(allowed=lambda url: True, wait=lambda: None)
                rows = AttachmentScanner(request, manners, classify).check('http://localhost/board', [
                    dict(href='http://localhost/ad.docx', text='안내문.docx', selector='a#file')])
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["judgement"], expected)
                self.assertIn(high, rows[0]["evidence_text"])
                self.assertIn(mid, rows[0]["evidence_text"])

    def test_many_judgements_keep_concealment_and_score_tiebreak(self):
        from judgement import judge, judge_many
        lower = classify("토토사이트", strict=True)
        higher = classify("꽁머니 가입 보너스 지급")
        self.assertLess(lower["score"]["score"], higher["score"]["score"])
        self.assertEqual(judge(lower, ["흰 글씨"])["level"], "high")
        self.assertEqual(judge(higher, ["흰 글씨"])["level"], "high")
        self.assertEqual(judge_many(iter([lower, higher]), iter(["흰 글씨"])),
                         judge(higher, ["흰 글씨"]))
        self.assertEqual(judge_many([]), judge(None))

    def test_findings_carry_level_but_result_files_do_not(self):
        from findings import findings_from_node
        node = {"text": "먹튀검증 토토사이트 가입코드 abc123 텔레 @casino77", "selector": "div.ad",
                "transparent": True, "offscreen": False, "reasons": ["opacity:0"]}
        rows = findings_from_node("http://127.0.0.1/board", node)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["judgement"]["level"], "high")
        self.assertIn("숨김: opacity:0", rows[0]["judgement"]["reasons"])
        now = __import__("datetime").datetime.now().astimezone()
        with tempfile.TemporaryDirectory() as tmp:
            write_report("http://127.0.0.1/board", dict(started=now, finished=now, elapsed=1, findings=rows), tmp)
            doc = json.loads(Path(tmp, "result.json").read_text(encoding="utf-8"))
        self.assertNotIn("judgement", doc["findings"][0])     # 요강 스키마에는 넣지 않는다


class UrlIdentityTests(unittest.TestCase):
    def test_only_equivalent_url_spellings_are_deduplicated_in_saved_results(self):
        from urls import page_key
        canonical = '/Board/View?bbsId=B1&id=11'
        distinct = [canonical, canonical + '&utm_source=mail',
                    '/Board/View;jsessionid=ABC?bbsId=B1&id=11',
                    canonical + '&pageIndex=1', '/board/view?bbsId=B1&id=11',
                    '/Board/View?bbsId=B1&id=12', canonical + '&empty=']
        aliases = ['/Board/View?id=11&bbsId=B1', canonical + '#ad',
                   '/Board/View/?bbsId=B1&id=11']
        received = []
        class Local(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                received.append(self.path)
                if self.path == '/':
                    body = ''.join(f'<a href="{u.replace("&", "&amp;")}">게시글</a>'
                                   for u in distinct + aliases + ['/normal'])
                elif self.path == '/normal':
                    body = '<p>도박 예방 교육 안내</p>'
                else:
                    # Identical documents are still separate URL findings under the contest contract.
                    body = '<span id="ad" style="display:none">카지노 가입 보너스 지급</span>'
                data = ('<html><meta charset="utf-8"><body>' + body + '</body></html>').encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Local)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            result = scan(base + '/', max_pages=20, respect_robots=False, primary_only=True)
            with tempfile.TemporaryDirectory() as out:
                write_report(base + '/', result, out)
                rows = json.loads((Path(out)/'result.json').read_text(encoding='utf-8'))['findings']
            expected = {base + u for u in distinct}
            self.assertEqual({r['url'] for r in rows}, expected)
            self.assertEqual(len(rows), len(expected))
            self.assertEqual({(r['location'], r['technique']) for r in rows}, {('span#ad', 'OFFSCREEN')})
            self.assertEqual({page_key(u) for u in result['pages']},
                             {page_key(u) for u in expected | {base+'/', base+'/normal'}})
            self.assertEqual(sum(page_key(base+u) == page_key(base+canonical) for u in received), 1)
            self.assertEqual(result['coverage']['failed_count'], 0)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.received.append(self.path)
                u = urlsplit(self.path)
                query = parse_qs(u.query)
                if u.path == '/theme.css':
                    variant = parse_qs(urlsplit(self.headers.get('Referer', '')).query).get('page')
                    css = '.ad{color:transparent;font-size:16px}' if variant == ['3'] else '.ad{font-size:0}'
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/css')
                    self.send_header('Content-Length', str(len(css)))
                    self.end_headers()
                    self.wfile.write(css.encode())
                    return
                if u.path == "/":
                    html = ''.join(f'<a href="{url}">글 보기</a>' for url in (
                        '/article?id=10&page=1', '/article?id=10', '/article?id=10&page=2',
                        '/article?id=10&page=3', '/article?id=11', '/article?id=12&page=1',
                        '/article?page=1&id=10', '/article?id=10&pageIndex=1', '/article?id=10&pageIndex=2'))
                elif u.path == "/lazy":
                    html = '''<div style="height:3000px"></div><div id="comments"></div><div id="end"></div>
                    <script>const observer = new IntersectionObserver(entries => {
                      if (!entries.some(e=>e.isIntersecting)) return;
                      observer.disconnect(); fetch('/fragment').then(r=>r.text()).then(t=>{
                        setTimeout(()=>document.querySelector('#comments').innerHTML=t, 180);
                      });
                    }); observer.observe(document.querySelector('#end'));</script>'''
                else:
                    code = 'OTHER77' if query.get('page') == ['2'] else 'FIRST88'
                    html = f'<span style="font-size:0">카지노 가입코드 {code} 첫충 지급</span>'
                    if u.path == '/article':
                        html = '<link rel="stylesheet" href="/theme.css">' + html.replace('style="font-size:0"', 'class="ad"')
                body = ('<!doctype html><meta charset="utf-8">' + html).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_zero_height_observer_loads_async_comments_repeatedly(self):
        with sync_playwright() as p:
            session = BrowserSession(p)
            try:
                for i in range(6):
                    with self.subTest(repetition=i):
                        session.open(self.base + '/lazy')
                        session.expand()
                        rows = []
                        walk_frame(session.page.main_frame, '', session.page.url, rows, set())
                        self.assertEqual(len(rows), 1)
                        self.assertEqual(rows[0]['technique'], 'OFFSCREEN')
                        self.assertIn('FIRST88', rows[0]['evidence_text'])
                        self.assertEqual(session.page.evaluate('scrollY'), 0)
            finally:
                session.close()

    def test_query_values_survive_submission_even_when_content_is_identical(self):
        result = scan(self.base + '/', max_pages=20)
        expected = {'/article?id=10', '/article?id=10&page=1', '/article?id=10&page=2',
                    '/article?id=10&page=3', '/article?id=11', '/article?id=12&page=1',
                    '/article?id=10&pageIndex=1', '/article?id=10&pageIndex=2'}
        with tempfile.TemporaryDirectory() as out:
            write_report(self.base + '/', result, out)
            rows = json.loads((Path(out) / 'result.json').read_text(encoding='utf-8'))['findings']
        self.assertEqual({r['url'].removeprefix(self.base) for r in rows}, expected)
        self.assertEqual(len(rows), len(expected))  # 순서만 다른 쿼리는 같은 페이지다.
        self.assertEqual([r['technique'] for r in rows if r['url'].endswith('page=3')], ['TRANSPARENT'])
        self.assertEqual(len(result['pages']), len(expected) + 1)

    def test_explicit_page_limit_remains_effective(self):
        result = scan(self.base + '/', max_pages=2)
        self.assertEqual(len(result['pages']), 2)
        self.assertGreater(result['coverage']['left_count'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
