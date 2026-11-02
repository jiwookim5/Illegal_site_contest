"""시험 사이트 전체 회귀 점검. 소스(또는 지정한 exe)로 모든 시험 사이트를 돌리고 채점한다.

    .venv\\Scripts\\python tools\\regress.py                 소스로 전체 실행
    .venv\\Scripts\\python tools\\regress.py --exe dist\\훤히\\훤히.exe
    .venv\\Scripts\\python tools\\regress.py --only testsite7 testsite12
    .venv\\Scripts\\python tools\\regress.py --save-baseline 지금 결과를 기준으로 저장
    .venv\\Scripts\\python tools\\regress.py --ui --exe 훤히.exe   심사위원처럼 화면 모드로 실행

각 사이트마다
  - result.json 을 tools/score.py 로 채점 (주요 4종 정답셋이 있는 사이트)
  - result_extra.json 의 (url, location, extra_finding) 집합을 기준과 비교
  - 시험 서버가 받은 POST(삭제·등록 등) 기록이 없는지 확인
결과 폴더는 _regress/<사이트>/ 이다.
"""
import argparse
import json
import os
import re
from datetime import datetime
from uuid import uuid4
import subprocess
import sys
import time
import urllib.request

import schema_check            # 같은 tools 폴더. 결과 파일 스키마(요강 붙임4)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_regress")
BASELINE = os.path.join(OUT, "baseline.json")
PY = sys.executable

# (이름, 사이트 폴더, 포트, 진입 주소, 추가 옵션)
RUNS = [
    ("testsite", "testsite", 8765, "http://127.0.0.1:8765/board/list", []),
    ("testsite2", "testsite2", 8766, "http://127.0.0.1:8766/notice/index", []),
    ("testsite3", "testsite3", 8767, "http://127.0.0.1:8767/portal/list", []),
    ("testsite4", "testsite4", 8768, "http://127.0.0.1:8768/www/main", []),
    ("testsite5", "testsite5", 8769, "http://127.0.0.1:8769/bbs/list", ["--attachments"]),
    ("testsite6", "testsite6", 8770, "http://127.0.0.1:8770/main",
     ["--search-reflect", "--index-csv", os.path.join(ROOT, "testsite6", "searchconsole_pages.csv")]),
    ("testsite7", "testsite7", 8771, "http://127.0.0.1:8771/gap/list", []),
    ("testsite8", "testsite8", 8772, "http://127.0.0.1:8772/egov/main.do", []),
    ("testsite9", "testsite9", 8773, "http://127.0.0.1:8773/free/list", []),
    ("testsite10", "testsite10", 8774, "http://127.0.0.1:8774/visit/list", []),
    ("testsite11", "testsite11", 8775, "http://www.demo.localhost:8775/main", []),
    ("testsite11-sub", "testsite11", 8775, "http://www.demo.localhost:8775/main", ["--subdomains"]),
    ("testsite12", "testsite12", 8776, "http://127.0.0.1:8776/egov/list.do", []),
    ("testsite13", "testsite13", 8777, "http://127.0.0.1:8777/site/main", []),
    # 8778 은 기관 누리집, 8779~8785 는 그 누리집이 링크한 바깥 누리집 흉내
    ("testsite14", "testsite14", tuple(range(8778, 8786)), "http://127.0.0.1:8778/main",
     ["--check-links"]),
    ("testsite14-off", "testsite14", tuple(range(8778, 8786)), "http://127.0.0.1:8778/main", []),
    ("testsite15", "testsite15", 8786, "http://127.0.0.1:8786/late/list", []),
    # 그림 속 글자 인식. Windows 한국어 글자 인식이 없는 환경에서는 건너뛴다
    ("testsite16", "testsite16", 8787, "http://127.0.0.1:8787/ocr/list", ["--attachments", "--ocr-images"]),
]


