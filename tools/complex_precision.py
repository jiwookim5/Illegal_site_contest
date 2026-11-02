"""고정 복합 개발 자료를 소스 CLI 또는 EXE CLI로 실행하고 DOM 정답과 대조한다.

python tools/complex_precision.py --output _regress/complex-new
python tools/complex_precision.py --exe dist/훤히/훤히.exe --output _regress/complex-exe-new
--viewport WIDTH HEIGHT is a source-only test override, not a product CLI option.
"""
import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'tools/fixtures/complex_precision'
sys.path.insert(0, str(ROOT / 'detector'))
from run_archive import verify
from playwright.sync_api import sync_playwright


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fingerprint():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in (ROOT / 'detector', CORPUS) for p in sorted(folder.rglob('*'))
            if p.is_file() and p.suffix in {'.py', '.js', '.html', '.css', '.json', '.txt'}}


def resolve(page, location):
    # Frame separators outside quoted CSS attribute values only.
    parts = re.split(r' >>> (?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', location)
    frame = page.main_frame
    for index, selector in enumerate(parts):
        elements = frame.query_selector_all(selector)
        if not elements:
            match = re.fullmatch(r'iframe\[src=("(?:\\.|[^"\\])*")\]', selector)
            if match:
                url = json.loads(match[1])
                elements = [el for el in frame.query_selector_all('iframe')
                            if el.evaluate('(e,url)=>e.src===url', url)]
        if len(elements) != 1:
            raise ValueError('Non-unique location: ' + selector)
        if index == len(parts) - 1:
            return elements[0]
        frame = elements[0].content_frame()
        if frame is None:
            raise ValueError('Missing frame: ' + selector)


def prepare(page, url):
    page.goto(url, wait_until='networkidle', timeout=15000)
    if urlsplit(url).path == '/dynamic.html':
        page.locator('#more').click()
        page.locator('#n-fetch-prevention').wait_for(state='attached')
        page.locator('#n-delayed').wait_for(state='attached')


def oracle_check(page, base, oracle):
    cases = oracle['negatives'] + oracle['positives']
    assert len({c['id'] for c in cases}) == len(cases)
    checked = []
    for path in oracle['pages']:
        prepare(page, base + path)
        for case in (c for c in cases if c['page'] == path):
            element = resolve(page, case['target'])
            text = element.get_attribute(case['source']) if case.get('source') else element.text_content()
            assert case['text'] in (text or ''), case['id']
            if 'TRANSPARENT' in case.get('techniques', []):
                assert element.evaluate('(e)=>parseFloat(getComputedStyle(e).opacity)===0'), case['id']
            if 'OFFSCREEN' in case.get('techniques', []):
                assert element.evaluate('(e)=>e.getBoundingClientRect().right<0'), case['id']
            checked.append(case['id'])
    return {'checked': len(checked), 'expected': len(cases), 'ids': checked}


def assess(page, base, output, oracle):
    result = json.loads((output / 'last_result.json').read_text(encoding='utf-8'))
    archive = output / 'runs' / result['run_id']
    assert not verify(archive), verify(archive)
    meta = json.loads((archive / 'run.json').read_text(encoding='utf-8'))
    cases = oracle['negatives'] + oracle['positives']
    benign = {c['page'] for c in oracle['negatives']}
    expected = {('official', c['id'], code) for c in oracle['positives'] for code in c['techniques']}
    # These two extra controls are visible ads in Hwonhi's existing output vocabulary.
    # Preserve the original oracle unchanged and publish the mapping explicitly.
    expected |= {('extra', c['id'], 'VISIBLE_AD(게시판 노출 광고)')
                 for c in oracle['positives'] if c.get('extras')}
    matched, findings, loaded = set(), [], None
    for group, filename, field in (('official', 'result.json', 'technique'), ('extra', 'result_extra.json', 'extra_finding')):
        data = json.loads((output / filename).read_text(encoding='utf-8'))
        assert data == json.loads((archive / filename).read_text(encoding='utf-8'))
        for row in data['findings']:
            path = urlsplit(row['url']).path
            assert path in oracle['pages'], path
            if path != loaded:
                prepare(page, base + path)
                loaded = path
            actual, case_id, error = None, None, None
            try:
                actual = resolve(page, row['location'])
                for case in (c for c in cases if c['page'] == path):
                    target = resolve(page, case['target'])
                    if actual.owner_frame() == target.owner_frame() and actual.evaluate('(a,b)=>a===b', target):
                        case_id = case['id']
                        break
            except Exception as exc:
                error = str(exc)
            matched.add((group, case_id, row[field]))
            findings.append({'group': group, 'page': path, 'case_id': case_id, 'code': row[field],
                             'location': row['location'], 'evidence_text': row['evidence_text'],
                             'false_positive': path in benign, 'location_error': error})
    visited = {urlsplit(url).path for url in result['pages']}
    return {'status': meta['status'], 'pages': len(visited), 'coverage': result.get('coverage'),
            'archive_verified': True, 'source_sha256': meta['source_sha256'], 'options': meta['options'],
            'unvisited_oracle_pages': sorted(set(oracle['pages']) - visited),
            'official_false_positives': sum(r['false_positive'] and r['group'] == 'official' for r in findings),
            'extra_false_positives': sum(r['false_positive'] and r['group'] == 'extra' for r in findings),
            'negative_controls': len(oracle['negatives']),
            'positive_expected': len(expected), 'positive_matched': len(expected & matched),
            'positive_missing': sorted(expected - matched), 'positive_type_mapping': sorted(expected),
            'location_errors': [r for r in findings if r['location_error']], 'findings': findings}


