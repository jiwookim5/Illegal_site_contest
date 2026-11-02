"""결과 파일 스키마 점검 (요강 붙임4).

    .venv\\Scripts\\python tools\\schema_check.py result.json
    .venv\\Scripts\\python tools\\schema_check.py result_extra.json --extra --entry http://127.0.0.1:8765/board/list

요강은 스키마를 지키지 않은 항목을 오답으로 처리하고(붙임2, 붙임4 '평가 참고사항'은 '채점 제외'),
파일 전체가 파싱되지 않으면 성능 점수를 0점으로 한다. 점수 계산과 별도로 여기서 먼저 걸러 낸다.
  파일 오류: 파일 전체가 평가 대상에서 빠지거나 0점이 될 수 있는 것 (BOM, 파싱 불가, 최상위 구조, meta)
  항목 오류: 그 findings 항목만 오답 처리되는 것
  주의: 채점에는 영향이 없을 수 있지만 고쳐 두는 것이 좋은 것
"""
import argparse
import json
import sys
from datetime import datetime

TECHNIQUES = ("HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN")
EXTRA_TECHNIQUE = "ETC"
META_REQUIRED = {"topic": str, "entry_url": str, "started_at": str, "finished_at": str, "elapsed_sec": (int, float)}
FINDING_REQUIRED = {"id": str, "url": str, "is_violation": bool, "location": str,
                    "evidence_text": str, "technique": str}


def _type_ok(value, kind):
    # JSON 의 true/false 는 파이썬에서 int 의 하위 형이라 숫자 칸에 들어가도 통과해 버린다
    if kind is bool:
        return isinstance(value, bool)
    return isinstance(value, kind) and not isinstance(value, bool)


