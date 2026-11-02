"""Remaining evasion cases with independent visual, context and timing controls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from io import BytesIO
import sys
import threading
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'detector'))
from playwright.sync_api import sync_playwright
from session import BrowserSession
from findings import walk_frame
from font_text import FontText, font_mapping
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from runtime import asset_path

AD='카지노 가입코드 TEST982 첫충 30% 텔레그램 @test982'


def alternate_font():
    """Different cmap, family and glyph names; no test-specific runtime lookup."""
    phrases=('카지노가입문의텔레그램','메모리슬롯무료확장안내')
    chars=list(dict.fromkeys(''.join(phrases)))
    with TTFont(asset_path('fonts/PretendardVariable.woff2')) as reference:
        glyphs=reference.getGlyphSet(location={'wght':400})
        cmap=reference.getBestCmap()
        units=reference['head'].unitsPerEm
        codes={ch:chr(65+i) for i,ch in enumerate(chars)}
        outlines={'.notdef':TTGlyphPen(None).glyph()}; widths={'.notdef':(units,0)}
        mapping={}
        for i,ch in enumerate(chars):
            name=f'opaque{i}'
            pen=TTGlyphPen(glyphs);glyphs[cmap[ord(ch)]].draw(pen)
            outlines[name]=pen.glyph();widths[name]=(round(glyphs[cmap[ord(ch)]].width),0)
            mapping[ord(codes[ch])]=name
        font=FontBuilder(units,isTTF=True)
        font.setupGlyphOrder(list(outlines));font.setupCharacterMap(mapping)
        font.setupGlyf(outlines);font.setupHorizontalMetrics(widths)
        font.setupHorizontalHeader(ascent=units,descent=-units//4)
        font.setupNameTable({'familyName':'IndependentShapes','styleName':'Regular'})
        font.setupOS2(sTypoAscender=units,sTypoDescender=-units//4,usWinAscent=units,usWinDescent=units//4)
        font.setupPost();font.setupMaxp();font.font.flavor='woff'
        out=BytesIO();font.save(out)
        return out.getvalue(), [''.join(codes[c] for c in p) for p in phrases]


class RemainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font,cls.encoded=alternate_font()
        cls.requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.requests.append(self.path)
                if self.path=='/font.woff': body=cls.font;kind='font/woff'
                else:
                    if self.path=='/slow': time.sleep(17)
                    body=('<!doctype html><meta charset="utf-8"><body>'+cls.html).encode();kind='text/html; charset=utf-8'
                self.send_response(200);self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(body)));self.end_headers()
                try:self.wfile.write(body)
                except (BrokenPipeError,ConnectionResetError):pass
            def log_message(self,*args):pass
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.pw=sync_playwright().start();cls.session=BrowserSession(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.session.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def inspect(self,html,path='/'):
        type(self).html=html
        self.session.open(f'http://127.0.0.1:{self.server.server_port}{path}')
        rows=[];walk_frame(self.session.page.main_frame,'',self.session.page.url,rows,set())
        return rows

    def test_negative_bottom_not_ordinary_below_fold(self):
        rows=self.inspect(f'''<div style="position:relative;height:30px"><span class="displaced" style="position:absolute;bottom:-7000px">{AD}</span></div>
        <div style="height:8000px"></div><p class="below">{AD}</p>
        <div style="position:relative;height:9000px"><span class="bottom" style="position:absolute;bottom:0">{AD}</span></div>
        <div style="position:relative;height:20px"><span class="normal" style="position:absolute;bottom:-7000px">메모리 슬롯 확장 안내</span></div>''')
        self.assertEqual({r['location'] for r in rows if r['technique']=='OFFSCREEN'},{'span.displaced'})

    def test_hidden_signup_requires_same_promoted_domain(self):
        rows=self.inspect('''<div style="display:none">
        <a class="advert">카지노 가입코드 JOIN88 주소:다른광고.kr</a>
        <a class="variant">가입【주소:다른광고.KR 코드:자동】 링크 안내</a>
        <a class="normal">가입【주소:시민교육.kr 코드:자동】 링크 안내</a></div>
        <div style="display:none"><a class="alone">가입【주소:다른광고.kr 코드:자동】</a></div>''')
        self.assertEqual({r['location'] for r in rows if r['technique']=='OFFSCREEN'},{'a.advert','a.variant'})

    def test_visible_signup_not_tainted_by_adjacent_ads(self):
        rows=self.inspect('''<div><a class="advert">카지노 가입코드 JOIN88 주소:다른광고.kr</a>
        <a class="normal">가입【주소:다른광고.kr 코드:자동】 링크 안내</a></div>''')
        self.assertFalse(any(r['location']=='a.normal' for r in rows))

    def test_canvas_requires_final_pixels_and_normal_content_is_safe(self):
        canvases=''.join(f'<canvas class="{c}" width="700" height="50"></canvas>' for c in ('advert','normal','cleared','overwritten','outside','transparent','clipped','resized'))
        rows=self.inspect(canvases+'''<script>
        for(const canvas of document.querySelectorAll('canvas')) {
          const c=canvas.getContext('2d');c.font='18px sans-serif';
          if(canvas.className==='transparent')c.globalAlpha=0;
          if(canvas.className==='clipped'){c.rect(0,0,1,1);c.clip()}
          c.fillText(canvas.className==='normal'?'메모리 슬롯 확장 안내':'AD',canvas.className==='outside'?10000:2,25);
          if(canvas.className==='cleared')c.clearRect(0,0,700,50);
          if(canvas.className==='overwritten'){c.fillStyle='white';c.fillRect(0,0,700,50)}
          if(canvas.className==='resized')canvas.width=700;
        }</script>'''.replace('AD',AD))
        self.assertEqual({r['location'] for r in rows},{'canvas.advert'})
        self.assertEqual(rows[0]['technique'],'ETC')

    def test_font_outline_matching_ignores_family_cmap_and_glyph_names(self):
        rows=self.inspect(f'''<style>@font-face{{font-family:UnrelatedFamily;src:url('/font.woff')}}.custom{{font-family:UnrelatedFamily}}</style>
        <span class="advert custom">{self.encoded[0]}</span>
        <span class="normal custom">{self.encoded[1]}</span>''')
        self.assertEqual({r['location'] for r in rows},{'span.advert.custom'})
        self.assertEqual(rows[0]['evidence_text'],'카지노가입문의텔레그램')
        self.assertEqual(rows[0]['technique'],'ETC')

    def test_broken_font_does_not_break_text_extraction(self):
        decoder=FontText();decoder.data['bad']=b'not a font'
        node={'text':'normal','fontSources':['bad']}
        self.assertEqual(decoder.recover(node),node)

    def test_slow_readable_response_is_not_a_block(self):
        rows=self.inspect(f'<span class="slow" style="display:none">{AD}</span>','/slow')
        self.assertTrue(any(r['location']=='span.slow' and r['technique']=='OFFSCREEN' for r in rows))


if __name__=='__main__':unittest.main(verbosity=2)
