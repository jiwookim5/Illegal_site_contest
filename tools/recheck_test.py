"""조치 확인 시험. 화면 서버를 띄워 점검한 뒤, 시험 사이트에서 광고를 지우고 [조치 확인]을 눌러 본다.

    .venv\\Scripts\\python tools\\recheck_test.py
    .venv\\Scripts\\python tools\\recheck_test.py --exe 훤히.exe     빌드한 실행 파일로

시험 사이트는 _regress\\recheck_site 에 만든다 (점검 뒤 파일을 고쳐 '조치'를 흉내 낸다).
  1번 글  숨긴 광고를 지움                          -> 사라짐 (조치완료)
  2번 글  숨긴 광고를 그대로 둠                      -> 아직 있음
  3번 글  글을 통째로 지움 (404)                     -> 페이지 삭제됨 (조치완료)
  4번 글  광고 앞에 새 댓글이 붙어 순번이 밀림      -> 아직 있음 (같은 문구로 알아봄)
  5번 글  게시판에 그대로 올린 광고 글을 지움        -> 사라짐 (조치완료)
그 뒤 시험 서버를 끄고 한 번 더 확인하면 남은 항목은 '확인 못 함'이고 상태는 미조치 그대로여야 한다.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_regress", "recheck_site")
OUT = os.path.join(ROOT, "_regress", "recheck_out")
SITE_PORT, UI_PORT = 8790, 8916     # 8787 은 testsite16 이 쓴다
PY = sys.executable

HEAD = '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>주민 게시판</title></head><body>'
HIDE = 'style="position:absolute;left:-9999px"'
AD = {
    1: "먹튀검증 안전놀이터 첫충 텔레그램 @fix_901",
    2: "카지노사이트 가입쿠폰 즉시 지급 텔@keep_902",
    3: "토토사이트 꽁머니 3만 지급 텔레그램 @gone_903",
    4: "바카라사이트 첫충 20% 텔레 @shift_904",
    5: "대포통장 삽니다 법인통장 매입 텔레그램 @visible_905",
}


def page(body):
    return HEAD + body + "</body></html>"


def write(name, html):
    with open(os.path.join(SITE, "pages", name), "w", encoding="utf-8") as fp:
        fp.write(html)


def build_site():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(os.path.join(SITE, "pages"))
    routes = {"/bbs/list|": "pages/list.html"}
    for i in range(1, 6):
        routes[f"/bbs/view|{i}"] = f"pages/view_{i}.html"
    with open(os.path.join(SITE, "routes.json"), "w", encoding="utf-8") as fp:
        json.dump(routes, fp)
    write("list.html", page("<ul>" + "".join(f'<li><a href="/bbs/view?id={i}">글 {i}</a></li>'
                                              for i in range(1, 6)) + "</ul>"))
    for i in (1, 2, 3):
        write(f"view_{i}.html", page(f'<div class="post"><p>공원 정비 안내 {i}</p>'
                                     f'<span class="ad" {HIDE}>{AD[i]}</span></div>'))
    write("view_4.html", page('<ul class="cmts"><li class="c">좋은 정보네요</li>'
                              f'<li class="c">감사합니다 <span {HIDE}>{AD[4]}</span></li></ul>'))
    write("view_5.html", page(f'<div class="post"><p>공지</p></div><div class="board"><p class="msg">{AD[5]}</p></div>'))


def take_action():
    """담당자가 관리자 화면에서 한 조치를 흉내 낸다."""
    write("view_1.html", page('<div class="post"><p>공원 정비 안내 1</p></div>'))
    os.remove(os.path.join(SITE, "pages", "view_3.html"))
    write("view_4.html", page('<ul class="cmts"><li class="c">첫 댓글</li><li class="c">좋은 정보네요</li>'
                              f'<li class="c">감사합니다 <span {HIDE}>{AD[4]}</span></li></ul>'))
    write("view_5.html", page('<div class="post"><p>공지</p></div><div class="board"></div>'))


def call(path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{UI_PORT}{path}",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=20))


def wait(flag):
    for _ in range(600):
        if not call("/api/status").get(flag):
            return
        time.sleep(0.3)
    raise TimeoutError(flag)


def outcome():
    """글 번호 -> (상태, 확인 결과) 들."""
    out = {}
    for f in call("/api/result")["findings"]:
        n = int(f["url"].rsplit("=", 1)[1]) if "id=" in f["url"] else 0
        out.setdefault(n, set()).add((f["status"], f["check"]))
    return out


def stop(proc):
    """프로세스를 자식까지 끈다. Windows 의 venv python.exe 는 실제 파이썬을 자식으로 띄워,
    terminate() 만으로는 시험 서버가 살아남아 '서버를 끈 뒤' 확인과 다음 실행이 같은 서버를 본다."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.kill()
    proc.wait()