def _iso(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def check(path, extra=False, entry_url=None):
    """(파일 오류 목록, {항목 번호: 항목 오류 목록}, 주의 목록, 문서 또는 None)"""
    file_err, item_err, warn = [], {}, []
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
    except OSError as exc:
        return [f"파일을 열 수 없음: {exc}"], item_err, warn, None
    if raw.startswith(b"\xef\xbb\xbf"):
        file_err.append("UTF-8 BOM 이 붙어 있음 (요강: BOM 없음)")
        raw = raw[3:]
    try:
        doc = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return file_err + ["UTF-8 이 아님"], item_err, warn, None
    except ValueError as exc:
        return file_err + [f"JSON 파싱 불가: {exc}"], item_err, warn, None

    if not isinstance(doc, dict):
        return file_err + ["최상위가 객체가 아님"], item_err, warn, None
    keys = set(doc)
    if keys != {"meta", "findings"}:
        missing, more = {"meta", "findings"} - keys, keys - {"meta", "findings"}
        if missing:
            file_err.append(f"최상위 키 없음: {sorted(missing)}")
        if more:
            file_err.append(f"최상위에 meta·findings 말고 다른 키: {sorted(more)}")

    meta = doc.get("meta")
    if not isinstance(meta, dict):
        file_err.append("meta 가 객체가 아님")
    else:
        for k, kind in META_REQUIRED.items():
            if k not in meta:
                file_err.append(f"meta.{k} 없음")
            elif not _type_ok(meta[k], kind):
                file_err.append(f"meta.{k} 형식이 다름: {type(meta[k]).__name__}")
        if "tool_version" in meta and not _type_ok(meta["tool_version"], str):
            file_err.append("meta.tool_version 이 문자열이 아님")
        if meta.get("topic") not in (None, "TOPIC") and isinstance(meta.get("topic"), str):
            file_err.append(f"meta.topic 은 'TOPIC' 이어야 함: {meta['topic']!r}")
        if entry_url and isinstance(meta.get("entry_url"), str) and meta["entry_url"] != entry_url:
            warn.append(f"meta.entry_url 이 입력 주소와 다름: {meta['entry_url']!r} != {entry_url!r}")
        started, finished = _iso(meta.get("started_at")), _iso(meta.get("finished_at"))
        for k, v in (("started_at", started), ("finished_at", finished)):
            if isinstance(meta.get(k), str) and v is None:
                file_err.append(f"meta.{k} 가 ISO 8601 이 아님: {meta[k]!r}")
            elif v is not None and v.tzinfo is None:
                warn.append(f"meta.{k} 에 시간대가 없음 (예시: +09:00)")
        if started and finished and started.tzinfo and finished.tzinfo:
            span = (finished - started).total_seconds()
            if span < 0:
                file_err.append("meta.finished_at 이 started_at 보다 앞섬")
            elif _type_ok(meta.get("elapsed_sec"), (int, float)) and abs(span - meta["elapsed_sec"]) > 2:
                warn.append(f"meta.elapsed_sec({meta['elapsed_sec']}) 가 시각 차이({span:.0f}초)와 다름")

    findings = doc.get("findings")
    if not isinstance(findings, list):
        file_err.append("findings 가 배열이 아님 (검출 0건이어도 [] 로 넣어야 함)")
        return file_err, item_err, warn, doc

    ids = {}
    allowed = (EXTRA_TECHNIQUE,) if extra else TECHNIQUES
    for i, f in enumerate(findings):
        errs = []
        if not isinstance(f, dict):
            item_err[i] = ["객체가 아님"]
            continue
        for k, kind in FINDING_REQUIRED.items():
            if k not in f:
                errs.append(f"{k} 없음")
            elif not _type_ok(f[k], kind):
                errs.append(f"{k} 형식이 다름: {type(f[k]).__name__}"
                            + (" (기법은 하나만, 배열 불가)" if k == "technique" and isinstance(f[k], list) else ""))
            elif kind is str and k != "evidence_text" and not f[k].strip():
                errs.append(f"{k} 가 빈 문자열")
        if isinstance(f.get("technique"), str) and f["technique"] not in allowed:
            errs.append(f"technique 값이 {'/'.join(allowed)} 가 아님: {f['technique']!r}")
        if isinstance(f.get("url"), str) and not f["url"].lower().startswith(("http://", "https://")):
            errs.append(f"url 이 전체 주소가 아님: {f['url']!r}")
        if isinstance(f.get("evidence_text"), str) and not f["evidence_text"].strip():
            warn.append(f"findings[{i}] evidence_text 가 비어 있음 (채점엔 안 쓰지만 반드시 기재)")
        if extra and not (isinstance(f.get("extra_finding"), str) and f["extra_finding"].strip()):
            errs.append("extra_finding 없음 (추가 탐지 결과 파일)")
        if isinstance(f.get("id"), str):
            if f["id"] in ids:
                errs.append(f"id 중복: {f['id']!r} (findings[{ids[f['id']]}] 와 같음)")
            else:
                ids[f["id"]] = i
        if errs:
            item_err[i] = errs
    return file_err, item_err, warn, doc


def report(path, file_err, item_err, warn, findings=None, limit=20):
    """사람이 읽을 줄들. 문제 없으면 빈 목록."""
    out = []
    for e in file_err:
        out.append(f"[파일 오류] {path}: {e}")
    for i, errs in list(item_err.items())[:limit]:
        f = findings[i] if findings and isinstance(findings[i], dict) else {}
        out.append(f"[항목 오류] findings[{i}] {f.get('id', '')} {f.get('url', '')}: {'; '.join(errs)}")
    if len(item_err) > limit:
        out.append(f"[항목 오류] … 외 {len(item_err) - limit}건")
    for w in warn[:limit]:
        out.append(f"[주의] {w}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--extra", action="store_true", help="추가 탐지 결과 파일(result_extra.json) 규칙으로 본다")
    ap.add_argument("--entry", default=None, help="입력한 진입 주소. meta.entry_url 과 비교한다")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    file_err, item_err, warn, doc = check(args.path, args.extra, args.entry)
    lines = report(args.path, file_err, item_err, warn, (doc or {}).get("findings") if isinstance(doc, dict) else None)
    print("\n".join(lines) if lines else f"이상 없음: {args.path}")
    return 1 if file_err or item_err else 0


if __name__ == "__main__":
    sys.exit(main())
