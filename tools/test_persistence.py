"""실행 보존·조치 이력·출력 보호 회귀 검사 (외부 사이트에 접속하지 않음)."""
import csv
from datetime import datetime, timezone
import io
import json
import re
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
import lexicon
from csv_safe import csv_text
from fileio import write_json
from review_store import ReviewStore
from run_archive import RunArchive, result_dir, verify
from ui.server import Session, Handler, finding_key
from ui.history import history_html
from ui import report_html


def result():
    now = datetime.now(timezone.utc)
    return dict(started=now, finished=now, elapsed=0.1, pages=["http://localhost/"],
                findings=[], coverage={}, evidence={}, snapshots={})


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_two_runs_preserve_evidence_and_schema(self):
        first = RunArchive(self.root, "http://localhost/", {"max_pages": 1})
        (first.path / "evidence").mkdir()
        (first.path / "evidence" / "a.png").write_bytes(b"first")
        res = result()
        first.finish(res)
        before = {p.relative_to(first.path): p.read_bytes() for p in first.path.rglob("*") if p.is_file()}
        second = RunArchive(self.root, "http://localhost/", {"max_pages": 2})
        second.finish(result())
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(before, {p.relative_to(first.path): p.read_bytes() for p in first.path.rglob("*") if p.is_file()})
        self.assertEqual(verify(first.path), [])
        self.assertEqual(verify(second.path), [])
        self.assertEqual(set(json.loads((self.root / "result.json").read_text())), {"meta", "findings"})
        self.assertEqual(result_dir(self.root, res), first.path)
        self.assertEqual(json.loads((self.root / "last_result.json").read_text())["run_id"], second.id)

    def test_checkpoint_and_failure_do_not_replace_latest(self):
        (self.root / "result.json").write_text("previous", encoding="utf-8")
        run = RunArchive(self.root, "http://localhost/", {})
        run.checkpoint(result())
        run.fail(RuntimeError("browser lost"))
        self.assertEqual((self.root / "result.json").read_text(), "previous")
        self.assertEqual(verify(run.path), [])
        self.assertEqual(json.loads((run.path / "run.json").read_text())["status"], "failed")

    def test_legacy_results_are_archived_before_first_replacement(self):
        (self.root / "result.json").write_bytes(b"legacy-result")
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "old.png").write_bytes(b"legacy-image")
        run = RunArchive(self.root, "http://localhost/", {})
        run.finish(result())
        legacy = self.root / "runs" / "legacy-import"
        self.assertEqual((legacy / "result.json").read_bytes(), b"legacy-result")
        self.assertEqual((legacy / "evidence" / "old.png").read_bytes(), b"legacy-image")
        self.assertEqual(verify(legacy), [])

    def test_partial_run_is_not_completed(self):
        run = RunArchive(self.root, "http://localhost/", {})
        res = result()
        res["coverage"] = {"left_count": 2}
        run.finish(res)
        self.assertEqual(json.loads((run.path / "run.json").read_text())["status"], "partial")

    def test_settings_include_defaults_and_overrides(self):
        run = RunArchive(self.root, "http://localhost/", {"max_pages": 7})
        self.assertEqual(run.meta["options"]["max_pages"], 7)
        self.assertEqual(run.meta["options"]["time_limit"], 1500)
        self.assertTrue(run.meta["options"]["respect_robots"])
        self.assertNotIn("checkpoint", run.meta["options"])

    def test_missing_ocr_is_partial(self):
        run = RunArchive(self.root, "http://localhost/", {"ocr_images": True})
        run.finish(dict(result(), ocr_images={"unavailable": "Korean OCR missing"}))
        self.assertEqual(run.meta["status"], "partial")

    def test_rule_snapshot_survives_keyword_changes(self):
        run = RunArchive(self.root, "http://localhost/", {})
        original = (run.path / "rules.json").read_bytes()
        cat = lexicon.CATEGORIES[0][0]
        words = getattr(lexicon, cat)
        words.append("test-keyword")
        try:
            run.finish(result())
            self.assertEqual(original, (run.path / "rules.json").read_bytes())
            self.assertEqual(verify(run.path), [])
        finally:
            words.pop()

    def test_manifest_detects_changed_missing_and_added_files(self):
        run = RunArchive(self.root, "http://localhost/", {})
        run.finish(result())
        (run.path / "rules.json").write_text("changed")
        (run.path / "result.json").unlink()
        (run.path / "unexpected.txt").write_text("added")
        errors = verify(run.path)
        self.assertTrue(any(e.startswith("changed:") for e in errors))
        self.assertTrue(any(e.startswith("missing") for e in errors))
        self.assertTrue(any(e.startswith("unexpected:") for e in errors))

    def test_legacy_path_and_traversal(self):
        self.assertEqual(result_dir(self.root, {}), self.root)
        with self.assertRaises(ValueError):
            result_dir(self.root, {"run_id": "../../outside"})

    def test_review_migrates_once_preserving_original(self):
        legacy = self.root / "review_state.json"
        legacy.write_text('{"a":{"status":"fp","memo":"old"}}')
        store = ReviewStore(self.root)
        store.update({"a": {"status": "done", "memo": "new"}}, run_id="run-1")
        restarted = ReviewStore(self.root)
        self.assertEqual(restarted.load()["a"]["status"], "done")
        self.assertEqual(json.loads(legacy.read_text())["a"]["status"], "fp")
        events = restarted.history("a")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["before"]["memo"], "old")
        self.assertEqual(events[0]["after"]["memo"], "new")
        self.assertEqual(events[0]["run_id"], "run-1")

    def test_review_failure_rolls_back_state_and_history(self):
        store = ReviewStore(self.root)
        store.update({"a": {"status": "open"}})
        with store.connect() as db:
            db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'full'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            store.update({"a": {"status": "done"}, "b": {"memo": "new"}})
        self.assertEqual(store.load(), {"a": {"status": "open", "memo": ""}})
        self.assertEqual(len(store.history()), 1)

    def test_review_delete_and_noop(self):
        store = ReviewStore(self.root)
        store.update({"a": {"status": "fp"}})
        store.update({"a": {"status": "fp"}})
        self.assertEqual(len(store.history()), 1)
        store.update({}, drop=["a"])
        self.assertEqual(store.load(), {})
        self.assertIsNone(store.history()[0]["after"])

    def test_broken_legacy_fails_without_overwriting(self):
        path = self.root / "review_state.json"
        path.write_text("broken")
        with self.assertRaises(ValueError):
            ReviewStore(self.root)
        self.assertEqual(path.read_text(), "broken")
        path.write_text('{"a":{"status":"done"}}')
        self.assertEqual(ReviewStore(self.root).load()["a"]["status"], "done")

    def test_csv_formula_prefixes_and_normal_text(self):
        for raw in ("=1+1", " +SUM(A1)", "-1", "@cmd", "\ufeff=1", "\x00=1", "\tplain", "\nplain"):
            self.assertEqual(csv_text(raw), "'" + raw)
        for raw in ("일반 광고", "https://example.test/?x=1", "메모,줄\n둘째줄"):
            self.assertEqual(csv_text(raw), raw)

    def test_history_escapes_untrusted_content(self):
        store = ReviewStore(self.root)
        store.update({"<script>": {"memo": "<img onerror=alert(1)>"}})
        page = history_html(self.root, store)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;img", page)

    def test_history_names_items_by_ad_text(self):
        # 조치 변경 이력의 항목을 코드 대신 광고 문구로 보인다. 문구는 바깥 누리집에서 긁어 온 것이라 이스케이프한다
        rid = "20261013T000000000000Z-abcdef123456"
        ad = {"url": "http://localhost/board", "location": "span.x", "technique": "JAMO",
              "evidence_text": "<b>광고</b> 카지노", "normalized": "광고카지노"}
        (self.root / "runs" / rid).mkdir(parents=True)
        write_json(self.root / "runs" / rid / "last_result.json", {"findings": [ad]})
        store = ReviewStore(self.root)
        store.update({finding_key(ad): {"memo": "확인"}}, run_id=rid)
        store.update({"0123456789abcdef": {"memo": "옛 기록"}}, run_id=None)
        page = history_html(self.root, store, finding_key)
        self.assertIn("&lt;b&gt;광고&lt;/b&gt; 카지노", page)
        self.assertNotIn("<b>광고", page)
        self.assertIn("http://localhost/board", page)
        self.assertIn("0123456789abcdef", page)      # 문구를 못 찾은 옛 기록은 항목 코드로 남긴다

    def test_unfinished_run_opens_latest_worker_checkpoint_without_rewriting_evidence(self):
        from run_archive import serializable, sha256
        archive = RunArchive(self.root, "http://localhost/first", {})
        old = result()
        archive.checkpoint(old)
        latest = result()
        latest["pages"] = old["pages"] + ["http://localhost/second"]
        write_json(archive.path / "worker" / "checkpoint.json", serializable(latest, archive.entry_url))
        before = {str(p): sha256(p) for p in archive.path.rglob("*") if p.is_file()}
        session = Session(str(self.root))
        self.assertEqual(session.list_runs()[0]["page_count"], len(latest["pages"]))
        self.assertIsNone(session.open_run(archive.id))
        self.assertEqual(session.result["stopped"], "interrupted")
        self.assertEqual(session.result["pages"], latest["pages"])
        self.assertEqual(before, {str(p): sha256(p) for p in archive.path.rglob("*") if p.is_file()})

    def test_session_runs_and_restart_preserve_images(self):
        session = Session(str(self.root))

        def fake_scan(url, archive, **kw):
            path = Path(kw["evidence_dir"])
            path.mkdir()
            (path / "proof.png").write_bytes(url.encode())
            return result()

        with patch("ui.server.run_scan", side_effect=fake_scan):
            session.entry_url = "http://localhost/first"
            session._run(session.entry_url, 1, capture=True)
            first_path = result_dir(self.root, session.result)
            session.prev_result = dict(session.result, entry_url=session.entry_url)
            session.entry_url = "http://localhost/second"
            session._run(session.entry_url, 1, capture=True)
        self.assertIsNone(session.error)
        second_path = result_dir(self.root, session.result)
        self.assertNotEqual(first_path, second_path)
        self.assertEqual((first_path / "evidence" / "proof.png").read_bytes(), b"http://localhost/first")
        restarted = Session(str(self.root))
        self.assertEqual(result_dir(self.root, restarted.result), second_path)
        self.assertEqual(verify(first_path), [])
        self.assertEqual(verify(second_path), [])

    def test_session_failure_restores_previous_and_keeps_failed_run(self):
        session = Session(str(self.root))
        session.entry_url = "http://localhost/previous"
        with patch("ui.server.run_scan", return_value=result()):
            session._run(session.entry_url, 1)
        original = (self.root / "result.json").read_bytes()
        previous = dict(session.result, entry_url=session.entry_url)
        session.prev_result = previous
        with patch("ui.server.run_scan", side_effect=RuntimeError("browser lost")):
            session._run("http://localhost/next", 1)
        self.assertEqual(session.result, previous)
        self.assertEqual(original, (self.root / "result.json").read_bytes())
        statuses = [json.loads(p.read_text())["status"] for p in (self.root / "runs").glob("*/run.json")]
        self.assertCountEqual(statuses, ["completed", "failed"])

    def test_saved_runs_open_and_delete_preserve_other_run_and_review_history(self):
        session = Session(str(self.root))
        with patch("ui.server.run_scan", return_value=result()):
            session.entry_url = "http://localhost/first"
            session._run(session.entry_url, 1)
            first = result_dir(self.root, session.result)
            session.entry_url = "http://localhost/second"
            session._run(session.entry_url, 1)
            second = result_dir(self.root, session.result)
        session.review_store.update({"item": {"memo": "keep history"}}, run_id=second.name)
        history = session.review_store.history()
        published = (self.root / "last_result.json").read_bytes()
        self.assertEqual(len(session.list_runs()), 2)
        self.assertIsNone(session.open_run(first.name))
        self.assertEqual(session.result["run_id"], first.name)
        self.assertEqual((self.root / "last_result.json").read_bytes(), published)
        self.assertIsNone(session.delete_run(second.name))
        self.assertFalse(second.exists())
        self.assertTrue(first.exists())
        self.assertEqual(verify(first), [])
        self.assertEqual(json.loads((self.root / "last_result.json").read_text(encoding="utf-8"))["run_id"], first.name)
        self.assertEqual(session.review_store.history(), history)
        self.assertIsNone(session.delete_run(first.name))
        self.assertIsNone(session.result)
        self.assertEqual(session.list_runs(), [])
        for name in ("last_result.json", "result.json", "result_extra.json"):
            self.assertFalse((self.root / name).exists())
        self.assertEqual(session.review_store.history(), history)

    def test_search_blocks_saved_run_mutation_and_other_scans(self):
        session = Session(str(self.root))
        with patch("ui.server.run_scan", return_value=result()):
            session.entry_url = "http://localhost/first"
            session._run(session.entry_url, 1)
        saved = result_dir(self.root, session.result)
        before = (self.root / "last_result.json").read_bytes()
        session.search.running = True
        self.assertIsNotNone(session.open_run(saved.name))
        self.assertIsNotNone(session.delete_run(saved.name))
        self.assertFalse(session.start("http://localhost/new", 1))
        self.assertFalse(session.start_recheck())
        self.assertTrue(saved.exists())
        self.assertEqual((self.root / "last_result.json").read_bytes(), before)

    def test_invalid_run_id_cannot_delete_output_root(self):
        session = Session(str(self.root))
        marker = self.root / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        for run_id in ("", "..", "../other", str(self.root)):
            with self.assertRaises(ValueError):
                session.delete_run(run_id)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_cancel_before_first_page_keeps_previous(self):
        session = Session(str(self.root))
        session.entry_url = "http://localhost/previous"
        with patch("ui.server.run_scan", return_value=result()):
            session._run(session.entry_url, 1)
        previous = dict(session.result, entry_url=session.entry_url)
        published = (self.root / "last_result.json").read_bytes()
        session.prev_result = previous
        cancelled = dict(result(), stopped="user", pages=[])
        with patch("ui.server.run_scan", return_value=cancelled):
            session._run("http://localhost/next", 1)
        self.assertEqual(session.result, previous)
        self.assertIsNone(session.error)
        self.assertIn("결과는 저장하지 않았습니다", session.notice)
        self.assertEqual((self.root / "last_result.json").read_bytes(), published)

    def test_cancel_first_run_does_not_publish_empty_result(self):
        session = Session(str(self.root))
        cancelled = dict(result(), stopped="user", pages=[])
        with patch("ui.server.run_scan", return_value=cancelled):
            session._run("http://localhost/first", 1)
        self.assertIsNone(session.result)
        self.assertIsNone(session.error)
        self.assertIn("결과는 저장하지 않았습니다", session.notice)
        self.assertNotIn("지난 점검 결과", session.notice)
        self.assertEqual(session.list_runs(), [])
        for name in ("last_result.json", "result.json", "result_extra.json"):
            self.assertFalse((self.root / name).exists(), name)
        archives = list((self.root / "runs").iterdir())
        self.assertEqual(len(archives), 1)
        self.assertEqual(json.loads((archives[0] / "run.json").read_text())["status"], "cancelled")
        self.assertEqual(verify(archives[0]), [])

    def test_report_counts_mixed_status_ads_once(self):
        # Legacy records may have different statuses for techniques on one ad or pages in a shared group.
        base = dict(location="#ad", evidence_text="광고", normalized="광고", reason="test", keywords=[])
        rows = [dict(base, url="http://localhost/one", technique=t, status=s)
                for t, s in (("TRANSPARENT", "fp"), ("JAMO", "open"))]
        rows += [dict(base, location="#shared", url=f"http://localhost/{i}",
                      technique="OFFSCREEN", status=s) for i, s in enumerate(("fp", "done", "fp"))]
        rows.append(dict(base, url="http://localhost/fp", technique="TRANSPARENT", status="fp"))
        for i, row in enumerate(rows):
            row["id"] = str(i)
        document = report_html.build({"meta":{"entry_url":"http://localhost/", "page_count":5}, "findings":rows})
        tiles = dict(re.findall(r'<span>([^<]+)</span><b>(\d+)', document))
        self.assertEqual(tiles["찾은 광고"], "3")
        self.assertEqual([tiles[k] for k in ("미확인", "확인", "오탐 처리")], ["1", "1", "1"])
        self.assertEqual(report_html.ad_count(rows), 3)

    def test_http_serves_run_image_and_protects_csv(self):
        session = Session(str(self.root))
        run = RunArchive(self.root, "http://localhost/", {})
        (run.path / "evidence").mkdir()
        (run.path / "evidence" / "a.png").write_bytes(b"run-image")
        res = result()
        res["findings"] = [dict(url="http://localhost/", location="#x", technique="TRANSPARENT",
                                evidence_text="=1+1", normalized="=1+1", reason="test", keywords=[])]
        run.finish(res)
        session.result = res
        class TestHandler(Handler):
            def log_message(self, *args):
                pass
        TestHandler.session = session
        server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/api/evidence/a.png") as response:
                self.assertEqual(response.read(), b"run-image")
            with urlopen(base + "/api/export.csv") as response:
                rows = list(csv.reader(io.StringIO(response.read().decode("utf-8-sig"))))
                self.assertEqual(rows[1][5], "'=1+1")
            with urlopen(base + "/api/history.html") as response:
                self.assertIn(run.id, response.read().decode())
            self.assertEqual(session.result["findings"][0]["evidence_text"], "=1+1")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
