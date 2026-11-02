"""우회 보정과 정상 대조: 타이머, Shadow DOM, CSS, 문장 집계."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import re
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from findings import classify, walk_frame
from session import BrowserSession
from playwright.sync_api import sync_playwright

AD = '카지노 가입코드 JOIN987 첫충 40% 지급 텔레그램 @join987'


class EvasionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = ('<!doctype html><meta charset="utf-8"><body>' + cls.html).encode()
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
        cls.pw = sync_playwright().start()
        cls.session = BrowserSession(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.session.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def inspect(self, html):
        type(self).html = re.sub(r'id="([a-z]+)"', r'id="\1" class="\1"', html)
        self.session.open(f'http://127.0.0.1:{self.server.server_port}/')
        rows = []
        walk_frame(self.session.page.main_frame, '', self.session.page.url, rows, set())
        for row in rows:
            row['location'] = self.session.page.locator(row['location']).evaluate('(el)=>el.tagName.toLowerCase()+"#"+el.id')
        return rows

    def test_delayed_chained_and_interval_insertions(self):
        rows = self.inspect('''<div id="target"></div><script>
        const add = id => target.insertAdjacentHTML('beforeend', `<p id="${id}" style="display:none">AD</p>`);
        setTimeout(()=>add('late'),1800);
        setTimeout(()=>setTimeout(()=>setTimeout(()=>add('chain'),500),500),500);
        let n=0; const timer=setInterval(()=>{if(++n===4){clearInterval(timer);add('interval')}},400);
        </script>'''.replace('AD', AD))
        self.assertEqual({r['location'] for r in rows if r['technique']=='OFFSCREEN'},
                         {'p#late', 'p#chain', 'p#interval'})

    def test_repeating_normal_timer_has_bounded_wait(self):
        start = time.monotonic()
        rows = self.inspect('<p>행정 안내</p><script>setInterval(()=>document.body.dataset.tick=Date.now(),80)</script>')
        self.assertLess(time.monotonic()-start, 6)
        self.assertFalse(rows)

    def test_closed_shadow_is_inspected_without_changing_mode(self):
        rows = self.inspect('''<div id="host"></div><script>
        host.attachShadow({mode:'closed'}).innerHTML='<span style="position:absolute;left:-9999px">AD</span>';
        </script>'''.replace('AD', AD))
        self.assertIsNone(self.session.page.evaluate('document.getElementById("host").shadowRoot'))
        self.assertTrue(any(r['location']=='div#host' and r['technique']=='OFFSCREEN' for r in rows))

    def test_mask_and_blend_with_visible_and_normal_controls(self):
        rows = self.inspect(f'''<div style="background:white">
        <span id="mask" style="display:inline-block;mask-image:linear-gradient(transparent,transparent)">{AD}</span>
        <span id="blend" style="color:black;mix-blend-mode:screen">{AD}</span>
        <span id="partial" style="display:inline-block;mask-image:linear-gradient(black,transparent)">{AD}</span>
        <span id="visible" style="color:black;mix-blend-mode:multiply">{AD}</span>
        <span id="normal" style="mask-image:linear-gradient(transparent,transparent)">메모리 슬롯 확장 안내</span>
        </div>''')
        transparent = {r['location'] for r in rows if r['technique']=='TRANSPARENT'}
        self.assertEqual(transparent, {'span#mask', 'span#blend'})
        self.assertFalse(any(r['location']=='span#normal' for r in rows))

    def test_inline_sentence_aggregates_but_independent_ads_remain(self):
        rows = self.inspect(f'''<div id="sentence" style="display:none"><span>안전놀이터 먹튀검증</span><span>카지노 첫충 40%</span><span>텔레그램 @join987</span></div>
        <div style="display:none"><a id="one">{AD}</a><a id="two">{AD}</a></div>
        <section style="display:none"><p id="three">{AD}</p><p id="four">{AD}</p></section>''')
        self.assertEqual({r['location'] for r in rows if r['technique']=='OFFSCREEN'},
                         {'div#sentence', 'a#one', 'a#two', 'p#three', 'p#four'})

    def test_css_display_order_with_benign_control(self):
        chars = ''.join(f'<span style="order:{i}">{c}</span>' for i,c in reversed(list(enumerate(AD))))
        rows = self.inspect(f'''<span id="rtl" style="unicode-bidi:bidi-override;direction:rtl">{AD[::-1]}</span>
        <span id="flex" style="display:inline-flex">{chars}</span>
        <span id="normal" style="unicode-bidi:bidi-override;direction:rtl">{('메모리 슬롯 확장 안내')[::-1]}</span>''')
        self.assertEqual({r['location'] for r in rows}, {'span#rtl', 'span#flex'})
        self.assertTrue(all(r['technique']=='ETC' and r['evidence_text']==AD for r in rows))

    def test_compound_slang_requires_delivery_and_contact(self):
        self.assertTrue(classify('캔디 허브 크리스탈 던지기 텔레그램 @contact123')['is_ad'])
        for text in ('캔디 허브 크리스탈 판매 문의 @store123',
                     '캔디 허브 크리스탈 던지기',
                     '마약 예방 교육: 캔디 허브 크리스탈 던지기 텔레그램 @example123'):
            self.assertFalse(classify(text)['is_ad'], text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
