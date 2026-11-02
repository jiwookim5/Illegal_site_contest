"""Supervise a single scan with atomic checkpoints and bounded cancellation.

The GUI/CLI owns RunArchive. The child writes only its worker files and evidence;
no IPC queue can be left half-written when a stuck renderer is terminated.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from fileio import write_json
from owned_process import ProcessTree, join_job
from uuid import uuid4

CANCEL_GRACE = 5.0
POLL_SECONDS = 0.1
STAGE_LIMIT = 120.0
# 정체로 건너뛸 페이지 수의 상한. 넘으면 누리집 자체가 응답하지 않는 것으로 보고 끝낸다
MAX_STALL_SKIPS = 10

def read_json(path):
    # Windows may briefly deny opening a file during atomic replacement or AV inspection.
    for attempt in range(6):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def restore_dates(result):
    result = dict(result)
    for key in ("started", "finished"):
        if isinstance(result.get(key), str):
            result[key] = datetime.fromisoformat(result[key])
    return result

def worker_main(directory):
    from console import attach_to_parent
    attach_to_parent()
    from run_archive import serializable
    import lexicon
    from scan import scan
    directory = Path(directory)
    # The supervisor assigns the Windows job before allowing any browser launch.
    start = time.monotonic()
    while not (directory / "ready").exists():
        if time.monotonic() - start > 20:
            return 2
        time.sleep(0.05)
    config = read_json(directory / "config.json")
    join_job(config["job_name"])
    for name, words in config["rules"].items():
        getattr(lexicon, name)[:] = words
    lexicon.VERSION += 1
    state = {"stage": "starting", "current": config["url"], "pages_done": 0}
    def status(stage, url, **counts):
        state.update(stage=stage, current=url, updated_at=datetime.now(timezone.utc).isoformat(), **counts)
        write_json(directory / "status.json", state)
    def checkpoint(res):
        write_json(directory / "checkpoint.json", serializable(res, config["url"]))
    try:
        res = scan(config["url"], **config["options"],
                   should_stop=lambda: (directory / "stop").exists(),
                   checkpoint=checkpoint, status=status)
        write_json(directory / "result.json", serializable(res, config["url"]))
        return 0
    except BaseException as exc:
        detail = traceback.format_exc()
        print(detail, file=sys.stderr, flush=True)
        write_json(directory / "error.json", {"error": f"{type(exc).__name__}: {exc}", "traceback": detail})
        return 1

def _stuck_page(latest):
    """정체 직전 저장에서 열던 페이지 (페이지 사이의 일에서 멈췄으면 None)."""
    from resume_state import unpack
    state = (latest or {}).get("resume_state") or {}
    try:
        return unpack(state["data"]).get("current_url")
    except Exception:
        return None


def run_scan(url, archive, *, progress=None, should_stop=None, status=None, **options):
    """작업 프로세스로 점검한다. 한 페이지가 응답하지 않아 정체되면(STAGE_LIMIT) 그 프로세스를 끝내고,
    마지막 저장에서 새 프로세스로 이어 간다. 멈춘 페이지는 실패(stalled)로 적고 다시 열지 않는다.
    2026-10-20 교육부 누리집은 팝업 하나에서 멈춰 579쪽 만에 점검 전체가 끝났다."""
    directory = archive.path / "worker"
    directory.mkdir()
    rules = read_json(archive.path / "rules.json")
    begin = time.monotonic()
    time_limit = options.get("time_limit", 25 * 60)
    clock = getattr(archive, "clock", None)
    deadline = (clock.begin if clock else begin) + time_limit if time_limit else None
    skipped, first_pages, first_started = [], None, None
    attempt_options = dict(options)
    while True:
        res, latest = _run_worker(url, archive, directory, rules, attempt_options, deadline,
                                  progress, should_stop, status, append_log=bool(skipped))
        if latest and first_pages is None:
            first_pages, first_started = len(latest.get("pages") or []), latest.get("started")
        stuck = _stuck_page(latest) if res.get("stopped") == "stalled" and res.get("forced_stop") else None
        left = deadline - time.monotonic() if deadline else None
        if not stuck or stuck in skipped or len(skipped) >= MAX_STALL_SKIPS or (left is not None and left < 30):
            break
        skipped.append(stuck)
        attempt_options = dict(options, resume_state=latest["resume_state"], stalled_url=stuck)
        if left is not None:
            attempt_options["time_limit"] = left
        if options.get("max_pages") is not None:
            attempt_options["max_pages"] = max(1, options["max_pages"] - (len(latest.get("pages") or []) - first_pages))
        for name in ("status.json", "stop", "ready", "result.json", "error.json", "process.json"):
            (directory / name).unlink(missing_ok=True)
    if skipped:
        res["stall_skips"] = skipped
        if first_started:
            res["started"] = first_started
    res["process_elapsed"] = time.monotonic() - begin
    res["process_finished"] = datetime.now(timezone.utc).isoformat()
    return res


def _run_worker(url, archive, directory, rules, options, deadline, progress, should_stop, status, append_log=False):
    """작업 프로세스 하나를 돌린다. (결과, 마지막 중간 저장) 을 돌려준다."""
    job_name = "Local\\HwonhiScan-" + uuid4().hex
    write_json(directory / "config.json", {"url": url, "options": options, "rules": rules, "job_name": job_name})
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command += [str(Path(__file__).with_name("main.py"))]
    command += ["--scan-worker", str(directory)]
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    started = datetime.now(timezone.utc)
    begin = time.monotonic()
    latest = None
    last_status = None
    last_status_at = begin
    last_saved = None
    last_checkpoint = 0
    snapshot = directory / "checkpoint.json"
    # 앞 작업이 남긴 저장은 이미 기록에 넣었다. 새 작업이 쓴 것만 읽는다
    checkpoint_stamp = snapshot.stat().st_mtime_ns if snapshot.exists() else None
    cancel_at = None
    reason = None
    proc = tree = None
    try:
        with (directory / "worker.log").open("a" if append_log else "w", encoding="utf-8") as log:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **flags)
            tree = ProcessTree(proc, job_name)
            write_json(directory / "process.json", {"pid": proc.pid, "job_name": job_name, "started": started.isoformat()})
            (directory / "ready").touch()
            while True:
                now = time.monotonic()
                current = read_json(directory / "status.json")
                if current and current != last_status:
                    last_status = current
                    last_status_at = now
                    if status:
                        status(dict(current, last_saved=last_saved))
                    if progress:
                        progress(current.get("pages_done", 0), current.get("current", ""))
                snapshot = directory / "checkpoint.json"
                stamp = snapshot.stat().st_mtime_ns if snapshot.exists() else None
                if stamp is not None and stamp != checkpoint_stamp:
                    checkpoint_stamp = stamp
                    latest = restore_dates(read_json(snapshot))
                    if now - last_checkpoint >= 15 or not last_checkpoint:
                        archive.checkpoint(latest)
                        last_checkpoint = now
                        last_saved = datetime.now(timezone.utc).isoformat()
                        if status and current:
                            status(dict(current, last_saved=last_saved))
                if not reason:
                    if should_stop and should_stop():
                        reason = "user"
                    elif deadline and now >= deadline:
                        reason = "time"
                    elif not current and now - begin > 30:
                        reason = "stalled"
                    elif current and now - last_status_at > STAGE_LIMIT:
                        reason = "stalled"
                    if reason:
                        cancel_at = now
                        (directory / "stop").touch()
                if proc.poll() is not None:
                    break
                if cancel_at is not None and now - cancel_at >= CANCEL_GRACE:
                    tree.close()
                    proc.wait(timeout=5)
                    break
                try:
                    time.sleep(POLL_SECONDS)
                except KeyboardInterrupt:
                    reason, cancel_at = "user", time.monotonic()
                    (directory / "stop").touch()
            # Read once more after the writer has stopped, before sealing the archive.
            final = read_json(directory / "result.json")
            if final:
                res = restore_dates(final)
                if reason:
                    res["stopped"] = reason
            else:
                error = read_json(directory / "error.json")
                if error and not reason:
                    raise RuntimeError(error["error"] + f" (상세: {directory / 'worker.log'})")
                if not reason:
                    raise RuntimeError(f"점검 프로세스가 결과 없이 종료됐습니다 (exit={proc.returncode}). {directory / 'worker.log'}")
                saved = read_json(directory / "checkpoint.json")
                res = restore_dates(saved) if saved else {
                    "engine": "?", "started": started, "finished": started, "elapsed": 0,
                    "pages": [], "findings": [], "coverage": {"visited": 0, "analyzed": 0,
                    "failed": [], "failed_count": 0, "left": [url], "left_count": 1}}
                res["stopped"] = reason
                res["forced_stop"] = True
                res["incomplete_stage"] = last_status
            return res, latest
    finally:
        if tree:
            tree.close()
        elif proc and proc.poll() is None:
            proc.kill()
        if proc:
            proc.wait(timeout=5)
