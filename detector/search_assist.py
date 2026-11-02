"""CLI로 실행하는 선택형 검색엔진 dork 탐색 도구."""
import argparse
import json
from pathlib import Path

from search_discovery import ENGINES, collect, new_folder, now, recheck, save, target_host
from search_providers import collect_api, load_keys, query_plan, resume_searches, DEFAULT_TEMPLATES

ROOT = Path(__file__).resolve().parents[1]


def pipeline(site, terms, engines, pages, mode, keys_path, dorks_path, output,
             inspect=True, subdomains=False, progress=print, should_stop=lambda: False, include_omitted=False,
             excluded_urls=(), entry_host=None, on_query=None, scope=None):
    """entry_host: 사용자가 입력한 원래 호스트. 검색 범위를 등록 도메인으로 넓혀도 제출 파일의 entry_url 은 이것을 쓴다."""
    host = target_host(site)
    terms = list(dict.fromkeys(t.strip() for t in terms if t.strip()))
    templates = json.loads(Path(dorks_path).read_text(encoding="utf-8-sig")) if Path(dorks_path).exists() else DEFAULT_TEMPLATES
    for engine in engines:
        query_plan(engine, host, terms, templates)
    if not engines or not 1 <= len(terms) <= 30 or not 1 <= pages <= 10:
        raise ValueError("검색엔진, 광고단어 1~30건, 페이지 수 1~10을 확인하세요.")
    keys = load_keys(keys_path)
    folder = new_folder(output, host)
    progress(f"결과 저장 위치: {folder}")
    run = {"target": host, "subdomains": subdomains, "started_at": now(), "queries": [], "results": [],
           "stopped": False, "limit_reached": False, "notes": [], "excluded_urls": list(excluded_urls)}
    if entry_host:
        run["entry_host"] = target_host(entry_host)
        run["entry_url"] = entry_host if "://" in entry_host else "https://" + entry_host
    if scope:
        run["scope"] = scope
    save(run, folder)
    for engine in engines:
        if should_stop():
            break
        engine_folder = folder / engine
        use_api = mode in ("api", "hybrid")
        opts = dict(pages=pages, subdomains=subdomains, templates=templates,
                    progress=progress, should_stop=should_stop)
        if use_api:
            if on_query:
                opts["on_query"] = on_query
            part = collect_api(host, terms, [engine], engine_folder, keys, include_omitted=include_omitted, **opts)
        else:
            part = collect(host, terms, [engine], engine_folder, **opts)
        # 질의와 source가 같은 evidence 사전을 공유할 수 있어 각각 새 사전으로 교체한다.
        for q in part["queries"]:
            q["evidence"] = {k: engine + "/" + v for k, v in q["evidence"].items()}
        existing = {r["url"]: r for r in run["results"]}
        for row in part["results"]:
            for s in row["sources"]:
                s["evidence"] = {k: engine + "/" + v for k, v in s["evidence"].items()}
            if row["url"] in existing:
                existing[row["url"]]["sources"].extend(row["sources"])
            elif len(run["results"]) < 300:
                run["results"].append(row)
                existing[row["url"]] = row
            else:
                run["limit_reached"] = True
        run["queries"].extend(part["queries"])
        run["notes"].extend(part.get("notes", []))
        run["limit_reached"] |= part["limit_reached"]
        save(run, folder)
        if run["limit_reached"]:
            break
    run.update(stopped=should_stop(), finished_at=now())
    save(run, folder)
    if inspect and run["results"] and not should_stop():
        recheck(run, folder, progress, should_stop, excluded_urls=excluded_urls)
    progress(f"완료: URL {len(run['results'])}건. 질의별 오류·차단 상태도 보고서에서 확인하세요.")
    return run, folder



def main():
    parser = argparse.ArgumentParser(description="엔진별 dork 수집 및 제출본 탐지기로 재검사")
    parser.add_argument("--site")
    parser.add_argument("--term", action="append")
    parser.add_argument("--engines", default="google")
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--mode", choices=("hybrid", "api", "browser"), default="hybrid")
    parser.add_argument("--keys", type=Path, default=ROOT / "search.env")
    parser.add_argument("--dorks", type=Path, default=ROOT / "search_dorks.json")
    parser.add_argument("--out", type=Path, default=ROOT / "search_results")
    parser.add_argument("--review-dir", type=Path,
                        help="훤히 점검 제외 목록이 저장된 출력 폴더 "
                             "(기본: --input 파일이 든 search_results 의 상위 폴더 또는 --out 의 상위 폴더)")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--include-omitted", action="store_true", help="구글 API의 유사 결과 생략 필터 해제(별도 비교용)")
    parser.add_argument("--subdomains", action="store_true")
    saved = parser.add_mutually_exclusive_group()
    saved.add_argument("--input", type=Path, help="저장된 results.json 재검사")
    saved.add_argument("--resume-search", type=Path, help="저장된 검색 ID로 미완료 검색 결과만 회수")
    args = parser.parse_args()
    from review_store import ReviewStore
    # 화면 실행과 같은 배치: <출력 폴더>/search_results/<검색 폴더>/results.json
    saved_input = args.input or args.resume_search
    output_dir = args.out.resolve().parent
    if saved_input:
        saved_folder = saved_input.resolve().parent
        # 강제 종료 뒤에는 검색 폴더의 google/results.json에만 검색 ID가 남을 수 있다.
        if saved_folder.name in ENGINES:
            saved_folder = saved_folder.parent
        output_dir = saved_folder.parent.parent
    review_dir = args.review_dir or output_dir
    excluded_urls = ReviewStore.exclusions_at(review_dir)
    if excluded_urls:
        print(f"점검 제외 목록 {len(excluded_urls)}건 적용: {review_dir}")
    from search_submission import publish
    if args.resume_search:
        run = json.loads(args.resume_search.read_text(encoding="utf-8"))
        resume_searches(run, args.resume_search.parent, load_keys(args.keys))
        publish(run, args.resume_search.parent, output_dir)
        print(args.resume_search.parent / "report.html")
        return 1 if any(q["state"] in ("error", "pending", "cancelled", "processing") for q in run["queries"]) else 0
    elif args.input:
        run = json.loads(args.input.read_text(encoding="utf-8"))
        recheck(run, args.input.parent, excluded_urls=excluded_urls)
        publish(run, args.input.parent, output_dir)
    elif args.site:
        run, folder = pipeline(args.site, args.term or [], args.engines.split(","), args.pages, args.mode,
                              args.keys, args.dorks, args.out, not args.collect_only, args.subdomains,
                              include_omitted=args.include_omitted, excluded_urls=excluded_urls)
        print(folder / "report.html")
        publish(run, folder, output_dir)
        return 1 if any(q["state"] in ("error", "blocked", "consent_required", "needs_review", "pending", "cancelled", "processing") for q in run["queries"]) else 0
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
