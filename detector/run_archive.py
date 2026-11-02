"""실행별 결과와 증거를 보존한다. 공식 제출 JSON의 필드는 바꾸지 않는다."""
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

import lexicon
import report
from fileio import write_json


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def serializable(res, entry_url):
    doc = dict(res, entry_url=entry_url)
    for key in ("started", "finished"):
        if hasattr(doc.get(key), "isoformat"):
            doc[key] = doc[key].isoformat(timespec="seconds")
    return doc


def result_dir(out_dir, result):
    run_id = (result or {}).get("run_id")
    if not run_id:
        return Path(out_dir)  # 이전 버전에서 저장한 결과
    if not re.fullmatch(r"\d{8}T\d{12}Z-[0-9a-f]{12}", run_id):
        raise ValueError("잘못된 실행 ID")
    return Path(out_dir) / "runs" / run_id


class RunClock:
    """Start at accepted GUI request / CLI start, independent of worker startup."""
    def __init__(self):
        self.started = datetime.now(timezone.utc)
        self.begin = time.monotonic()

    def stamp(self, res):
        res.setdefault("engine_elapsed", res["elapsed"])
        res.setdefault("engine_started", res["started"].isoformat())
        res.setdefault("engine_finished", res["finished"].isoformat())
        res.update(started=self.started, finished=datetime.now(timezone.utc),
                   elapsed=time.monotonic() - self.begin,
                   timing_scope="request_to_saved_results_before_final_metadata_commit")


