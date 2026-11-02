"""Local HTTP/Edge checks for cancellation, worker ownership, and checkpoints."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import argparse
import os
import subprocess
from uuid import uuid4
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "detector"))
from run_archive import RunArchive, verify
from scan_worker import run_scan
from owned_process import ProcessTree

class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /"
        elif self.path == "/hang":
            body = b"<html><body>stuck<script>while(true){}</script></body></html>"
        else:
            body = '<html><body><div style="display:none">카지노 가입 보너스</div><a href="/hang">next</a></body></html>'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def check_owned_tree(out):
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    job = "Local\\HwonhiTest-" + uuid4().hex
    pidfile = out / "owned-processes.json"
    code = """import sys,time,subprocess,json,os
sys.path.insert(0,sys.argv[1])
from owned_process import join_job
sys.stdin.readline()
join_job(sys.argv[2])
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
open(sys.argv[3],'w').write(json.dumps({'worker':os.getpid(),'child':child.pid}))
time.sleep(60)
"""
    unrelated = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "import time;time.sleep(60)"], creationflags=subprocess.CREATE_NO_WINDOW)
    proc = subprocess.Popen([sys.executable, "-c", code, str(ROOT / "detector"), job, str(pidfile)],
                            stdin=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    tree = None
    try:
        tree = ProcessTree(proc, job)
        proc.stdin.write("\n"); proc.stdin.flush()
        end = time.monotonic() + 10
        while not pidfile.exists() and time.monotonic() < end: time.sleep(0.05)
        ids = json.loads(pidfile.read_text())
        tree.close(); proc.wait(timeout=5)
        k = ctypes.WinDLL("kernel32")
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        for pid in ids.values():
            handle = k.OpenProcess(0x1000, False, pid)
            if handle:
                value = wintypes.DWORD()
                try:
                    assert k.GetExitCodeProcess(handle, ctypes.byref(value)) and value.value != 259, (pid, value.value)
                finally: k.CloseHandle(handle)
        assert unrelated.poll() is None, "unrelated process was terminated"
    finally:
        if tree: tree.close()
        if proc.poll() is None: proc.kill()
        proc.wait(timeout=5)
        unrelated.terminate(); unrelated.wait(timeout=5)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    out = ROOT / "_regress" / ("scan-control-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    checks = []
    check_owned_tree(out)
    original_executable = sys.executable
    original_frozen = getattr(sys, "frozen", None)
    if args.exe:
        sys.executable = str(args.exe.resolve())
        sys.frozen = True
    try:
        for mode in ("user", "time", "complete"):
            options = {"max_pages": 1 if mode == "complete" else 10, "time_limit": 5 if mode == "time" else 30}
            archive = RunArchive(out / mode, base, options)
            state = {}
            def status(info): state.update(info)
            stop_requested = []
            def should_stop():
                stop = state.get("current", "").endswith("/hang")
                if stop and not stop_requested: stop_requested.append(time.monotonic())
                return stop
            start = time.monotonic()
            result = run_scan(base, archive, status=status,
                              should_stop=should_stop if mode == "user" else None,
                              **options)
            wall = time.monotonic() - start
            stop_latency = time.monotonic() - stop_requested[0] if stop_requested else None
            if stop_latency is not None: assert stop_latency < 7, stop_latency
            assert len(result["pages"]) >= 1, result
            assert result["coverage"]["analyzed"] >= 1, result
            assert result["findings"], result
            if mode != "complete":
                assert result["stopped"] == mode, result
                assert wall < 15, wall
            else:
                assert not result["stopped"], result
            archive.finish(result)
            assert verify(archive.path) == [], verify(archive.path)
            checks.append({"mode": mode, "seconds": round(wall, 3), "stop_latency_seconds": round(stop_latency, 3) if stop_latency is not None else None,
                           "pages": len(result["pages"]), "analyzed": result["coverage"]["analyzed"],
                           "stopped": result["stopped"], "forced": result.get("forced_stop", False)})
        (out / "summary.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        print(json.dumps(checks)); print(out)
    finally:
        sys.executable = original_executable
        if original_frozen is None:
            if hasattr(sys, "frozen"): del sys.frozen
        else: sys.frozen = original_frozen
        server.shutdown(); server.server_close()

if __name__ == "__main__": main()
