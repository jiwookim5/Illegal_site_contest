"""붙임4 표준 스키마에 맞춰 결과 파일을 쓴다.

스키마를 어기면 평가 대상에서 제외되므로 필드 구성과 인코딩을 엄격히 지킨다.
- UTF-8, BOM 없음
- 최상위는 meta 와 findings 두 키
- 검출이 없어도 findings 는 빈 배열로 반드시 존재
- technique 은 코드 1건만 (배열·복수 나열 금지)
"""
import os

from fileio import write_json

MAIN_CODES = {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"}
TOOL_VERSION = "1.0.0"
COVERAGE_FILE = "scan_coverage.json"

# 열지 못한 사유 (session.fail_reason)
FAIL_NAMES = {
    "timeout": "응답 시간 초과", "network": "접속 오류", "server": "서버 오류(5xx)",
    "blocked": "접근 거부(401·403·429)", "error": "열기 오류", "partial": "열렸지만 끝까지 읽지 못함",
    "stalled": "응답이 멈춰 건너뜀",
}
STOP_NAMES = {
    "stalled": "진행이 정체되어 중단했습니다. 마지막 저장까지의 부분 결과입니다.",
    "interrupted": "완료가 확인되지 않은 실행의 중간 저장 기록입니다.",
    "user": "담당자가 점검을 중지해 일부 페이지만 점검했습니다.",
    "time": "점검 시간 상한에 닿아 일부 페이지만 점검했습니다.",
    "blocked": "페이지가 잇달아 열리지 않아 점검을 멈췄습니다. 서버가 요청을 막았거나 접속 장애가 의심됩니다.",
}


def coverage_lines(res):
    """점검 범위를 사람이 읽을 문장 몇 줄로. 아무 문제 없으면 빈 목록."""
    cov = res.get("coverage") or {}
    out = []
    if res.get("stopped") in STOP_NAMES:
        out.append(STOP_NAMES[res["stopped"]])
    if cov.get("in_progress"):
        out.append("분석을 마치지 못한 현재 페이지: " + cov["in_progress"])
    if res.get("forced_stop"):
        out.append("응답 없는 작업을 종료했습니다. 마지막 저장 이후의 진행분은 포함되지 않습니다.")
    if cov.get("invalid_candidates"):
        out.append(f"무효·반복 탐색 후보 {cov['invalid_candidates']}건을 제외했습니다.")
    if cov.get("exclusion_rule_count") or cov.get("excluded_count"):
        out.append(f"담당자가 등록한 이 누리집의 제외 규칙 {cov.get('exclusion_rule_count', 0)}건을 적용했고, "
                   f"해당 주소 {cov.get('excluded_count', 0)}건은 점검하지 않았습니다. "
                   "제외 주소의 내용 변경과 그 안에서만 연결된 페이지는 확인하지 않았습니다.")
    if cov.get("failed_count"):
        kinds = cov.get("failed_kinds") or {}
        out.append(f"열지 못했거나 끝까지 읽지 못한 페이지 {cov['failed_count']}건 ("
                   + ", ".join(f"{FAIL_NAMES.get(k, k)} {n}" for k, n in kinds.items()) + ")")
    if res.get("attachments_unread"):
        out.append(f"첨부파일 {len(res['attachments_unread'])}건은 받거나 읽지 못해 점검하지 못했습니다.")
    if cov.get("retry_waiting_count"):
        out.append(f"첫 열기에 실패해 다시 열 차례를 기다리던 주소 {cov['retry_waiting_count']}건은 점검하지 못했습니다.")
    if cov.get("frame_failed_pages"):
        out.append(f"페이지 {cov['frame_failed_pages']}곳의 하위 iframe 글을 읽지 못했습니다. 그 안의 광고는 점검되지 않았습니다.")
    if (res.get("ocr_images") or {}).get("unavailable"):
        out.append("그림 속 글자 검사를 하지 못했습니다: " + res["ocr_images"]["unavailable"])
    if cov.get("left_count") and not res.get("stopped"):
        out.append(f"최대 페이지 수({cov.get('max_pages')})에 닿아 주소 {cov['left_count']}건을 열지 않았습니다.")
    elif cov.get("left_count"):
        out.append(f"열지 않은 주소 {cov['left_count']}건이 남았습니다.")
    if cov.get("login_redirect_count"):
        out.append(f"로그인·로그아웃 화면으로 넘어가는 회원 메뉴 {cov['login_redirect_count']}건은 분석하지 않았습니다.")
    if cov.get("trap_skipped"):
        out.append(f"달력·정렬·검색 조건만 바뀌는 주소 {cov['trap_skipped']}건은 같은 꼴을 충분히 봐서 열지 않았습니다.")
    return out


def _meta(entry_url, res):
    return {
        "topic": "TOPIC",
        "entry_url": entry_url,
        "started_at": res["started"].isoformat(timespec="seconds"),
        "finished_at": res["finished"].isoformat(timespec="seconds"),
        "elapsed_sec": round(res["elapsed"], 3),
        "tool_version": TOOL_VERSION,
    }


def write(entry_url, res, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    main_rows, extra_rows = [], []
    for r in res["findings"]:
        if (r.get("judgement") or {}).get("decision") == "review":
            continue  # 원문·근거는 실행 기록과 UI에 보존하고, 제출 위반 항목에서는 제외한다.
        (main_rows if r["technique"] in MAIN_CODES else extra_rows).append(r)

    main = {"meta": _meta(entry_url, res), "findings": [
        {
            "id": f"f_{i:03d}",
            "url": r["url"],
            "is_violation": True,
            "location": r["location"],
            "evidence_text": r["evidence_text"],
            "technique": r["technique"],
        } for i, r in enumerate(main_rows, 1)
    ]}

    extra = {"meta": _meta(entry_url, res), "findings": [
        {
            "id": f"e_{i:03d}",
            "url": r["url"],
            # 검색창 반사 '취약'처럼 광고가 아직 없는 예방 점검 결과는 위반이 아니다
            "is_violation": r.get("is_violation", True),
            "location": r["location"],
            "evidence_text": r["evidence_text"],
            "technique": "ETC",
            "extra_finding": r.get("extra_finding") or r["technique"],
        } for i, r in enumerate(extra_rows, 1)
    ]}

    # 점검 범위(열지 못한 페이지·못 본 주소)는 표준 스키마에 넣을 자리가 없어 따로 쓴다.
    # '검출 0건'이 깨끗해서인지 열지 못해서인지 이 파일로 가린다.
    cov = {"meta": _meta(entry_url, res), "stopped": res.get("stopped"),
           **(res.get("coverage") or {})}

    paths = {}
    for name, doc in (("result.json", main), ("result_extra.json", extra), (COVERAGE_FILE, cov)):
        path = os.path.join(out_dir, name)
        write_json(path, doc, indent=2)
        paths[name] = path
    return paths, len(main_rows), len(extra_rows)
