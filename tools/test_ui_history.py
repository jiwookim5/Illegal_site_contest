"""실제 headless Edge에서 두 번 점검하고 증거·이력·재시작 복원을 검사한다."""
from datetime import datetime
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "detector"))
from playwright.sync_api import sync_playwright
from run_archive import result_dir, verify
from scan import DEFAULT_MAX_PAGES, TIME_LIMIT_SEC
from ui.server import Handler, Session


def main():
    out = ROOT / "_regress" / ("ui-history-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
    out.mkdir(parents=True)
    os.environ["SITE"] = "testsite7"
    spec = importlib.util.spec_from_file_location("fixture_server", ROOT / "tools" / "serve.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    class QuietFixture(fixture.Handler):
        def log_message(self, *args):
            pass
    fixture_server = ThreadingHTTPServer(("127.0.0.1", 0), QuietFixture)
    class UIHandler(Handler):
        def log_message(self, *args):
            pass
    session = Session(str(out))
    UIHandler.session = session
    ui = ThreadingHTTPServer(("127.0.0.1", 0), UIHandler)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (fixture_server, ui)]
    for thread in threads:
        thread.start()
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda err: errors.append(str(err)))
            base = f"http://127.0.0.1:{ui.server_port}"
            target = f"http://127.0.0.1:{fixture_server.server_port}/gap/list"
            page.goto(base)
            assert page.locator("#maxp").input_value() == str(DEFAULT_MAX_PAGES) == "5000"
            for control in ('attach', 'reflect', 'capture', 'snapshots', 'extra-types'):
                assert not page.locator('#' + control).is_checked(), control
            page.locator('details summary').first.click()
            for control in ('attach', 'reflect', 'capture', 'snapshots', 'extra-types'):
                page.locator('#' + control).check()
            first_path = None
            for iteration in range(2):
                if iteration:
                    page.locator("#again").click()
                page.locator("#url").fill(target)
                page.locator("#go").click()
                page.locator("#body").wait_for(state="visible", timeout=90000)
                payload = page.request.get(base + "/api/result").json()
                assert not session.error, session.error
                assert not payload["meta"]["save_error"], payload["meta"]
                main_rows = [f for f in payload["findings"] if f["technique"] in
                             {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"}]
                assert len(main_rows) == 13, len(main_rows)
                path = result_dir(out, session.result)
                assert verify(path) == [], verify(path)
                options = json.loads((path / "run.json").read_text(encoding="utf-8"))["options"]
                assert options["max_pages"] == DEFAULT_MAX_PAGES
                assert options["attachments"] and options["search_reflect"]
                assert options["time_limit"] == TIME_LIMIT_SEC == 1500
                assert list((path / "evidence").glob("*.png")), "No evidence images"
                if first_path is None:
                    first_path = path
                    image_row = next(f for f in payload["findings"] if f["evidence_image"])
                    assert page.request.get(base + image_row["evidence_image"]).status == 200
                    snapshot_url = base + "/api/page?u=" + quote(image_row["url"], safe="")
                    assert page.request.get(snapshot_url).status == 200
                    response = page.request.post(base + "/api/review", data={
                        "key": image_row["key"], "status": "fp", "memo": "검토 이력 보존 확인"})
                    assert response.ok, response.text()
                else:
                    assert first_path != path
                    assert verify(first_path) == []
            page.screenshot(path=str(out / "results.png"), full_page=True)
            with page.expect_popup() as popup:
                page.locator("#run-history").click()
            history = popup.value
            history.wait_for_load_state()
            assert history.get_by_role("heading", name="점검·조치 이력", exact=True).is_visible()
            assert "검토 이력 보존 확인" in history.locator("body").inner_text()
            assert first_path.name in history.locator("body").inner_text()
            history.screenshot(path=str(out / "history.png"), full_page=True)
            # 저장 오류를 성공으로 표시하지 않는다. 서버 상태를 다시 읽어 화면도 복구한다.
            page.route("**/api/review", lambda route: route.fulfill(
                status=500, content_type="application/json", body='{"error":"disk full"}'))
            # 오탐 처리한 항목은 미조치 목록 아래 접힌 묶음에 있다. 펼쳐서 되돌려 본다
            page.locator("#restsum").click()
            page.locator("#restrows .manage select").first.select_option("open")
            page.locator("#askdlg").wait_for(state="visible")
            message = page.locator("#askmsg").inner_text()
            assert "저장하지 못했습니다" in message, message
            page.locator("#askok").click()
            page.wait_for_function("document.querySelector('#restrows .manage select').value === 'fp'")
            assert session.review[image_row["key"]]["status"] == "fp"
            assert not errors, errors
            browser.close()
        restarted = Session(str(out))
        assert restarted.result["run_id"] == session.result["run_id"]
        assert restarted.review == session.review
        summary = {"passed": True, "scans": 2, "main_findings_each": 13,
                   "run_count": len(list((out / "runs").glob("*/manifest.json"))),
                   "page_errors": errors, "restart_restored": True, "save_failure_restored": True}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary))
        print("UI evidence:", out)
    finally:
        session.stop_requested = True
        for server in (ui, fixture_server):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()


if __name__ == "__main__":
    main()