def measure(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    initial = fingerprint()
    save(output / 'input-sha256.json', initial)
    oracle = json.loads((CORPUS / 'oracle.json').read_text(encoding='utf-8'))
    save(output / 'oracle-snapshot.json', oracle)
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(CORPUS / 'site')))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    viewport = dict(zip(('width', 'height'), args.viewport or (1280, 720)))
    report = {'source': oracle['source'], 'viewport': viewport, 'viewport_override': bool(args.viewport)}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                report['oracle_check'] = oracle_check(browser.new_page(viewport=viewport), base, oracle)
            finally:
                browser.close()
        if args.exe:
            command = [str(args.exe.resolve())]
        elif args.viewport:
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--source-child', *map(str, args.viewport)]
        else:
            command = [sys.executable, '-B', str(ROOT / 'detector/main.py')]
        command += ['--cli', '--url', base + '/', '--out', str(output)]
        report['command'] = command
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        for name in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'):
            env.pop(name, None)
        env['PATH'] = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep)
                                   if 'python' not in p.lower() and 'venv' not in p.lower())
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        started = time.perf_counter()
        with (output / 'stdout.log').open('w', encoding='utf-8') as out, (output / 'stderr.log').open('w', encoding='utf-8') as err:
            process = subprocess.Popen(command, cwd=output, env=env, stdout=out, stderr=err,
                                       startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                report['exit_code'] = process.wait(timeout=180)
            finally:
                if process.poll() is None:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        report['wall_seconds'] = round(time.perf_counter() - started, 3)
        assert report['exit_code'] == 0, (output / 'stderr.log').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                report.update(assess(browser.new_page(viewport=viewport), base, output, oracle))
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
        report['inputs_unchanged'] = initial == fingerprint()
        save(output / 'assessment.json', report)
    print(json.dumps({key: report[key] for key in ('pages', 'official_false_positives', 'extra_false_positives',
          'positive_expected', 'positive_matched', 'positive_missing', 'inputs_unchanged')}, ensure_ascii=False))
    assert report['inputs_unchanged'] and report['oracle_check']['checked'] == 57
    assert not report['unvisited_oracle_pages'] and not report['location_errors']
    assert not report['coverage']['failed_count']
    assert report['official_false_positives'] == report['extra_false_positives'] == 0
    assert report['positive_matched'] == report['positive_expected'] == 6


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--source-child':
        width, height = map(int, sys.argv[2:4])
        import session
        original = session.BrowserSession._open_page
        def open_page(self):
            page = original(self)
            page.set_viewport_size({'width': width, 'height': height})
            return page
        session.BrowserSession._open_page = open_page
        sys.argv = [str(ROOT / 'detector/main.py'), *sys.argv[4:]]
        runpy.run_path(str(ROOT / 'detector/main.py'), run_name='__main__')
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--output', type=Path, required=True)
        parser.add_argument('--exe', type=Path)
        parser.add_argument('--viewport', type=int, nargs=2)
        args = parser.parse_args()
        if args.exe and args.viewport:
            parser.error('--viewport is a source-only test override')
        measure(args)
