"""탐지 우회 기법 시험 사이트(testsite_evasion) 확인.

    .venv\\Scripts\\python tools\\evasion_check.py                 소스로 실행
    .venv\\Scripts\\python tools\\evasion_check.py --exe 훤히.exe
    .venv\\Scripts\\python tools\\evasion_check.py --sync          실제 결과로 정답 파일의 status 를 고쳐 쓴다

regress.py 와 달리 '아직 못 잡는 것'을 모은 사이트라 놓치는 항목이 있는 것이 정상이다.
항목마다 status 를 두고 그것과 비교한다.
  answers       (url·위치·기법이 맞아야 잡힘)
  other_answers (4종 가운데 분류 미정. 그 요소를 주요·추가 유형 어느 쪽으로든 보고하면 잡힘)
    - detected  인데 놓침      -> 회귀 (실패)
    - known_gap 인데 잡힘      -> 개선. --sync 로 detected 로 바꿔 커밋한다
  traps         (정상 글. 주요 유형 검출이 없어야 함. location 이 없으면 그 주소 전체가 함정)
    - ok        인데 오탐      -> 실패
    - known_fp  인데 오탐 없음 -> 개선
  정답·함정 어디에도 없는 주요 유형 검출은 늘 실패다.
결과 폴더는 _regress/evasion/ 이다.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regress                      # noqa: E402  시험 서버 띄우기·도구 실행을 같이 쓴다
import schema_check                 # noqa: E402  결과 파일 스키마(요강 붙임4)
import score                        # noqa: E402  선택자 -> 요소 해석을 같이 쓴다

SITE = "testsite_evasion"
PORT = 8788
KEY = os.path.join(regress.ROOT, SITE, "answer_key.json")
OUT = os.path.join(regress.OUT, "evasion")


def _findings(path, kind):
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except Exception:
        return []
    return [{"url": f.get("url", ""), "location": f.get("location", ""), "technique": f.get(kind, "")}
            for f in doc.get("findings", [])]


def judge(key):
    """항목마다 (항목, 잡혔는가 | None=선택자 오류) 와, 어디에도 맞지 않는 주요 유형 검출을 돌려준다."""
    base = key["base"]
    tech = lambda i: i["technique"]
    with score.sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        main, unresolved = score.build_index(page, base, _findings(os.path.join(OUT, "result.json"), "technique"), tech)
        extra, _ = score.build_index(page, base, _findings(os.path.join(OUT, "result_extra.json"), "extra_finding"),
                                     tech)
        anywhere = {(u, path) for u, path, _ in main | extra}
        main_at = {(u, path) for u, path, _ in main}
        groups = {"answers": [], "other_answers": [], "traps": []}
        claimed = set()
        items = [(g, a) for g in groups for a in key.get(g, [])]
        by_url = {}
        for g, a in items:
            by_url.setdefault(a["url"], []).append((g, a))
        for url, group in by_url.items():
            # 페이지 단위 함정(location 없음): 그 주소의 주요 유형 검출은 위치와 상관없이 모두 오탐이다
            # (바깥 주소로 넘어간 뒤의 화면을 보고한 것처럼, 이 페이지에 없는 요소를 가리키는 검출 포함)
            whole = [(g, a) for g, a in group if not a.get("location")]
            for g, a in whole:
                u = score.norm_url(url, base)
                on_page = [x for x in main if x[0] == u]
                lost = [it for it in unresolved if score.norm_url(it["url"], base) == u]
                claimed.update(on_page)
                unresolved = [it for it in unresolved if it not in lost]
                groups[g].append((a, bool(on_page or lost)))
            group = [(g, a) for g, a in group if a.get("location")]
            if not group:
                continue
            page.goto(base + url, wait_until="networkidle")
            page.wait_for_timeout(2000)          # 늦게 끼워 넣는 광고 (score.py 와 같은 대기)
            score.reveal_lazy(page)              # 화면을 내려야 불러오는 iframe·댓글 (score.py 와 같음)
            for g, a in group:
                path = score.resolve(page, a["location"])
                at = (score.norm_url(url, base), path)
                if path is None:
                    hit = None
                elif g == "answers":
                    hit = at + (a["technique"],) in main
                    claimed.add(at + (a["technique"],))
                elif g == "other_answers":
                    hit = at in anywhere
                    claimed.update(x for x in main if x[:2] == at)
                else:                           # 함정: 주요 유형 검출이 하나라도 있으면 오탐
                    hit = at in main_at
                    claimed.update(x for x in main if x[:2] == at)
                groups[g].append((a, hit))
        browser.close()
    stray = sorted(main - claimed)
    return groups, stray, unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=None)
    ap.add_argument("--sync", action="store_true", help="실제 결과로 answer_key.json 의 status 를 고쳐 쓴다")
    args = ap.parse_args()
    args.ui = False                 # regress.run_tool 이 보는 값
    sys.stdout.reconfigure(encoding="utf-8")

    key = json.load(open(KEY, encoding="utf-8"))
    server = regress.start_server(SITE, PORT)
    try:
        proc, sec = regress.run_tool(args, key["entry_url"], [], OUT)
        if proc.returncode != 0:
            print(f"실행 실패\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
            return 1
        groups, stray, unresolved = judge(key)
    finally:
        server.terminate()
        server.wait()

    regressions, improved, broken, new_fp = [], [], [], []
    for g, title in (("answers", "주요 4종"), ("other_answers", "분류 미정 (주요·추가 유형 어느 쪽이든)"),
                     ("traps", "오탐 함정 (주요 유형 검출이 없어야 함)")):
        page = None
        for a, hit in groups[g]:
            if a["url"] != page:
                page = a["url"]
                print(f"\n[{title}] {page}")
            if hit is None:
                broken.append(a)
                mark = "??"
            elif g == "traps":
                mark = "오탐" if hit else "정상"
                if hit and a["status"] == "ok":
                    new_fp.append(a)
                    mark += "  << 새 오탐"
                elif not hit and a["status"] == "known_fp":
                    improved.append(a)
                    mark += "  << 개선"
            elif hit:
                mark = "잡힘"
                if a["status"] != "detected":
                    improved.append(a)
                    mark += "  << 개선"
            else:
                mark = "놓침"
                if a["status"] == "detected":
                    regressions.append(a)
                    mark += "  << 회귀"
            print(f"  {mark:12s} {a.get('technique', '-'):11s} {a.get('location') or '(페이지 전체)':28s} {a.get('note') or a.get('why')}")

    found = [h for g in ("answers", "other_answers") for _, h in groups[g]]
    fps = sum(1 for _, h in groups["traps"] if h)
    print(f"\n잡힘 {sum(1 for h in found if h)} / {len(found)}  ·  함정 오탐 {fps} / {len(groups['traps'])}  ({sec:.1f}초)")
    for a in broken:
        print(f"[정답 파일 오류] 선택자가 요소 하나를 가리키지 않음: {a['url']} {a['location']}")
    for u, path, t in stray:
        print(f"[오탐] 정답·함정에 없는 검출 {u[1]}?{'&'.join(f'{k}={v}' for k, v in u[2])} [{t}] {path}")
    for it in unresolved:
        print(f"[해석 불가한 제출] {it['url']} | {it['location']}")
    if improved:
        print(f"\n개선 {len(improved)}건." + ("" if args.sync else " --sync 로 status 를 고쳐 함께 커밋하세요."))
    if regressions:
        print(f"\n회귀 {len(regressions)}건: 전에는 잡히던 항목을 놓쳤습니다.")
    if new_fp:
        print(f"\n새 오탐 {len(new_fp)}건: 전에는 검출이 없던 정상 글을 광고로 보고했습니다.")

    # 결과 파일 스키마. 진입 주소가 리다이렉트돼도 meta.entry_url 은 입력한 주소 그대로여야 한다
    schema_err = False
    for name, extra in (("result.json", False), ("result_extra.json", True)):
        path = os.path.join(OUT, name)
        f_err, i_err, warn, doc = schema_check.check(path, extra, key["entry_url"])
        for line in schema_check.report(name, f_err, i_err, warn,
                                        doc.get("findings") if isinstance(doc, dict) else None):
            print(line)
        schema_err = schema_err or bool(f_err or i_err or warn)

    hard_fail = bool(stray or unresolved or broken or schema_err)
    if args.sync:
        for g in groups:
            for a, hit in groups[g]:
                if hit is not None:
                    a["status"] = (("known_fp" if hit else "ok") if g == "traps"
                                   else ("detected" if hit else "known_gap"))
        with open(KEY, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(json.dumps(key, ensure_ascii=False, indent=1) + "\n")
        print("status 를 실제 결과로 고쳐 썼습니다:", KEY)
        return 1 if hard_fail else 0
    return 1 if (hard_fail or regressions or new_fp) else 0


if __name__ == "__main__":
    sys.exit(main())
