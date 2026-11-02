"""오탐 제외: 실제 localhost 요청·Edge·SQLite·GUI 재점검. 외부 검색 API는 호출하지 않는다."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "detector"))
from playwright.sync_api import sync_playwright
from review_store import ReviewStore
from scan_exclusions import ExcludedNavigation, ScanExclusions, exclusion_key
from scan import scan
from recheck import recheck
from search_discovery import recheck as search_recheck
from ui.server import Handler, Session, finding_key
from ui.history import history_html

OUT = ROOT / "_regress" / ("scan-exclusions-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])


class Fixture(BaseHTTPRequestHandler):
    requests = []
    removed = set()        # 광고를 지운 글 번호. 지난 점검 대비 '사라짐' 비교 시험용

    def do_GET(self):
        self.requests.append(self.path)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/review?id=1")
            self.end_headers()
            return
        if self.path == "/":
            content = ('<a href="/review?id=1">첫 글</a><a href="/review?id=2">둘째 글</a>'
                       '<iframe src="/review?id=1"></iframe>')
        elif self.path == "/frame-redirect":
            content = '<iframe src="/redirect"></iframe>'
        elif self.path.startswith("/review") and self.path[-1] in self.removed:
            content = "<p>광고를 지운 글</p>"
        elif self.path.startswith("/review"):
            content = f'<p id="ad" style="opacity:0">카지노 가입 보너스 텔레그램 @test{self.path[-1]}</p>'
        else:
            content = "<p>일반 안내</p>"
        body = ("<!doctype html><meta charset=utf-8><title>로컬 시험</title>" + content).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class ExclusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True)
        cls.site = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        threading.Thread(target=cls.site.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.site.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.site.shutdown()
        cls.site.server_close()
        print("Evidence:", OUT)

    def setUp(self):
        self.out = OUT / self._testMethodName
        self.out.mkdir()
        Fixture.requests.clear()
        Fixture.removed.clear()

    def rules(self):
        return [dict(url=self.base + "/review?id=1", reason="원문 확인: 교육용 예시")]

    def test_exact_url_scope_and_invalid_input(self):
        rules = ScanExclusions([dict(url="https://Example.org:443/Board?id=1", reason="확인")])
        self.assertTrue(rules.contains("https://example.org/Board?id=1#part"))
        for url in ("http://example.org/Board?id=1", "https://example.org/board?id=1",
                    "https://example.org/Board?id=2", "https://sub.example.org/Board?id=1",
                    "https://example.org/Board/?id=1", "https://example.org/Board?id=1&x="):
            self.assertFalse(rules.contains(url), url)
        for url in ("file:///tmp/test", "https://a:bad/x", "https://user:pw@a/x", "https://a/\n"):
            with self.assertRaises(ValueError):
                exclusion_key(url)

    def test_store_persistence_audit_and_validation(self):
        store = ReviewStore(self.out)
        url = self.rules()[0]["url"]
        with self.assertRaises(ValueError):
            store.set_exclusion(url, " ", patches={"f": {"status": "fp"}})
        self.assertEqual(store.load(), {})
        store.set_exclusion(url, "<script>확인</script>", "run1", {"f": {"status": "fp"}})
        restored = ReviewStore(self.out)
        self.assertEqual(restored.exclusions()[0]["reason"], "<script>확인</script>")
        self.assertEqual(restored.load()["f"]["status"], "fp")
        history = history_html(self.out, restored, finding_key)
        self.assertNotIn("<script>확인</script>", history)
        self.assertIn("&lt;script&gt;", history)
        restored.set_exclusion(url, run_id="run2")
        self.assertEqual(restored.exclusions(), [])
        self.assertEqual(restored.load()["f"]["status"], "fp")
        events = restored.history("exclude:" + exclusion_key(url))
        self.assertEqual(len(events), 2)
        self.assertIsNone(events[0]["after"])

    def test_session_requires_confirmation_current_finding_and_reason(self):
        session = Session(str(self.out))
        f = dict(url=self.base + "/review?id=1", location="#ad", technique="TRANSPARENT",
                 evidence_text="카지노 가입 보너스", normalized="카지노 가입 보너스")
        session.result = {"findings": [f]}
        key = finding_key(f)
        body = dict(action="add", keys=[key], confirmed=True, reason="직접 확인")
        for change in ({"confirmed": False}, {"keys": ["unknown"]}, {"reason": None}, {"reason": " "}):
            with self.assertRaises(ValueError):
                session.set_exclusion(dict(body, **change))
            self.assertEqual(session.review_store.exclusions(), [])
        session.running = True
        with self.assertRaises(ValueError):
            session.set_exclusion(body)
        session.running = False
        session.set_exclusion(body)
        self.assertEqual(session.review[key]["status"], "fp")
        self.assertEqual(len(session.review_store.exclusions()), 1)

    def test_real_crawl_skips_page_iframe_and_preserves_other_query(self):
        result = scan(self.base + "/", max_pages=5, primary_only=True, excluded_urls=self.rules())
        self.assertNotIn("/review?id=1", Fixture.requests)
        self.assertIn("/review?id=2", Fixture.requests)
        self.assertTrue(any(f["url"].endswith("id=2") for f in result["findings"]))
        self.assertEqual(result["coverage"]["excluded_count"], 1)
        self.assertEqual(result["coverage"]["failed_count"], 0)
        self.assertEqual(result["coverage"]["left_count"], 0)
        (self.out / "coverage.json").write_text(json.dumps(result["coverage"], ensure_ascii=False, indent=2), encoding="utf-8")

    def test_excluded_entry_does_not_open_browser_or_request(self):
        result = scan(self.base + "/review?id=1", excluded_urls=self.rules())
        self.assertEqual(Fixture.requests, [])
        self.assertEqual(result["pages"], [])
        self.assertEqual(result["coverage"]["excluded_count"], 1)
        self.assertEqual(result["coverage"]["left_count"], 0)

    def test_excluded_entry_preserves_other_index_targets(self):
        result = scan(self.base + "/review?id=1", excluded_urls=self.rules(),
                      index_urls=[self.base + "/review?id=1", self.base + "/review?id=2"])
        self.assertNotIn("/review?id=1", Fixture.requests)
        self.assertIn("/review?id=2", Fixture.requests)
        self.assertEqual(result["index_checked"], 1)

    def test_cli_reads_same_output_folder_rules(self):
        store = ReviewStore(self.out)
        store.set_exclusion(self.base + "/review?id=1", "원문 확인")
        proc = subprocess.run([sys.executable, str(ROOT / "detector" / "main.py"), "--cli",
                               "--url", self.base + "/review?id=1", "--out", str(self.out)],
                              capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        result = json.loads((self.out / "last_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["coverage"]["excluded_count"], 1)
        self.assertEqual(result["pages"], [])
        self.assertEqual(Fixture.requests, [])

    def test_redirect_and_api_request_exclusions(self):
        result = scan(self.base + "/redirect", max_pages=2, excluded_urls=self.rules())
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["coverage"]["excluded_count"], 1)
        self.assertEqual(result["coverage"]["failed_count"], 0)
        browser_requests = list(Fixture.requests)
        Fixture.requests.clear()
        with sync_playwright() as pw:
            request = pw.request.new_context()
            try:
                wrapped = ScanExclusions(self.rules()).request(request)
                with self.assertRaises(ExcludedNavigation):
                    wrapped.get(self.base + "/redirect", max_redirects=5)
                with self.assertRaises(ExcludedNavigation):
                    wrapped.head(self.base + "/review?id=1")
                self.assertEqual(wrapped.get(self.base + "/review?id=2").status, 200)
                self.assertTrue(callable(wrapped.dispose))
            finally:
                request.dispose()
        self.assertEqual(Fixture.requests, ["/redirect", "/review?id=2"])
        (self.out / "requests.json").write_text(json.dumps(dict(browser=browser_requests, api=Fixture.requests)), encoding="utf-8")

    def test_redirected_iframe_is_not_analyzed_or_marked_gone(self):
        first = scan(self.base + "/frame-redirect", max_pages=1, primary_only=True)
        self.assertTrue(first["findings"])
        result = scan(self.base + "/frame-redirect", max_pages=1, primary_only=True, excluded_urls=self.rules())
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["coverage"]["excluded_count"], 1)
        checked = recheck(first["findings"], excluded_urls=self.rules())
        self.assertEqual(set(checked.values()), {"skipped"})
        session = Session(str(self.out))
        session.entry_url = self.base + "/frame-redirect"
        first["entry_url"] = session.entry_url
        self.assertEqual(session._history(first, result)["gone_count"], 0)

    def test_recheck_and_search_skip_registered_url(self):
        findings = [dict(url=self.base + "/review?id=1", technique="TRANSPARENT",
                         location="#ad", evidence_text="카지노 가입 보너스", normalized="카지노 가입 보너스")]
        self.assertEqual(recheck(findings, excluded_urls=self.rules()), {0: "skipped"})
        run = dict(target=f"127.0.0.1:{self.site.server_port}", subdomains=False, queries=[],
                   results=[dict(url=findings[0]["url"], sources=[])], notes=[], stopped=False, limit_reached=False)
        search_recheck(run, self.out, polite=False, progress=lambda _: None, excluded_urls=self.rules())
        self.assertEqual(run["results"][0]["status"], "점검 제외")
        self.assertIsNone(run["results"][0]["checked_at"])
        self.assertNotIn("/review?id=1", Fixture.requests)

    def test_gone_comparison_skips_only_pages_touched_by_exclusion(self):
        session = Session(str(self.out))
        session.entry_url = self.base + "/"
        first = scan(self.base + "/", max_pages=5, primary_only=True)
        first["entry_url"] = session.entry_url
        urls = {f["url"] for f in first["findings"]}
        self.assertTrue(any(u.endswith("id=2") for u in urls))
        self.assertTrue(any(u.rstrip("/").endswith(str(self.site.server_port)) for u in urls), urls)
        Fixture.removed.add("2")                      # 둘째 글의 광고를 지웠다
        second = scan(self.base + "/", max_pages=5, primary_only=True, excluded_urls=self.rules())
        self.assertEqual(second["coverage"]["excluded_count"], 1)
        self.assertEqual(second["coverage"]["excluded_pages"], [self.base + "/"])
        self.assertEqual(second["coverage"]["exclusion_rule_count"], 1)
        history = session._history(first, second)
        self.assertEqual(history["excluded_page_count"], 1)
        self.assertEqual(history["uncompared"], [])
        # 제외 주소(id=1)와 제외 iframe 이 있던 첫 화면의 광고는 '사라짐'이 아니다. 둘째 글의 광고만 사라졌다
        self.assertTrue(history["gone"])
        self.assertTrue(all(g["url"].endswith("id=2") for g in history["gone"]), history["gone"])
        self.assertEqual(history["gone_count"], len(history["gone"]))
        other = scan(self.base + "/", max_pages=5, primary_only=True,
                     excluded_urls=[dict(url="https://other.example/x", reason="다른 누리집")])
        self.assertEqual(other["coverage"]["exclusion_rule_count"], 0)
        self.assertEqual(other["coverage"]["excluded_count"], 0)
        (self.out / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_google_search_inspection_preserves_exclusions_and_publishes(self):
        from search_providers import collect_api
        from ui.search_job import SearchJob

        store = ReviewStore(self.out)
        store.set_exclusion(self.base + "/review?id=1", "직접 확인", patches={"reviewed": {"status": "fp"}})
        job = SearchJob(str(self.out))
        job.config = self.out
        (self.out / "search.env").write_text("SERPAPI_API_KEY=fake-test-key", encoding="utf-8")

        def collect(host, terms, engines, folder, keys, **kwargs):
            def fetch(*_):
                return {"search_metadata": {"status": "Success", "id": "local-fixture"},
                        "organic_results": [
                            {"link": self.base + f"/review?id={n}",
                             "title": "카지노 가입 보너스 텔레그램 @test123", "snippet": ""}
                            for n in (1, 2)]}
            return collect_api(host, terms, engines, folder, keys, fetch=fetch, **kwargs)

        with patch("search_assist.collect_api", side_effect=collect):
            self.assertTrue(job.start(dict(site=self.base, scope="host", terms="카지노",
                                           engines=["google"], pages=1, inspect=True)))
            job.thread.join(90)
        self.assertFalse(job.running)
        self.assertEqual(job.error, "")
        self.assertNotIn("/review?id=1", Fixture.requests)
        self.assertIn("/review?id=2", Fixture.requests)
        rows = {row["url"]: row for row in job.run["results"]}
        self.assertEqual(rows[self.base + "/review?id=1"]["status"], "점검 제외")
        self.assertIsNone(rows[self.base + "/review?id=1"]["checked_at"])
        self.assertTrue(rows[self.base + "/review?id=2"]["findings"])
        self.assertEqual(job.run["excluded_urls"], store.exclusions())
        self.assertEqual(ReviewStore(self.out).load()["reviewed"]["status"], "fp")
        submitted = json.loads((self.out / "result_extra.json").read_text(encoding="utf-8"))
        by_url = {f["url"]: f["extra_finding"] for f in submitted["findings"]}
        # 제외 주소는 원문을 열지 않는다. 검색에서 얻은 제목·요약과 실제 원문 탐지를 구분한다.
        self.assertTrue(by_url[self.base + "/review?id=1"].startswith("SEARCH_INDEXED_AD"))
        self.assertTrue(by_url[self.base + "/review?id=2"].startswith("SEARCH_LIVE_AD"))
        self.assertTrue(job.submission["merged"])

    def test_search_cli_default_review_dir_without_side_effects(self):
        folder = self.out / "search_results" / "fixture"
        folder.mkdir(parents=True)
        run = dict(target=f"127.0.0.1:{self.site.server_port}", subdomains=False, queries=[],
                   results=[dict(url=self.base + "/review?id=1", sources=[])], notes=[], stopped=False,
                   limit_reached=False)
        (folder / "results.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
        cwd = self.out / "elsewhere"
        cwd.mkdir()
        cmd = [sys.executable, str(ROOT / "detector" / "search_assist.py"), "--input", str(folder / "results.json")]
        env = dict(os.environ, PYTHONUTF8="1")
        proc = subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(cwd), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertFalse((cwd / "review.sqlite3").exists())
        self.assertFalse((self.out / "review.sqlite3").exists())
        self.assertTrue((self.out / "result_extra.json").exists())
        self.assertTrue((folder / "result_extra.json").exists())
        rows = json.loads((folder / "results.json").read_text(encoding="utf-8"))["results"]
        self.assertNotEqual(rows[0]["status"], "점검 제외")
        self.assertIn("/review?id=1", Fixture.requests)
        ReviewStore(self.out).set_exclusion(self.base + "/review?id=1", "원문 확인")
        Fixture.requests.clear()
        proc = subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(cwd), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("점검 제외 목록 1건 적용", proc.stdout.decode("utf-8", "replace"))
        rows = json.loads((folder / "results.json").read_text(encoding="utf-8"))["results"]
        self.assertEqual(rows[0]["status"], "점검 제외")
        self.assertNotIn("/review?id=1", Fixture.requests)

    def test_gui_register_restart_scan_and_remove(self):
        session = Session(str(self.out))
        session.entry_url = self.base + "/"
        initial = scan(self.base + "/review?id=1", max_pages=1, primary_only=True)
        self.assertTrue(initial["findings"])
        initial["entry_url"] = session.entry_url
        session.result = initial
        session._sync_review()
        key = finding_key(initial["findings"][0])
        # Old 'fp' state alone must never start skipping pages.
        session.save_review(key, {"status": "fp"})
        self.assertEqual(session.review_store.exclusions(), [])
        class UI(Handler):
            pass
        UI.session = session
        ui = ThreadingHTTPServer(("127.0.0.1", 0), UI)
        threading.Thread(target=ui.serve_forever, daemon=True).start()
        address = f"http://127.0.0.1:{ui.server_port}"
        errors = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 960})
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(address)
                page.evaluate("load()")
                page.locator("#rows [data-go]").first.click()
                page.locator("#dexadd").click()
                self.assertIn("확인 사유", page.locator("#dexerr").inner_text())
                page.locator("#dexreason").fill("원문 확인: 교육 자료의 예시")
                page.locator("#dexconfirmed").check()
                page.locator("#dexadd").click()
                page.wait_for_function("document.querySelector('#dexstate').textContent.includes('현재 제외 중')")
                page.screenshot(path=str(self.out / "registered.png"), full_page=True)
                self.assertEqual(len(ReviewStore(self.out).exclusions()), 1)
                # A restart and a new process-backed GUI scan share the same rules.
                restarted = Session(str(self.out))
                self.assertEqual(len(restarted.review_store.exclusions()), 1)
                UI.session = restarted
                Fixture.requests.clear()
                page.reload()
                page.locator("#url").fill(self.base + "/")
                page.locator("#go").click()
                page.locator("#body").wait_for(state="visible", timeout=60000)
                self.assertIsNone(restarted.error)
                self.assertNotIn("/review?id=1", Fixture.requests)
                self.assertIn("/review?id=2", Fixture.requests)
                self.assertEqual(restarted.result["coverage"]["excluded_count"], 1)
                run_meta = json.loads((self.out / "runs" / restarted.result["run_id"] / "run.json").read_text(encoding="utf-8"))
                self.assertEqual(len(run_meta["options"]["excluded_urls"]), 1)
                page.locator("#exclusionsbtn").click()
                page.locator("[data-remove-exclusion]").wait_for()
                page.screenshot(path=str(self.out / "manage.png"), full_page=True)
                page.locator("[data-remove-exclusion]").click()
                page.wait_for_function("document.querySelector('#exclusionslist').textContent.includes('제외한 주소가 없습니다')")
                self.assertEqual(ReviewStore(self.out).exclusions(), [])
                page.locator("#exclusionsdlg .dlg-close").click()
                page.locator("#again").click()
                page.locator("#url").fill(self.base + "/review?id=1")
                Fixture.requests.clear()
                page.locator("#go").click()
                page.locator("#body").wait_for(state="visible", timeout=60000)
                self.assertIsNone(restarted.error)
                self.assertIn("/review?id=1", Fixture.requests)
                self.assertTrue(restarted.result["findings"])
                self.assertEqual(errors, [])
                browser.close()
        finally:
            ui.shutdown()
            ui.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
