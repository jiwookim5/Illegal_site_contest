"""문서 뷰어(시냅) 글자층을 숨긴 글로 보지 않는지, 같은 꼴을 흉내 낸 숨김 광고는 계속 잡는지 확인한다.

2026-10-19 gb.go.kr 시냅 뷰어의 채용 신체검사서 '마약류 검사 필로폰 대마 …'를 화면 밖 은닉 광고로 봤다.
뷰어는 쪽 그림 위에 글자 크기 0 글자층을 겹쳐 두므로 그 글은 그림으로 보인다 (extract_js.documentTextLayer).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_page_builtin_overrides import Site  # noqa: E402

AD = "안전놀이터 가입쿠폰 지급 텔레 @abcd1234"
LAYER = ('<div class="contents-page" id="page-area1" style="font-size:0">'
         '<img class="contents-page__img" id="page1" src="/page1.png" width="800" height="1100">'
         '<div class="textlayer"><span>{}</span></div></div>')
SYNAP = '<script src="/synap_skin/js/newviewer.js"></script>'
SITE = {
    "/": '<a href="/viewer">뷰어</a> <a href="/fake">흉내</a> <a href="/viewer-hidden">뷰어 숨김</a>',
    # 시냅 뷰어: 글자층의 글은 쪽 그림으로 보인다
    "/viewer": SYNAP + LAYER.format(AD),
    # 같은 꼴이지만 뷰어 스크립트가 없다: 숨긴 광고로 본다
    "/fake": LAYER.format(AD),
    # 뷰어 안이라도 display:none 으로 감춘 글은 그림과 상관없이 숨김이다
    "/viewer-hidden": SYNAP + LAYER.format("공지") + f'<div class="contents-page" id="page-area2">'
                      f'<img class="contents-page__img"><span style="display:none">{AD}</span></div>',
    "/synap_skin/js/newviewer.js": "",
}


class DocumentViewerLayerTest(unittest.TestCase):
    def test_viewer_text_layer_is_not_concealment(self):
        from scan import scan
        with Site(SITE) as base:
            res = scan(base + "/", max_pages=10, respect_robots=False, primary_only=True)
        hidden = {}
        for f in res["findings"]:
            hidden.setdefault(f["url"].split(base)[-1], set()).add(f["technique"])
        self.assertNotIn("/viewer", hidden, res["findings"])
        self.assertIn("OFFSCREEN", hidden.get("/fake", set()), res["findings"])
        self.assertIn("OFFSCREEN", hidden.get("/viewer-hidden", set()), res["findings"])


if __name__ == "__main__":
    unittest.main()