class RunArchive:
    def __init__(self, out_dir, entry_url, options, clock=None):
        self.clock = clock
        self.out_dir = Path(out_dir)
        self._preserve_legacy()
        self.entry_url = entry_url
        self.id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid4().hex[:12]
        self.path = self.out_dir / "runs" / self.id
        self.path.mkdir(parents=True, exist_ok=False)
        from scan import scan
        excluded = {"progress", "evidence_dir", "snapshot_dir", "should_stop", "checkpoint", "status", "checkpoint_each_page", "resume_state"}
        defaults = {name: param.default for name, param in inspect.signature(scan).parameters.items()
                    if name not in excluded and param.default is not inspect.Parameter.empty}
        options = dict(defaults, **options)
        rules = {c[0]: list(getattr(lexicon, c[0])) for c in lexicon.CATEGORIES}
        write_json(self.path / "rules.json", rules, indent=2)
        if getattr(sys, "frozen", False):
            source = {"executable": sha256(sys.executable)}
        else:
            root = Path(__file__).parent
            source = {p.relative_to(root).as_posix(): sha256(p)
                      for p in sorted(root.rglob("*"))
                      if p.is_file() and p.suffix in {".py", ".js", ".html"}}
        versions = {}
        for name in ("playwright", "pypdf", "olefile", "pypdfium2"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = "unavailable"
        self.meta = {"run_id": self.id, "entry_url": entry_url, "status": "running",
                     "created_at": datetime.now(timezone.utc).isoformat(),
                     "owner_pid": __import__("os").getpid(),
                     "options": options, "python": sys.version, "dependencies": versions,
                     "source_sha256": source, "rules_sha256": sha256(self.path / "rules.json")}
        self._save_meta()

    def _preserve_legacy(self):
        """업그레이드 전 고정 경로의 결과·증거도 첫 실행 전에 복사해 둔다."""
        if (self.out_dir / "runs").exists():
            target = self.out_dir / "runs" / "legacy-import"
            if target.exists() and not (target / "manifest.json").exists():
                raise OSError("이전 기록 복사가 완료되지 않았습니다. runs/legacy-import와 원본을 확인하십시오.")
            return
        names = ("result.json", "result_extra.json", "scan_coverage.json", "last_result.json",
                 "review_state.json", "evidence", "snapshots")
        old = [self.out_dir / name for name in names if (self.out_dir / name).exists()]
        if not old:
            return
        target = self.out_dir / "runs" / "legacy-import"
        target.mkdir(parents=True, exist_ok=False)
        try:
            for src in old:
                if src.is_dir():
                    shutil.copytree(src, target / src.name)
                else:
                    shutil.copy2(src, target / src.name)
            write_json(target / "run.json", {
                "run_id": "legacy-import", "status": "imported", "entry_url": "이전 버전 결과",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "note": "업그레이드 때 보존한 원본. 당시 실행 설정·규칙은 확인되지 않음."}, indent=2)
            files = {p.relative_to(target).as_posix(): sha256(p)
                     for p in target.rglob("*") if p.is_file()}
            write_json(target / "manifest.json", {"algorithm": "sha256", "files": files}, indent=2)
        except Exception:
            # 불완전한 복사를 성공으로 취급하지 않는다. 원본은 그대로 둔다.
            write_json(target / "import_error.json", {"error": "이전 기록 복사 실패"})
            raise

    def inherit(self, folder, previous):
        """Each continuation owns a new immutable archive, with self-contained evidence."""
        folder = Path(folder)
        meta = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        shutil.copy2(folder / 'rules.json', self.path / 'rules.json')
        for name in ('evidence', 'snapshots'):
            if (folder / name).is_dir():
                shutil.copytree(folder / name, self.path / name)
        self.meta.update(parent_run_id=folder.name, scan_id=meta.get('scan_id', folder.name),
                         session_number=meta.get('session_number', 1) + 1,
                         previous_elapsed=previous.get('total_elapsed', previous.get('elapsed', 0)),
                         rules_sha256=sha256(self.path / 'rules.json'))
        self._save_meta()

    def cancel(self, res):
        if self.clock:
            self.clock.stamp(res)
        self.checkpoint(res)
        self.meta.update(status="cancelled", finished_at=datetime.now(timezone.utc).isoformat())
        self._save_meta()
        self._seal()

    def _save_meta(self):
        write_json(self.path / "run.json", self.meta, indent=2)

    def checkpoint(self, res):
        res["run_id"] = self.id
        res.update(scan_id=self.meta.get('scan_id', self.id),
                   parent_run_id=self.meta.get('parent_run_id'),
                   session_number=self.meta.get('session_number', 1),
                   total_elapsed=self.meta.get('previous_elapsed', 0) + res['elapsed'])
        report.write(self.entry_url, res, self.path)
        write_json(self.path / "last_result.json", serializable(res, self.entry_url), indent=1)

    def finish(self, res, review=None):
        self.checkpoint(res)
        if review is not None:
            write_json(self.path / "review_snapshot.json", review, indent=1)
        self.meta.update(status="partial" if (res.get("stopped") or
                         (res.get("coverage") or {}).get("failed_count") or
                         (res.get("coverage") or {}).get("left_count") or
                         (res.get("ocr_images") or {}).get("unavailable")) else "completed",
                         finished_at=datetime.now(timezone.utc).isoformat())
        self._save_meta()
        # Hash evidence and validate actual saved files before declaring completion.
        from output_schema import check
        for name, extra in (("result.json", False), ("result_extra.json", True)):
            errors, items, _, _ = check(self.path / name, extra, self.entry_url)
            if errors or items:
                raise ValueError(f"결과 파일 형식 검증 실패: {name}: {errors or items}")
        self._seal()
        if self.clock:
            # Include preparation, scan, optional checks, result serialization and
            # evidence hashing. Only the final small metadata commit follows this clock.
            report.write(self.entry_url, res, self.out_dir)
            write_json(self.out_dir / "last_result.json", serializable(res, self.entry_url), indent=1)
            cached = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))["files"]
            self.clock.stamp(res)
            self.checkpoint(res)
            self.meta.update(finished_at=res["finished"].isoformat(), elapsed_sec=res["elapsed"],
                             engine_elapsed_sec=res["engine_elapsed"], timing_scope=res["timing_scope"])
            self._save_meta()
            self._seal(cached)
        # 루트의 고정 파일 이름은 기존 제출·자동화와 호환된다. 원본은 runs 아래에 남는다.
        published = report.write(self.entry_url, res, self.out_dir)
        write_json(self.out_dir / "last_result.json", serializable(res, self.entry_url), indent=1)
        return published

    def fail(self, exc):
        self.meta.update(status="failed", error=f"{type(exc).__name__}: {exc}",
                         finished_at=datetime.now(timezone.utc).isoformat())
        self._save_meta()
        self._seal()

    def _seal(self, cached=None):
        cached = cached or {}
        mutable = {"run.json", "last_result.json", "result.json", "result_extra.json", "scan_coverage.json"}
        files = {p.relative_to(self.path).as_posix(): (cached[p.relative_to(self.path).as_posix()]
                 if p.relative_to(self.path).as_posix() in cached and p.name not in mutable else sha256(p))
                 for p in sorted(self.path.rglob("*"))
                 if p.is_file() and p.name != "manifest.json"}
        write_json(self.path / "manifest.json", {"algorithm": "sha256", "files": files}, indent=2)


def verify(path):
    """체크섬은 저장 이후의 손상·변경을 확인한다. 전자서명이나 진위 보증은 아니다."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(path).as_posix() for p in path.rglob("*")
              if p.is_file() and p.name != "manifest.json"}
    expected = manifest["files"]
    errors = [f"unexpected: {n}" for n in sorted(actual - expected.keys())]
    for name, digest in expected.items():
        target = (path / name).resolve()
        if not target.is_relative_to(path.resolve()) or not target.is_file():
            errors.append(f"missing or invalid: {name}")
        elif sha256(target) != digest:
            errors.append(f"changed: {name}")
    return errors
