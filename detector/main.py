"""훤히 - 공공 누리집 숨은 불법광고 점검 도구. 진입점."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--scan-worker":
    from scan_worker import worker_main
    raise SystemExit(worker_main(sys.argv[2]))

from console import attach_to_parent

# 터미널 모드로 실행했으면 출력이 반드시 보여야 한다.
attach_to_parent(allocate_if_missing="--cli" in sys.argv)

import lexicon  # noqa: E402
import report  # noqa: E402
from run_archive import RunArchive, RunClock  # noqa: E402
from index_check import decode, parse_urls  # noqa: E402
from scan import DEFAULT_MAX_PAGES, TIME_LIMIT_SEC
from scan_worker import run_scan  # noqa: E402
from urls import normalize_entry  # noqa: E402


def default_out_dir():
    """구동 파일이 있는 폴더에 결과를 생성하는 것이 원칙."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def main():
    ap = argparse.ArgumentParser(description="훤히 — 공공 누리집 숨은 불법광고 점검 도구")
    ap.add_argument("--url", help="점검 대상 진입 URL (생략하면 화면 모드로 실행)")
    ap.add_argument("--cli", action="store_true", help="화면 없이 터미널로만 실행")
    ap.add_argument("--port", type=int, default=8900, help="화면 모드 포트")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--out", default=None, help="결과 파일 생성 폴더")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--polite", action="store_true",
                    help="요청 간격을 두고 robots.txt 를 지킨다 (실제 누리집 점검 시 권장)")
    ap.add_argument("--delay", type=float, default=None, help="페이지 사이 간격(초)")
    ap.add_argument("--ignore-robots", action="store_true", help="robots.txt 를 무시")
    ap.add_argument("--cloaking", action="store_true",
                    help="검색엔진 크롤러 신원으로 한 번 더 조회해 위장 여부를 확인")
    ap.add_argument("--attachments", action="store_true",
                    help="게시글 첨부파일(PDF·HWP·HWPX) 안의 광고도 검사 (CLI 기본 꺼짐)")
    ap.add_argument("--search-reflect", action="store_true",
                    help="검색창에 무해한 표식을 넣어 한 번 조회해, 검색어가 결과 페이지에 반사되어 "
                         "검색엔진 광고에 악용될 수 있는지 점검 (CLI 기본 꺼짐)")
    ap.add_argument("--index-csv", default=None, metavar="파일",
                    help="Search Console 에서 내려받은 색인 페이지 목록(CSV 또는 주소 목록). "
                         "색인된 주소를 하나씩 열어 광고가 노출되는지 확인")
    ap.add_argument("--subdomains", action="store_true",
                    help="같은 기관의 서브도메인·다른 포트 주소(예: bbs.기관.go.kr)도 따라가 점검")
    ap.add_argument("--check-links", action="store_true",
                    help="누리집이 걸어 둔 바깥 링크(패밀리 사이트·배너)의 목적지를 도메인마다 한 번 조회해, "
                         "만료된 도메인이 광고 사이트로 바뀌지 않았는지 확인 (CLI 기본 꺼짐)")
    ap.add_argument("--ocr-images", action="store_true",
                    help="본문 그림을 받아 Windows 글자 인식으로 읽고, 그림으로 올린 광고 문구를 찾는다 (기본 꺼짐)")
    ap.add_argument("--time-limit", type=float, default=TIME_LIMIT_SEC / 60, metavar="분",
                    help="이 시간이 지나면 새 페이지를 열지 않고 지금까지의 결과로 마친다 "
                         "(기본 25분, 0 이면 제한 없음)")
    ap.add_argument("--evidence", action="store_true",
                    help="숨겨진 요소를 드러낸 증거 화면을 함께 저장 (CLI 기본 꺼짐)")
    ap.add_argument("--primary-only", action="store_true", help="주요 4종만 검사 (GUI 기본값)")
    args = ap.parse_args()
    if args.primary_only and any((args.attachments, args.search_reflect, args.check_links, args.ocr_images, args.cloaking, args.index_csv)):
        ap.error("--primary-only와 추가 검사는 함께 선택할 수 없습니다")
    if args.url:
        args.url = normalize_entry(args.url)

    out_dir = args.out or default_out_dir()
    # 화면에서 고친 탐지 키워드가 있으면 터미널 실행에도 똑같이 적용한다
    lexicon.load_state(out_dir)

    # URL 을 주지 않았거나 --cli 가 아니면 화면 모드로 띄운다.
    if not args.url or not args.cli:
        from ui.server import serve
        serve(out_dir, port=args.port, open_browser=not args.no_browser)
        return

    def progress(n, url):
        if not args.quiet:
            print(f"  [{n:3d}] {url}", flush=True)

    clock = RunClock()
    if not args.quiet:
        print(f"점검 시작: {args.url}")
    index_urls = None
    if args.index_csv:
        with open(args.index_csv, "rb") as fp:
            index_urls = parse_urls(decode(fp.read()))
        if not args.quiet:
            print(f"색인 목록: 주소 {len(index_urls)}건")
    from review_store import ReviewStore
    options = dict(max_pages=args.max_pages, polite=args.polite, delay=args.delay,
                   respect_robots=not args.ignore_robots, cloaking=args.cloaking,
                   attachments=args.attachments, search_reflect=args.search_reflect,
                   index_urls=index_urls, subdomains=args.subdomains, check_links=args.check_links,
                   ocr_images=args.ocr_images, primary_only=args.primary_only,
                   time_limit=args.time_limit * 60 if args.time_limit else None,
                   excluded_urls=ReviewStore(out_dir).exclusions())
    archive = RunArchive(out_dir, args.url, dict(options, evidence=args.evidence), clock=clock)
    try:
        res = run_scan(args.url, archive, progress=progress,
                   evidence_dir=str(archive.path / "evidence") if args.evidence else None,
                   **options)
        paths, n_main, n_extra = archive.finish(res)
    except Exception as exc:
        try:
            archive.fail(exc)
        except OSError:
            pass  # 원래 실행 오류를 보존한다
        print(f"점검 실패: {exc}\n실행 기록: {archive.path}", file=sys.stderr, flush=True)
        return 1
    print(f"실행 기록: {archive.path}")

    print(f"\n점검 종료  페이지 {len(res['pages'])}건 / {res['elapsed']:.1f}초"
          f"  ·  엔진: {res.get('engine', '?')}")
    print(f"  종료 확인까지 {res.get('process_elapsed', res['elapsed']):.1f}초 (전체 시간과 구분)")
    for line in report.coverage_lines(res):
        print(f"  ※ {line}")
    if res.get("stopped") == "time":
        print("    (--time-limit 으로 시간 상한을 바꿀 수 있습니다)")
    print(f"  주요 유형 검출 {n_main}건 -> {paths['result.json']}")
    print(f"  추가 유형 검출 {n_extra}건 -> {paths['result_extra.json']}")
    if report.coverage_lines(res):
        print(f"  열지 못한 페이지 목록 -> {paths[report.COVERAGE_FILE]}")


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as exc:
        print(f"실행 실패: {exc}", file=sys.stderr, flush=True)
        exit_code = 1
    raise SystemExit(exit_code)
