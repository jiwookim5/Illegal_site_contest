"""Paired GUI API benchmark on identical local delayed-scroll advertisements."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import statistics
import threading
from urllib.parse import urlsplit
import regress

def run_gui(exe, url, out):
    """Measure real Start button click to the visible result panel in headless Edge."""
    import subprocess, time
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=False)
    port=regress._free_port()
    app=subprocess.Popen([str(exe),'--no-browser','--port',str(port),'--out',str(out)],
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for _ in range(150):
            try:regress._api(port,'/api/status');break
            except OSError:time.sleep(.2)
        else:raise RuntimeError('GUI startup timeout')
        with sync_playwright() as p:
            b=p.chromium.launch(channel='msedge',headless=True)
            page=b.new_page(viewport={'width':1440,'height':1000});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/');page.locator('#url').fill(url)
            start=time.perf_counter();page.locator('#go').click()
            page.locator('#body').wait_for(state='visible',timeout=120000)
            elapsed=time.perf_counter()-start
            assert not errors,errors
            st=regress._api(port,'/api/status');assert not st['running'] and not st.get('error'),st
            assert not regress._api(port,'/api/result')['meta'].get('save_error')
            page.screenshot(path=str(out/'completed.png'),full_page=True)
            b.close()
        return elapsed
    finally:
        try:regress._api(port,'/api/quit',{},timeout=5)
        except Exception:pass
        try:app.wait(timeout=15)
        except subprocess.TimeoutExpired:app.kill();app.wait()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        p=urlsplit(self.path)
        if p.path=='/robots.txt':
            data=b'User-agent: *\nAllow: /'
        elif p.path=='/':
            data=('<html><body>'+''.join(f'<a href="/page?id={i}">page {i}</a>' for i in range(1,5))+'</body></html>').encode()
        else:
            data=b"""<html><body><div style="height:2600px">Public notice</div><div id="tail">End</div>
<script>new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&!document.getElementById('hidden-ad'))
setTimeout(()=>{const p=document.createElement('p');p.id='hidden-ad';p.style.display='none';
p.textContent='AD_TEXT';document.body.append(p)},150)}).observe(document.getElementById('tail'));</script></body></html>""".replace(b'AD_TEXT','카지노 가입 보너스'.encode())
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(data)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--before',required=True);ap.add_argument('--after',required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--trials',type=int,default=3);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    rows=[]; expected=None
    try:
        for trial in range(args.trials):
            for label,exe in [('before',args.before),('after',args.after)]:
                out=args.output/f'{label}-{trial+1}'
                wall=run_gui(exe,f'http://127.0.0.1:{server.server_port}/',out)
                res=json.loads((out/'last_result.json').read_text(encoding='utf-8'))
                official=json.loads((out/'result.json').read_text(encoding='utf-8'))
                findings=sorted((r['url'],r['location'],r['technique'],r['evidence_text']) for r in official['findings'])
                assert len(findings)==4,findings
                if expected is None:expected=findings
                assert findings==expected,(expected,findings)
                assert not res.get('stopped') and not res['coverage']['left_count'] and not res['coverage']['failed_count']
                if label=='after':assert 0<=wall-res['elapsed']<1,(wall,res['elapsed'])
                rows.append(dict(version=label,trial=trial+1,gui_seconds=wall,recorded_seconds=res['elapsed'],
                                 engine_seconds=res.get('engine_elapsed',res['elapsed']),pages=len(res['pages']),correct=4))
                print(json.dumps(rows[-1]),flush=True)
        med={k:statistics.median(x['gui_seconds'] for x in rows if x['version']==k) for k in ('before','after')}
        result=dict(scenario='Local scroll + delayed hidden ads, default GUI, identical findings',runs=rows,
                    median_seconds=med,reduction_percent=100*(1-med['after']/med['before']))
        (args.output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
