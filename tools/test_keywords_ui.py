"""점검 키워드 관리 화면 검증: localhost 서버와 headless Edge 만 쓴다.

머리의 [점검 키워드]로 메인 창 안에서 화면이 바뀌고 돌아가기로 들어오기 전 화면에 돌아가는지,
단어 추가·끄고 켜기·되돌리기·지우기·기본값, 시험해 보기의 판정과 등급,
브라우저 기본 확인창과 새 창을 쓰지 않는지, 좁은 창에서 가로로 넘치지 않는지 본다.
"""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from playwright.sync_api import sync_playwright
from ui.server import Session, Handler


class KeywordStageTests(unittest.TestCase):
    def test_keyword_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            class H(Handler):
                def log_message(self, *args): pass
            H.session = Session(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), H)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            errors, natives = [], []
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel="msedge", headless=True)
                    ctx = browser.new_context(viewport={"width": 1280, "height": 860})
                    kw = ctx.new_page()
                    kw.on("pageerror", lambda e: errors.append(str(e)))
                    kw.on("dialog", lambda d: (natives.append(d.message), d.dismiss()))
                    kw.goto(base + "/")
                    kw.wait_for_selector("#start:not([hidden])")

                    # 화면 이동: 단계 표시 대신 돌아가기 줄, 새 창은 열지 않는다
                    kw.click("#kwbtn")
                    kw.wait_for_selector("#kwstage:not([hidden]) .kwcat")
                    self.assertEqual(len(ctx.pages), 1)
                    self.assertTrue(kw.locator("#start").is_hidden())
                    self.assertTrue(kw.locator("#steps").is_hidden())
                    self.assertEqual(kw.inner_text("#kwback"), "← 주소 입력으로")
                    self.assertEqual(kw.get_attribute("#kwbtn", "aria-current"), "page")

                    text = kw.inner_text("#kwstage")
                    self.assertIn("점검 키워드 관리", text)
                    self.assertNotIn("탐지", text)
                    for name in ("불법 은어 키워드", "유해 업종·종목 키워드", "불법 행위·품목 키워드",
                                 "광고 유도 키워드", "오탐 방지 키워드"):
                        self.assertIn(name, text)
                    self.assertEqual(kw.locator(".kwcat").count(), 5)

                    # 단어 추가: 받침에 맞는 조사, 분류 맨 앞에 빨간 단어, 중복은 거부
                    kw.select_option("#kwcat", "TOPIC")
                    kw.fill("#kwword", "시험업종말")
                    kw.click("#kwadd")
                    kw.wait_for_selector('#kwcat-TOPIC .kw.user[data-w="시험업종말"]')
                    self.assertIn("'시험업종말'을 '유해 업종·종목 키워드'에 추가했습니다. 다음 점검부터",
                                  kw.inner_text("#kwaddmsg"))
                    kw.fill("#kwword", "시험업종말")
                    kw.click("#kwadd")
                    kw.wait_for_selector("#kwaddmsg.bad")

                    # 기본 단어 끄기와 알림의 되돌리기
                    chip = kw.locator('#kwcat-STRONG .kw[data-act="toggle"]').first
                    word = chip.get_attribute("data-w")
                    chip.click()
                    kw.wait_for_selector(f'#kwcat-STRONG .kw.off[data-w="{word}"]')
                    self.assertIn("껐습니다", kw.inner_text("#snack"))
                    kw.click("#snack button")
                    kw.wait_for_selector(f'#kwcat-STRONG .kw[data-w="{word}"][aria-pressed="true"]')

                    # 지우기는 화면 안 확인 창: 취소하면 남고, 지우기를 누르면 사라진다
                    user = '#kwcat-TOPIC .kw.user[data-w="시험업종말"]'
                    kw.click(user)
                    kw.wait_for_selector("#askdlg[open]")
                    self.assertIn("'시험업종말'을 지울까요?", kw.inner_text("#askmsg"))
                    kw.click("#askcancel")
                    kw.wait_for_timeout(200)
                    self.assertEqual(kw.locator(user).count(), 1)
                    kw.click(user)
                    kw.click("#askok")
                    kw.wait_for_selector(user, state="detached")

                    # 시험해 보기: 광고 문장은 판정 등급과 함께, 안내 문장은 광고 아님과 오탐 방지 키워드
                    kw.fill("#kwtest", "꽁머니 지급 텔레 @abc123")
                    kw.click("#kwgo")
                    kw.wait_for_selector("#kwout.ad .lv")
                    self.assertTrue(kw.locator("#kwcats .kw.hit").count() >= 1)
                    kw.fill("#kwtest", "불법 도박 예방 상담센터 안내")
                    kw.click("#kwgo")
                    kw.wait_for_selector("#kwout.ok")
                    self.assertIn("오탐 방지 키워드", kw.inner_text("#kwout"))

                    # 목록에서 찾기
                    kw.fill("#kwfind", "꽁머니")
                    self.assertTrue(all("꽁머니" in w for w in kw.locator("#kwcats .kw").evaluate_all(
                        "els => els.map(e => e.dataset.w)")))
                    kw.fill("#kwfind", "")

                    # 기본값으로 되돌리기
                    kw.fill("#kwword", "되돌림시험")
                    kw.click("#kwadd")
                    kw.wait_for_selector('.kw.user[data-w="되돌림시험"]')
                    kw.click("#kwreset")
                    kw.wait_for_selector("#askdlg[open]")
                    kw.click("#askok")
                    kw.wait_for_selector(".kw.user", state="detached")
                    self.assertIn("기본값으로 되돌렸습니다", kw.inner_text("#snack"))

                    # 좁은 창에서도 가로로 넘치지 않는다 (네이티브 창 최소 폭 940)
                    kw.set_viewport_size({"width": 940, "height": 620})
                    kw.wait_for_timeout(200)
                    self.assertLessEqual(kw.evaluate("document.getElementById('kwstage').scrollWidth"), 940)
                    self.assertLessEqual(kw.evaluate("document.documentElement.scrollWidth"), 940)
                    kw.set_viewport_size({"width": 1280, "height": 860})

                    # 돌아가기: 들어오기 전 화면(주소 입력)과 단계 표시가 그대로 돌아온다
                    kw.click("#kwback")
                    kw.wait_for_selector("#start:not([hidden])")
                    self.assertTrue(kw.locator("#kwstage").is_hidden())
                    self.assertTrue(kw.locator("#steps").is_visible())
                    self.assertIsNone(kw.get_attribute("#kwbtn", "aria-current"))

                    # 키워드 화면을 보는 중에 다른 화면으로 바뀌어야 하면 화면을 빼앗지 않고 돌아갈 곳만 바꾼다
                    kw.click("#kwbtn")
                    kw.wait_for_selector("#kwstage:not([hidden])")
                    kw.evaluate("setStage('result')")
                    self.assertTrue(kw.locator("#kwstage").is_visible())
                    self.assertEqual(kw.inner_text("#kwback"), "← 점검 결과로")
                    kw.click("#kwback")
                    kw.wait_for_selector("#body:not([hidden])")
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
            self.assertEqual(natives, [], "브라우저 기본 확인창이 떴습니다")
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