def start_site():
    return subprocess.Popen([PY, os.path.join(ROOT, "tools", "serve.py"), str(SITE_PORT)],
                            env=dict(os.environ, SITE=os.path.relpath(SITE, ROOT)),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    exe = sys.argv[sys.argv.index("--exe") + 1] if "--exe" in sys.argv else None
    build_site()
    shutil.rmtree(OUT, ignore_errors=True)
    site = start_site()
    base = [exe] if exe else [PY, os.path.join(ROOT, "detector", "main.py")]
    ui = subprocess.Popen(base + ["--no-browser", "--port", str(UI_PORT), "--out", OUT],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    try:
        for _ in range(100):
            try:
                call("/api/status")
                break
            except Exception:
                time.sleep(0.2)
        time.sleep(0.5)
        # 5번 글(그대로 보이는 광고)은 추가 유형이다. 화면 기본값은 주요 4종만 보므로 켠다
        call("/api/scan", {"url": f"http://127.0.0.1:{SITE_PORT}/bbs/list", "extra_types": True})
        wait("running")
        before = outcome()
        print("점검:", {k: sorted(v) for k, v in sorted(before.items())})
        if sorted(before) != [1, 2, 3, 4, 5]:
            print("  << 점검에서 다섯 글의 광고를 모두 찾지 못함")
            ok = False

        take_action()
        call("/api/recheck", {})
        wait("rechecking")
        got = outcome()
        expect = {1: {("done", "gone")}, 2: {("open", "present")}, 3: {("done", "deleted")},
                  4: {("open", "present")}, 5: {("done", "gone")}}
        for n, want in expect.items():
            mark = "" if got.get(n) == want else "  << 기대와 다름"
            ok &= not mark
            print(f"  {n}번 글: {sorted(got.get(n, []))}{mark}")
        meta = call("/api/result")["meta"]
        print("  마지막 확인:", meta["recheck"])

        stop(site)
        call("/api/recheck", {})
        wait("rechecking")
        got = outcome()
        for n in (2, 4):
            mark = "" if got.get(n) == {("open", "unknown")} else "  << 서버가 꺼졌는데 상태가 바뀜"
            ok &= not mark
            print(f"  서버 꺼짐 {n}번 글: {sorted(got.get(n, []))}{mark}")
        for n in (1, 3, 5):        # 이미 조치완료된 항목은 다시 보지 않는다
            if got.get(n) != expect[n]:
                print(f"  << {n}번 글 조치완료가 바뀜: {sorted(got.get(n, []))}")
                ok = False
        posted = os.path.join(SITE, "_posted.log")
        if os.path.exists(posted):
            print("  << 시험 서버가 POST 를 받음:", open(posted, encoding="utf-8").read().split())
            ok = False
    finally:
        try:
            call("/api/quit", {})
        except Exception:
            pass
        time.sleep(1)
        stop(ui)
        if site.poll() is None:
            stop(site)
    print("\n조치 확인 시험:", "이상 없음" if ok else "확인 필요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
