"""Result UI regressions: synthetic findings/scan work, real localhost API, SQLite and headless Edge."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "detector"))
from playwright.sync_api import sync_playwright
from run_archive import RunArchive
from ui.server import Handler, Session
from findings import classify
from judgement import judge

TARGET = "http://127.0.0.1:8774/"


def finding(i, technique="TRANSPARENT", url=TARGET):
    return dict(url=url, location=f"#ad{i}", technique=technique, evidence_text=f"카지노 가입 보너스 {i}",
                normalized=f"카지노 가입 보너스 {i}", reason="local regression fixture", keywords=["카지노"])


def result(rows, pages=None, **extra):
    now = datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)
    return dict(started=now, finished=now, elapsed=1, pages=[TARGET] if pages is None else pages,
                findings=rows, coverage={}, **extra)


class ResultUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "_regress" / ("result-ui-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
        cls.out.mkdir(parents=True)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel="msedge", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        print("UI evidence:", cls.out)

    def setUp(self):
        self.folder = self.out / self._testMethodName
        self.folder.mkdir()
        self.session = Session(str(self.folder))
        class UI(Handler):
            session = self.session
            def log_message(self, *args): pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), UI)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.context = self.browser.new_context(viewport={"width":940, "height":620}, timezone_id="Asia/Seoul")
        self.page = self.context.new_page()
        self.errors, self.dialogs = [], []
        self.page.on("pageerror", lambda err:self.errors.append(str(err)))
        self.page.on("dialog", lambda dialog:(self.dialogs.append(dialog.message), dialog.accept()))
        self.page.goto(self.base)
        self.page.wait_for_function("sessionStorage.getItem('hwonhi-viewed') === '1'")

    def tearDown(self):
        try:
            self.page.screenshot(path=str(self.folder / "screen.png"), full_page=True)
            self.assertEqual(self.errors, [])
        finally:
            self.context.close()
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()

    def install(self, rows, coverage=None):
        res = result(rows)
        if coverage:
            res["coverage"] = coverage
        run = RunArchive(self.folder, TARGET, {"primary_only":True})
        run.finish(res)
        self.session.result, self.session.entry_url = res, TARGET
        self.session._sync_review()
        self.page.evaluate("load()")
        return run

    def summary(self):
        return self.page.locator("#sumgrid dd").all_text_contents()

    def test_review_candidate_survives_reload_export_and_filter(self):
        row = finding(1)
        row.update(evidence_text='재택부업 무료 상담 모집',
                   judgement=judge(classify('재택부업 무료 상담 모집')))
        run = self.install([row, finding(2)])
        submitted = json.loads((run.path / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual([f['location'] for f in submitted['findings']], ['#ad2'])
        fresh = Session(str(self.folder)).payload()['findings']
        self.assertEqual(len(fresh), 2)
        self.assertEqual(fresh[0]['judgement']['decision'], 'review')
        # 광고 근거가 부족한 항목은 '경계' 등급 하나로 모아 보고, 제출 제외 표시만 따로 붙인다
        self.assertEqual(self.page.locator('#levelf option[value="review"]').count(), 0)
        self.page.locator('#levelf').select_option('low')
        self.assertEqual(self.page.locator('#rows tr').count(), 1)
        self.assertIn('경계 · 제출 제외', self.page.locator('#rows').inner_text())
        self.assertNotIn('검토 후보', self.page.locator('#rows').inner_text())
        self.page.locator('#rows [data-go]').first.click()
        self.assertIn('제출용 위반 항목에서는 제외', self.page.locator('#detailview').inner_text())
        csv = self.page.request.get(self.base + '/api/export.csv').body().decode('utf-8-sig')
        self.assertIn('경계 · 제출 제외', csv)
        printed = self.page.request.get(self.base + '/api/report.html').text()
        self.assertIn('경계 · 제출 제외', printed)
        self.assertNotIn('검토 후보', printed)

    def test_evidence_left_off_is_explained_not_reported_as_failure(self):
        row = dict(finding(1), evidence_key='ev1')
        res = result([row])
        run = RunArchive(self.folder, TARGET, {"primary_only":True, "evidence":False, "snapshots":False})
        run.finish(res)
        res["run_id"] = run.id
        self.session.result, self.session.entry_url = res, TARGET
        self.session._sync_review()
        self.page.evaluate("load()")
        # 꺼 둔 추가 검사는 0건이어도 보지 않은 것이므로 결과 위에 검사 항목을 함께 적는다
        scope = self.page.locator('#checkscope').inner_text()
        self.assertIn('기본 4종', scope)
        self.assertIn("첨부파일·그림 속 글자", scope)
        self.page.locator('#rows [data-go]').first.click()
        detail = self.page.locator('#detailview')
        self.assertIn("고급 설정의 '검출 증거 사진 저장'을 켜고 점검해야 저장됩니다", detail.inner_text())
        self.assertNotIn('촬영하지 못했습니다', detail.inner_text())
        self.page.locator('#dpage summary').click()
        self.assertIn("'방문 페이지 사본 저장'을 켜고 점검해야 저장됩니다", self.page.locator('#dpage').inner_text())
        self.assertEqual(self.page.locator('#dpage iframe').count(), 0)

    def save_status(self, status):
        self.page.locator("#rows select").first.select_option(status)
        self.page.evaluate("pendingSave")

    def test_filter_saves_whole_ad_and_report_matches(self):
        self.install([finding(0), finding(0, "JAMO")])
        self.page.locator("#q").fill("카지노")
        self.save_status("fp")
        self.assertEqual(self.summary(), ["1건", "0건", "0건", "1건"])
        self.assertEqual(self.page.locator("#rows select").count(), 0)      # moved into the collapsed group
        self.page.locator("#restsum").click()
        self.page.locator('#restrows [data-go]').first.click()
        self.page.locator("#dmemo").fill("필터를 켜고 저장한 메모")
        self.page.wait_for_function("document.getElementById('snack').textContent === '메모를 저장했습니다.'")
        self.page.evaluate("pendingSave")
        # Check the server and a fresh Session, not just the optimistic DOM values.
        fresh = Session(str(self.folder)).payload()["findings"]
        self.assertEqual([f["status"] for f in fresh], ["fp", "fp"])
        self.assertEqual([f["memo"] for f in fresh], ["필터를 켜고 저장한 메모"] * 2)
        self.page.locator("#dback").click()
        self.page.locator("#clearf").click()
        self.assertEqual(self.page.locator("#rows select").input_value(), "fp")
        self.assertEqual(self.summary(), ["1건", "0건", "0건", "1건"])
        report = self.context.new_page()
        report.goto(self.base + "/api/report.html")
        self.assertEqual(report.locator(".tile b").all_text_contents(), ["1건", "1곳", "0건", "0건", "1건"])
        report.close()

    def test_url_search_keeps_shared_group_and_saves_all_pages(self):
        rows = [finding(0, url=TARGET + suffix) for suffix in ("shared-a", "shared-b", "other")]
        self.install(rows)
        self.page.locator("#q").fill("shared-")
        self.assertEqual(self.page.locator("#total").inner_text(), "전체 1건 중 1건 표시")
        self.assertEqual(self.page.locator("#rows tr").count(), 1)
        self.assertIn("3곳", self.page.locator("#rows").inner_text())
        self.save_status("fp")
        self.assertEqual([f["status"] for f in Session(str(self.folder)).payload()["findings"]], ["fp"] * 3)
        self.assertEqual(self.summary(), ["1건", "0건", "0건", "1건"])

    def test_active_filters_with_unchanged_count_can_be_reset(self):
        self.install([finding(0), finding(0, "JAMO")])
        for apply in (
            lambda:self.page.locator("#q").fill("카지노"),
            lambda:self.page.locator("#statusf").select_option("all"),
        ):
            apply()
            self.assertEqual(self.page.locator("#total").inner_text(), "전체 1건 중 1건 표시")
            self.assertTrue(self.page.locator("#clearf").is_visible())
            self.page.locator("#clearf").click()
            self.assertEqual(self.page.locator("#total").inner_text(), "총 1건")
            self.assertEqual(self.page.locator("#q").input_value(), "")
            self.assertEqual(self.page.locator("#statusf").input_value(), "open")   # 기본값: 미확인만
            self.assertTrue(self.page.locator("#clearf").is_hidden())
        self.page.locator("#q").fill("missing")
        self.assertEqual(self.page.locator("#total").inner_text(), "전체 1건 중 0건 표시")
        self.install([finding(1)])
        self.assertEqual(self.page.locator("#q").input_value(), "")
        self.assertEqual(self.page.locator("#total").inner_text(), "총 1건")

    def test_new_only_filter_also_applies_to_folded_reviewed_items(self):
        self.install([finding(0), finding(1), finding(2)])
        self.save_status("done")
        self.save_status("fp")
        self.page.evaluate("""() => {
            DATA.findings.forEach((f, i) => f.is_new = i > 0);
            render();
        }""")
        self.page.locator("#newonly").check()
        self.assertEqual(self.page.locator("#rows select").count(), 1)
        self.page.locator("#restsum").click()
        self.assertEqual(self.page.locator("#restrows select").count(), 1)
        self.assertEqual(self.page.locator("#restrows select").input_value(), "fp")
        self.page.locator("#clearf").click()
        self.assertFalse(self.page.locator("#newonly").is_checked())
        self.assertEqual(self.page.locator("#restrows select").count(), 0)
        self.page.locator("#restsum").click()
        self.assertEqual(self.page.locator("#restrows select").count(), 2)

    def test_default_filter_hides_finished_items_in_collapsed_group(self):
        self.install([finding(0), finding(1), finding(2)])
        self.assertEqual(self.page.locator("#statusf").input_value(), "open")
        self.assertEqual(self.page.locator("#total").inner_text(), "총 3건")
        self.assertTrue(self.page.locator("#clearf").is_hidden())
        self.assertTrue(self.page.locator("#restbox").is_hidden())
        self.save_status("fp")
        # The view the person chose (default) stays; the finished item moves below, collapsed.
        self.assertEqual(self.page.locator("#statusf").input_value(), "open")
        self.assertEqual(self.page.locator("#rows tr").count(), 2)
        self.assertEqual(self.page.locator("#total").inner_text(), "미확인 2건 · 전체 3건")
        self.assertTrue(self.page.locator("#clearf").is_hidden())
        self.assertTrue(self.page.locator("#restbox").is_visible())
        self.assertIn("오탐 처리 1건 · 확인 0건", self.page.locator("#restsum").inner_text())
        self.assertEqual(self.page.locator("#restrows tr").count(), 0)
        self.page.locator("#restsum").click()
        self.assertEqual(self.page.locator("#restrows tr").count(), 1)
        self.assertEqual(self.page.locator("#restrows td.num").inner_text(), "3")
        self.assertEqual(self.summary(), ["3건", "2건", "0건", "1건"])
        # Detail opens from the group and returns to the list with the group still expanded.
        self.page.locator("#restrows [data-go]").first.click()
        self.assertTrue(self.page.locator("#detailview").is_visible())
        self.assertEqual(self.page.locator('#detailview input[name="dst"]:checked').input_value(), "fp")
        self.page.locator("#dback").click()
        self.assertEqual(self.page.locator("#restrows tr").count(), 1)
        # Reverting the status in the group brings the item back to the main list.
        self.page.locator("#restrows select").select_option("open")
        self.page.evaluate("pendingSave")
        self.assertEqual(self.page.locator("#rows tr").count(), 3)
        self.assertTrue(self.page.locator("#restbox").is_hidden())
        self.assertEqual(self.page.locator("#total").inner_text(), "총 3건")
        # Marking false positive from the detail keeps the detail open instead of closing it.
        self.page.locator('#rows [data-go]').first.click()
        self.page.locator('#detailview input[name="dst"][value="fp"]').check()
        self.page.evaluate("pendingSave")
        self.assertTrue(self.page.locator("#detailview").is_visible())
        self.page.locator("#dback").click()
        self.assertEqual(self.page.locator("#rows tr").count(), 2)
        self.assertEqual(self.page.locator("#restrows tr").count(), 1)
        # Marking everything false positive leaves no open item: the empty note points at the group.
        for _ in range(2):
            self.page.locator("#rows select").first.select_option("fp")
            self.page.evaluate("pendingSave")
        self.assertEqual(self.page.locator("#rows select").count(), 0)
        self.assertIn("미확인 광고가 없습니다", self.page.locator("#rows").inner_text())
        self.assertEqual(self.page.locator("#restrows tr").count(), 3)
        # A new result whose items are all already judged opens on '전체' so the list is not empty.
        self.install([finding(0)])
        self.assertEqual(self.page.locator("#statusf").input_value(), "all")
        self.assertEqual(self.page.locator("#rows tr").count(), 1)
        self.assertEqual(self.page.locator("#rows select").input_value(), "fp")
        self.assertTrue(self.page.locator("#restbox").is_hidden())
        self.assertEqual(self.page.locator("#total").inner_text(), "총 1건")

    def scan_disconnect(self, endpoint):
        self.install([finding(0)])
        requests = []
        # Hold a request across multiple polling intervals to catch overlapping completion handlers.
        self.page.route("**" + endpoint, lambda route:requests.append(route))
        with self.page.expect_request("**" + endpoint):
            self.page.evaluate("startRunning('http://127.0.0.1:8774/')")
        self.page.wait_for_timeout(800)
        self.assertEqual(len(requests), 1)
        requests[0].abort("connectionrefused")
        self.page.wait_for_function("!document.getElementById('runlost').hidden")
        self.assertTrue(self.page.locator("#stop").is_disabled())
        self.assertEqual(self.page.locator("#running .prog i").evaluate("e=>getComputedStyle(e).animationName"), "none")
        self.assertIn("연결이 끊어졌습니다", self.page.locator("#runlost").inner_text())
        self.page.wait_for_timeout(600)
        self.assertEqual(len(requests), 1)

    def test_scan_status_disconnect_stops_polling(self):
        self.scan_disconnect("/api/status")

    def test_scan_result_disconnect_stops_polling(self):
        self.scan_disconnect("/api/result")

    def test_result_has_no_recheck_button(self):
        # 점검 결과 화면에서 [조치 확인] 단추와 그 도움말을 뺐다
        self.install([finding(0)])
        self.assertEqual(self.page.locator("#recheck").count(), 0)
        self.assertEqual(self.page.locator("#hrecheck").count(), 0)
        self.assertNotIn("조치 확인", self.page.locator("#topinfo").inner_text())
        self.assertTrue(self.page.locator("#again").is_enabled())
        # 도움말도 지금 화면(3단계, 미확인·확인·오탐 처리)에 맞춘다
        self.page.locator("#help").click()
        guide = self.page.locator("#guidebody").inner_text()
        self.assertEqual(self.page.locator("#guidebody .g-steps li").count(), 3)
        for word in ("미확인", "확인", "오탐 처리"):
            self.assertIn(word, guide)
        for gone in ("조치 확인", "미조치", "조치완료"):
            self.assertNotIn(gone, guide)

    def test_first_scan_cancel_returns_to_start_then_can_scan_again(self):
        def cancelled(*args, should_stop, **kwargs):
            deadline = time.monotonic() + 10
            while not should_stop() and time.monotonic() < deadline:
                time.sleep(.01)
            if not should_stop():
                raise RuntimeError("stop was not delivered")
            return result([], pages=[], stopped="user")
        with patch("ui.server.run_scan", side_effect=cancelled):
            self.page.locator("#url").fill(TARGET)
            self.page.locator("#go").click()
            self.page.wait_for_function("document.getElementById('app').dataset.stage === 'running'")
            self.page.locator("#stop").click()
            self.page.wait_for_function("document.getElementById('app').dataset.stage === 'start'")
        self.assertIn("결과는 저장하지 않았습니다", self.page.locator("#starterr").inner_text())
        self.assertFalse((self.folder / "last_result.json").exists())
        self.assertEqual(self.session.list_runs(), [])
        self.assertTrue(self.page.locator("#go").is_enabled())
        with patch("ui.server.run_scan", return_value=result([])):
            self.page.locator("#go").click()
            self.page.wait_for_function("document.getElementById('app').dataset.stage === 'result'")
        self.assertIsNone(self.session.notice)
        self.assertTrue((self.folder / "last_result.json").exists())
        for button in ("report", "csv", "run-history"):
            self.assertTrue(self.page.locator("#" + button).is_visible())


if __name__ == "__main__":
    unittest.main(verbosity=2)