def ocr_ok():
    sys.path.insert(0, os.path.join(ROOT, "detector"))
    try:
        import ocr
        return ocr.available()
    except Exception:
        return False


def start_server(site, port):
    ports = port if isinstance(port, tuple) else (port,)
    port = ports[0]
    env = dict(os.environ, SITE=site)
    for name in ("_posted.log", "_ext_get.log"):
        log = os.path.join(ROOT, site, name)
        if os.path.exists(log):
            os.remove(log)
    proc = subprocess.Popen([PY, os.path.join(ROOT, "tools", "serve.py"), *map(str, ports)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/__ping__", timeout=1)
        except urllib.error.HTTPError:
            break               # 404 라도 응답이 오면 떠 있다
        except Exception:
            time.sleep(0.1)
            continue
        break
    return proc


def _free_port():
    """빈 포트. 방금 닫은 포트는 잠시 다시 못 쓰고, 그러면 훤히가 다음 포트로 옮겨 뜨므로 매번 새로 고른다."""
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class UIProc:
    """화면 모드 실행 결과를 subprocess.run 결과처럼 보이게 한다 (returncode·stdout·stderr)."""

    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _api(port, path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def run_ui(args, url, flags, out_dir):
    """심사위원과 같은 경로: 화면 모드로 띄워 [탐지 시작]과 같은 요청을 보낸다.

    화면 기본값(주요 4종 검사)을 적용하고 시험에 필요한 추가 검사만 명시적으로 켠다.
    CLI 옵션 가운데 화면 설정에 해당하는 것만 옮긴다.
    """
    import base64
    base = [args.exe] if args.exe else [PY, os.path.join(ROOT, "detector", "main.py")]
    port = _free_port()
    app = subprocess.Popen(base + ["--no-browser", "--port", str(port), "--out", out_dir],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                _api(port, "/api/status", timeout=2)
                break
            except Exception:
                time.sleep(0.2)
        else:
            return UIProc(1, stderr="화면 모드가 뜨지 않음"), 0.0
        body = {"url": url, "subdomains": "--subdomains" in flags,
                "check_links": "--check-links" in flags, "ocr_images": "--ocr-images" in flags,
                "attachments": "--attachments" in flags, "search_reflect": "--search-reflect" in flags}
        if "--index-csv" in flags:
            with open(flags[flags.index("--index-csv") + 1], "rb") as fp:
                body["index_csv"] = base64.b64encode(fp.read()).decode("ascii")
        t0 = time.perf_counter()
        _api(port, "/api/scan", body)
        while True:
            time.sleep(0.3)
            st = _api(port, "/api/status")
            if not st["running"]:
                break
        sec = time.perf_counter() - t0
        if st.get("error"):
            return UIProc(1, stderr=st["error"]), sec
        meta = _api(port, "/api/result")["meta"]
        # 결과 파일이 실제로 쓰였는지가 채점의 전부다
        if not os.path.exists(os.path.join(out_dir, "result.json")):
            return UIProc(1, stderr="result.json 이 생기지 않음"), sec
        return UIProc(0, stdout=f"페이지 {meta['page_count']}개"), sec
    finally:
        try:
            _api(port, "/api/quit", {}, timeout=5)
        except Exception:
            pass
        try:
            app.wait(timeout=15)
        except subprocess.TimeoutExpired:
            app.kill()


def run_tool(args, url, flags, out_dir):
    os.makedirs(out_dir, exist_ok=False)
    if args.ui:
        return run_ui(args, url, flags, out_dir)
    base = [args.exe] if args.exe else [PY, os.path.join(ROOT, "detector", "main.py")]
    cmd = base + ["--cli", "--quiet", "--url", url, "--out", out_dir] + flags
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return proc, time.perf_counter() - t0


def score(site, out_dir):
    key = json.load(open(os.path.join(ROOT, site, "answer_key.json"), encoding="utf-8"))
    if not key.get("answers"):
        return None
    proc = subprocess.run([PY, os.path.join(ROOT, "tools", "score.py"),
                           "--key", os.path.join(ROOT, site, "answer_key.json"),
                           "--result", os.path.join(out_dir, "result.json")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    text = proc.stdout
    m = re.search(r"정답 (\d+)건 / 제출 (\d+)건 / 정탐 (\d+)건", text)
    if not m:
        return {"error": text[-800:] + proc.stderr[-800:]}
    truth, sub, hit = map(int, m.groups())
    return {"truth": truth, "submitted": sub, "hit": hit,
            "perfect": truth == sub == hit, "detail": text}


def schema_problems(out_dir, entry_url):
    """두 결과 파일의 요강 붙임4 스키마 위반. (오류 줄, 주의 수)"""
    lines, warns = [], 0
    for name, extra in (("result.json", False), ("result_extra.json", True)):
        path = os.path.join(out_dir, name)
        if not extra and not os.path.exists(path):
            lines.append(f"[파일 오류] {name} 이 생성되지 않음 (요강: 미생성 시 평가 제외)")
            continue
        if extra and not os.path.exists(path):
            continue
        file_err, item_err, warn, doc = schema_check.check(path, extra, entry_url)
        warns += len(warn)
        if file_err or item_err:
            lines += schema_check.report(name, file_err, item_err, [],
                                         doc.get("findings") if isinstance(doc, dict) else None)
    return lines, warns


def main_set(out_dir):
    try:
        doc = json.load(open(os.path.join(out_dir, "result.json"), encoding="utf-8"))
    except Exception:
        return []
    return sorted({f"{f['url']} | {f['location']} | {f['technique']}" for f in doc["findings"]})


def extra_set(out_dir):
    try:
        doc = json.load(open(os.path.join(out_dir, "result_extra.json"), encoding="utf-8"))
    except Exception:
        return []
    return sorted({f"{f['url']} | {f['location']} | {f['extra_finding']}" for f in doc["findings"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=None)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--ui", action="store_true",
                    help="심사위원처럼 화면 모드로 실행 (첨부파일·검색창 점검·증거 사진이 켜진 기본 설정). "
                         "result.json 은 CLI 기준과 같아야 하고, result_extra.json 차이는 참고로만 보인다")
    args = ap.parse_args()
    if args.ui and args.save_baseline:
        ap.error("--ui 결과는 기준으로 저장하지 않습니다 (기준은 CLI 결과)")
    sys.stdout.reconfigure(encoding="utf-8")

    base = {}
    if os.path.exists(BASELINE):
        base = json.load(open(BASELINE, encoding="utf-8"))
    run_out = os.path.join(OUT, "runs", datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
    os.makedirs(run_out, exist_ok=False)
    print("회귀 증거 폴더:", run_out, flush=True)
    summary, ok_all = {}, True
    for name, site, port, url, flags in RUNS:
        if args.only and name not in args.only and site not in args.only:
            continue
        if "--ocr-images" in flags and not ocr_ok():
            print(f"[{name:15s}] 건너뜀 (이 환경에는 Windows 한국어 글자 인식이 없음)", flush=True)
            continue
        server = start_server(site, port)
        out_dir = os.path.join(run_out, ("ui_" if args.ui else "") + name)
        posted = os.path.join(ROOT, site, "_posted.log")
        try:
            proc, sec = run_tool(args, url, flags, out_dir)
            # 채점기는 사람처럼 '더보기'를 눌러 보므로, 그 전에 점검 도구가 보낸 POST 만 읽어 둔다
            posts = open(posted, encoding="utf-8").read().split() if os.path.exists(posted) else []
            ext_log = os.path.join(ROOT, site, "_ext_get.log")
            ext_gets = open(ext_log, encoding="utf-8").read().split() if os.path.exists(ext_log) else []
            sc = (score(site, out_dir) if name not in ("testsite11-sub", "testsite14-off")
                  and proc.returncode == 0
                  else None)
        finally:
            server.terminate()
            server.wait()
        allowed = json.load(open(os.path.join(ROOT, site, "answer_key.json"),
                                 encoding="utf-8")).get("allowed_posts", [])
        posts = [x for x in posts if x.split("?")[0] not in allowed]
        if proc.returncode != 0:
            print(f"[{name}] 실행 실패\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
            ok_all = False
            continue
        extra = extra_set(out_dir)
        schema, schema_warns = schema_problems(out_dir, url)
        pages = re.search(r"페이지 (\d+)[건개]", proc.stdout)   # 단위를 건으로 바꾸기 전 exe 도 읽는다
        row = {"out_dir": out_dir, "seconds": round(sec, 1), "pages": int(pages.group(1)) if pages else None,
               "main": main_set(out_dir), "extra": extra, "posts": posts}
        line = f"[{name:15s}] {sec:5.1f}s  pages={row['pages']}"
        if sc is not None:
            if "error" in sc:
                line += "  채점 오류"
                print(sc["error"])
                ok_all = False
            else:
                row["score"] = {k: sc[k] for k in ("truth", "submitted", "hit")}
                line += f"  정답 {sc['truth']} 제출 {sc['submitted']} 정탐 {sc['hit']}"
                if not sc["perfect"]:
                    line += "  << 100점 아님"
                    ok_all = False
                    print(sc["detail"])
        line += f"  main={len(row['main'])} extra={len(extra)}"
        if schema:
            line += f"  << 스키마 위반 {len(schema)}건"
            line += "".join(f"\n      {s}" for s in schema)
            ok_all = False
        elif schema_warns:
            line += f"  (스키마 주의 {schema_warns}건: tools\\schema_check.py 로 확인)"
        if posts:
            line += f"  << POST {len(posts)}건: {posts[:3]}"
            ok_all = False
        if isinstance(port, tuple):
            line += f"  바깥 조회={len(ext_gets)}"
            # 꺼 두면 바깥 누리집에 한 건도 가면 안 되고, 켜도 도메인마다 몇 건을 넘으면 안 된다
            limit = 3 * (len(port) - 1) if "--check-links" in flags else 0
            if len(ext_gets) > limit:
                line += f"  << 바깥 조회가 너무 많음 {ext_gets[:5]}"
                ok_all = False
        prev = base.get(name)
        if prev is not None:
            gone = sorted(set(prev.get("main", [])) - set(row["main"]))
            new = sorted(set(row["main"]) - set(prev.get("main", row["main"])))
            # 화면 모드는 첨부파일·검색창 점검이 늘 켜져 있어 추가 유형이 CLI 기준과 다를 수 있다
            extra_gone = sorted(set(prev["extra"]) - set(extra))
            extra_new = sorted(set(extra) - set(prev["extra"]))
            if args.ui:
                for g in extra_gone:
                    line += f"\n      (참고) 추가 유형 사라짐: {g}"
                for n in extra_new:
                    line += f"\n      (참고) 추가 유형 새로 나옴: {n}"
            else:
                gone, new = extra_gone + gone, extra_new + new
            if gone or new:
                line += "  << 결과 변화"
                ok_all = False
                for g in gone:
                    line += f"\n      - 사라짐: {g}"
                for n in new:
                    line += f"\n      + 새로 나옴: {n}"
            if prev.get("pages") != row["pages"]:
                line += f"  (방문 페이지 {prev.get('pages')} -> {row['pages']})"
        print(line, flush=True)
        summary[name] = row

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(run_out, "summary.json"), "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=1)
    json.dump(summary, open(os.path.join(OUT, "last_ui.json" if args.ui else "last.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    if args.save_baseline:
        base.update(summary)
        json.dump(base, open(BASELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("기준 저장:", BASELINE)
    print("\n전체 결과:", "이상 없음" if ok_all else "확인 필요")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
