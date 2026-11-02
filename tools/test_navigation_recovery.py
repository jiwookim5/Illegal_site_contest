"""Local redirect/body/error regressions; never contacts a public site."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, os, subprocess, sys, threading, time
from datetime import datetime
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "detector"))
from run_archive import RunArchive, verify
from scan_worker import run_scan
class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        pages = {
            "/redirect": '<html><head><meta http-equiv="refresh" content="1;url=/target"></head><body>moving</body></html>',
            "/target": '<html><body><div style="display:none">카지노 가입 보너스</div></body></html>',
            "/frames": '<html><frameset cols="100%"><frame src="/target"></frameset></html>',
            "/empty": '<html><body><script>document.body.remove()</script></body></html>',
        }
        body = pages.get(self.path, "User-agent: *\nAllow: /").encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
def main():
    out=ROOT/"_regress"/("navigation-"+datetime.now().strftime("%Y%m%d-%H%M%S")); out.mkdir()
    server=ThreadingHTTPServer(("127.0.0.1",0),Fixture)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[]
    try:
        for case in ("redirect", "empty", "frames"):
            url=f"http://127.0.0.1:{server.server_port}/{case}"
            archive=RunArchive(out/case,url,{"max_pages":1,"time_limit":20})
            result=run_scan(url,archive,max_pages=1,time_limit=20)
            archive.finish(result); assert verify(archive.path)==[]
            if case=="redirect":
                assert result["findings"] and any(f["url"].endswith("/target") for f in result["findings"]), result
            elif case=="frames":
                assert result["findings"] and all("frame" in f["location"] for f in result["findings"]), result
                assert result["coverage"]["failed_count"]==0 and result["coverage"]["analyzed"]==1, result
            else:
                assert result["coverage"]["failed_count"] and result["coverage"]["analyzed"]==0, result
            checks.append({"case":case,"analyzed":result["coverage"]["analyzed"],"failed":result["coverage"]["failed_count"]})
        if len(sys.argv)>1:
            bad=out/"not-a-directory";bad.write_text("preserve me")
            proc=subprocess.run([sys.argv[1],"--cli","--url","http://127.0.0.1:1/","--out",str(bad)],capture_output=True,timeout=15,env=dict(os.environ,PYTHONIOENCODING="utf-8"),creationflags=subprocess.CREATE_NO_WINDOW)
            assert proc.returncode==1,proc.returncode
            try: error_text = proc.stderr.decode("utf-8")
            except UnicodeDecodeError: error_text = proc.stderr.decode("cp949")
            assert "실행 실패" in error_text, repr(proc.stderr)
            assert bad.read_text()=="preserve me"
            checks.append({"case":"packaged-startup-error","exit":proc.returncode})
    finally: server.shutdown();server.server_close()
    (out/"checks.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(checks,ensure_ascii=False));print(out)
if __name__=="__main__":main()
