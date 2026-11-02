"""Compare the original and current session on the same held-AJAX local page."""
import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'detector'))
from playwright.sync_api import sync_playwright
from session import BrowserSession
from findings import walk_frame
HTML='''<html><body><button onclick="this.remove();fetch('/hold');setTimeout(()=>{let p=document.createElement('p');p.id='ad';p.style.display='none';p.textContent='카지노 가입 보너스';document.body.append(p)},300)">댓글 더보기</button></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/hold':time.sleep(45)
        data=HTML.encode() if self.path!='/hold' else b'ok'
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers()
        try:self.wfile.write(data)
        except OSError:pass

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    source=subprocess.check_output(['git','-C',str(ROOT),'show',args.baseline+':detector/session.py'])
    baseline=args.output/'baseline_session.py';baseline.write_bytes(source)
    spec=importlib.util.spec_from_file_location('baseline_session',baseline)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    rows=[]
    try:
        with sync_playwright() as pw:
            for label,cls in [('baseline',old.BrowserSession),('updated',BrowserSession)]:
                for trial in range(3):
                    session=cls(pw)
                    try:
                        start=time.perf_counter()
                        session.open(f'http://127.0.0.1:{server.server_port}/')
                        session.page.evaluate("document.querySelector('button').click()")
                        session.react()
                        findings=[];walk_frame(session.page.main_frame,'',session.page.url,findings,set())
                        elapsed=time.perf_counter()-start
                        assert len(findings)==1 and findings[0]['technique']=='OFFSCREEN', findings
                        assert session.page.query_selector(findings[0]['location']).get_attribute('id')=='ad'
                        rows.append({'version':label,'trial':trial+1,'seconds':elapsed,'findings':len(findings)})
                        print(json.dumps(rows[-1]),flush=True)
                    finally:session.close()
        med={label:statistics.median(x['seconds'] for x in rows if x['version']==label) for label in ('baseline','updated')}
        result={'baseline_ref':args.baseline,'scenario':'held AJAX after more button; delayed hidden ad retained','runs':rows,'median_seconds':med,'reduction_percent':100*(1-med['updated']/med['baseline'])}
        (args.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
