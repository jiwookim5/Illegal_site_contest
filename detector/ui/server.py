"""로컬 웹 UI 서버.

배포 대상이 기관 PC(폐쇄망 포함)이므로 표준 라이브러리만 사용한다.
탐지는 별도 스레드에서 돌리고, 화면은 상태를 주기적으로 물어본다.
"""
import base64
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from ui.search_job import SearchJob

import lexicon
import resume_state as resume_mod
import report
from fileio import write_json
from csv_safe import csv_text
from run_archive import RunArchive, RunClock, result_dir, verify, sha256
from review_store import ReviewStore
from scan_exclusions import ScanExclusions, exclusion_key
from ui.history import history_html
from index_check import decode as decode_index, parse_urls
from findings import classify
from judgement import judge, label_of
from scan import DEFAULT_MAX_PAGES
from scan_worker import run_scan
from recheck import recheck
from runtime import asset_path
from urls import normalize_entry, page_key
from ui import report_html
from ui import snapshot as snapshot_mod
from ui import native as native_ui
from ui.window import open_app_window

if getattr(sys, "frozen", False):
    # PyInstaller 로 묶이면 화면 파일이 임시 전개 폴더에 들어간다.
    HERE = os.path.join(sys._MEIPASS, "ui")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

LAST_FILE = "last_result.json"       # 프로그램을 다시 켜도 지난 결과를 볼 수 있게 남긴다
GONE_SHOW = 200                      # 지난 점검과 비교해 사라진 항목을 이만큼까지 보여 준다
# 출력 폴더 바로 아래의 제출용 사본. 가장 최근 점검 결과를 지우면 남은 것 중 최근 점검으로 바꿔 둔다
PUBLISHED = ("result.json", "result_extra.json", report.COVERAGE_FILE, LAST_FILE)
SHOWN_STATUS = ("completed", "partial")   # 시작 화면의 지난 점검 목록에 보이는 실행


def scan_seconds(minutes):
    if isinstance(minutes, bool):
        raise ValueError('점검 시간은 1~240분 중에서 선택하십시오.')
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        raise ValueError('점검 시간은 1~240분 중에서 선택하십시오.')
    if not 1 <= minutes <= 240:
        raise ValueError('점검 시간은 1~240분 중에서 선택하십시오.')
    return minutes * 60


class Session:
    """한 번의 탐지 실행과 그 결과를 들고 있는다."""

    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.lock = threading.Lock()
        self.search = SearchJob(out_dir)
        self.running = False
        self.closing = False
        self.error = None
        self.notice = None          # 오류는 아니지만 시작 화면에서 알려야 할 일 (예: 시작 직후 중지)
        self.entry_url = ""
        self.pages_done = 0
        self.scan_status = {}
        self.current = ""
        self.started_at = 0.0
        self.ended_at = 0.0
        self.prev_result = None
        self.result = None
        self.stop_requested = False
        # 조치 확인 진행 상황
        self.rechecking = False
        self.recheck_done = self.recheck_total = 0
        self.review_store = ReviewStore(out_dir)
        self.review = self.review_store.load()
        self.tkeys = {}             # 지금 결과의 항목 키 -> 문구 키
        self.keywords = lexicon.load_state(out_dir)   # 화면에서 고친 탐지 키워드
        self.last_ping = 0.0        # 화면이 살아 있는지 확인하는 신호
        self.bye_at = 0.0           # 화면이 닫히며 보낸 신호 (새로고침이면 곧 ping 이 다시 온다)
        self._load_last()
        self._sync_review()

    # ---- 지난 결과 ----
    def _last_path(self):
        return os.path.join(self.out_dir, LAST_FILE)

    @staticmethod
    def _read_result(path):
        """저장한 탐지 결과 하나를 읽는다. 없거나 깨졌으면 None."""
        try:
            with open(path, encoding="utf-8") as fp:
                doc = json.load(fp)
        except (OSError, ValueError):
            return None
        return doc if isinstance(doc, dict) and isinstance(doc.get("findings"), list) else None

    def _read_archived_result(self, folder, meta):
        doc = self._read_result(folder / LAST_FILE)
        if meta.get("status") in ("running", "failed"):
            # Recover the newest atomic page snapshot without rewriting evidence.
            doc = self._read_result(folder / "worker" / "checkpoint.json") or doc
            if doc:
                doc = dict(doc, run_id=folder.name, stopped="interrupted",
                           entry_url=meta['entry_url'], scan_id=meta.get('scan_id', folder.name),
                           session_number=meta.get('session_number', 1), parent_run_id=meta.get('parent_run_id'),
                           total_elapsed=meta.get('previous_elapsed', 0) + doc.get('elapsed', 0))
        return doc

    def _load_last(self):
        """지난 탐지 결과를 되살린다. 없거나 깨졌으면 결과 없이 시작한다."""
        doc = self._read_result(self._last_path())
        self.result = doc
        if doc:
            self.entry_url = doc.get("entry_url", "")

    # ---- 지난 점검 목록 ----
    def _run_dir(self, run_id):
        if not run_id:
            raise ValueError("점검 결과를 고르십시오.")
        return result_dir(self.out_dir, {"run_id": str(run_id)})   # 실행 ID 모양이 아니면 거절한다

    def resume_info(self, doc):
        state = (doc or {}).get('resume_state')
        if not state or not state.get('pending'):
            return {'can_resume': False, 'resume_reason': '남은 작업 또는 재개 가능한 저장 상태가 없습니다.'}
        try:
            resume_mod.validate(state)
        except ValueError as exc:
            return {'can_resume': False, 'resume_reason': str(exc)}
        return {'can_resume': True, 'resume_reason': '', 'pending_extra': state.get('pending_extra', 0)}

    def start_resume(self, run_id, time_limit=1500):
        if self.closing or self.running or self.rechecking or self.search.running:
            raise ValueError('진행 중인 작업이 끝난 뒤 이어서 점검하십시오.')
        folder = self._run_dir(run_id)
        meta = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        previous = self._read_archived_result(folder, meta)
        if (folder / 'manifest.json').exists() and verify(folder):
            raise ValueError('저장 기록의 무결성 검사에 실패했습니다. 원본 기록을 확인하십시오.')
        if sha256(folder / 'rules.json') != meta.get('rules_sha256'):
            raise ValueError('저장된 판정 규칙이 변경되었습니다. 새 점검을 시작하십시오.')
        info = self.resume_info(previous)
        if not info['can_resume']:
            raise ValueError(info['resume_reason'])
        # Use archived flags and keyword rules, never the current form's defaults.
        opts = meta['options']
        return self.start(previous.get('entry_url') or meta['entry_url'], opts.get('max_pages', DEFAULT_MAX_PAGES),
                          cloaking=opts.get('cloaking', False), attachments=opts.get('attachments', False),
                          search_reflect=opts.get('search_reflect', False), index_urls=opts.get('index_urls'),
                          subdomains=opts.get('subdomains', False), polite=opts.get('polite', False),
                          check_links=opts.get('check_links', False), ocr_images=opts.get('ocr_images', False),
                          extra_types=not opts.get('primary_only', False), capture=opts.get('evidence', False),
                          snapshots=opts.get('snapshots', False), time_limit=time_limit,
                          continuation=(folder, previous))

    def list_runs(self):
        """끝난 점검을 최근 것부터. 실행 ID 가 시각으로 시작하므로 이름 역순이 최근 순서다."""
        current = (self.result or {}).get("run_id")
        runs = []
        for meta_path in sorted((Path(self.out_dir) / "runs").glob("*/run.json"), reverse=True):
            try:
                folder = self._run_dir(meta_path.parent.name)
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if meta.get("status") not in (*SHOWN_STATUS, "running", "failed"):
                continue
            doc = self._read_archived_result(folder, meta)
            if not doc:
                continue
            cov = doc.get("coverage") or {}
            stopped = doc.get("stopped") or ("interrupted" if meta.get("status") in ("running", "failed") else None)
            runs.append({"run_id": folder.name, "entry_url": doc.get("entry_url") or meta.get("entry_url", ""),
                         "finished": doc.get("finished") or meta.get("finished_at", ""),
                         "page_count": len(doc.get("pages") or []),
                         # 결과 화면의 '의심 항목'과 같은 기준(같은 광고는 한 번)으로 센다
                         "count": report_html.ad_count(doc["findings"]),
                         "stopped": stopped,
                         # 최대 페이지 수에 닿았거나 열지 못한 페이지가 있으면 중지하지 않았어도 일부만 점검한 것이다
                         "partial": bool(stopped or cov.get("left_count") or cov.get("failed_count")),
                         # 목록에 이유별 표시(페이지 한도 도달·못 연 페이지 N건)를 달기 위한 수
                         "left_count": cov.get("left_count") or 0,
                         "failed_count": cov.get("failed_count") or 0,
                         "current": folder.name == current,
                         "scan_id": doc.get('scan_id', folder.name),
                         "session_number": doc.get('session_number', 1),
                         "total_elapsed": doc.get('total_elapsed', doc.get('elapsed', 0)),
                         **self.resume_info(doc)})
        return runs

    def open_run(self, run_id):
        if self.running or self.rechecking or self.search.running:
            return "점검이나 조치 확인이 끝난 뒤 다시 누르십시오."
        folder = self._run_dir(run_id)
        meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        doc = self._read_archived_result(folder, meta)
        if not doc:
            return "점검 결과 파일을 읽지 못했습니다. 지워졌거나 손상되었을 수 있습니다."
        self.result = doc
        self.entry_url = doc.get("entry_url", "")
        self._sync_review()
        return None

    def delete_run(self, run_id):
        """점검 결과 하나를 실행 폴더째(증거 사진·페이지 사본 포함) 지운다. 조치 이력은 남긴다."""
        if self.running or self.rechecking or self.search.running:
            return "점검이나 조치 확인이 끝난 뒤 지우십시오."
        folder = self._run_dir(run_id)
        if not folder.is_dir():
            return "이미 지워진 점검 결과입니다."
        latest = (self._read_result(self._last_path()) or {}).get("run_id")
        with self.lock:
            try:
                shutil.rmtree(folder)
            except OSError as exc:
                return f"점검 결과를 지우지 못했습니다: {exc.strerror or exc}. 결과 파일을 연 프로그램을 닫고 다시 누르십시오."
            if latest == folder.name:
                self._republish_latest()
        if (self.result or {}).get("run_id") == folder.name:
            self._load_last()            # 보던 결과를 지웠으면 남은 것 중 최근 점검을 보인다
            self._sync_review()
        return None

    def _republish_latest(self):
        """출력 폴더의 제출용 사본을 남은 점검 중 가장 최근 것으로 바꾼다. 남은 점검이 없으면 사본도 지운다."""
        runs = self.list_runs()
        src = Path(self.out_dir) / "runs" / runs[0]["run_id"] if runs else None
        for name in PUBLISHED:
            dst = Path(self.out_dir) / name
            try:
                if src and (src / name).is_file():
                    shutil.copy2(src / name, dst)
                elif dst.is_file():
                    dst.unlink()
            except OSError:
                pass

    def _save_last(self, res):
        doc = dict(res)
        for k in ("started", "finished"):
            if hasattr(doc.get(k), "isoformat"):
                doc[k] = doc[k].isoformat(timespec="seconds")
        doc["entry_url"] = self.entry_url
        try:
            write_json(self._last_path(), doc)
        except OSError as exc:
            res["save_error"] = str(res.get("save_error", "")) + f" 마지막 결과 저장 실패: {exc}"

    def _run_options(self, doc):
        """저장된 점검의 설정(run.json). 옛 결과라 알 수 없으면 None."""
        if not (doc or {}).get("run_id"):
            return None
        try:
            meta = json.loads((result_dir(self.out_dir, doc) / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return meta.get("options")

    def _history(self, prev, res, options=None):
        """같은 주소를 지난번에 점검했으면 무엇이 새로 생기고 무엇이 사라졌는지 견준다."""
        # 한쪽이라도 도중에 멈춘 점검이면 '사라짐'이 조치 때문인지 덜 봐서인지 알 수 없다
        if (not prev or prev.get("entry_url") != self.entry_url or prev.get("stopped")
                or res.get("stopped")):
            return None
        # 한쪽에서만 켠 검사(추가 유형·첨부파일 등)의 항목은 견주지 않는다.
        # 끈 검사의 광고가 '사라짐'으로, 새로 켠 검사의 광고가 '새로 생김'으로 보이면 안 된다
        prev_opts = self._run_options(prev)
        uncompared = (sorted(k for k in CHECK_KINDS if check_enabled(prev_opts, k) != check_enabled(options, k))
                      if prev_opts is not None and options is not None else [])
        prev_rows = {finding_key(f): f for f in prev.get("findings", [])}
        now = {finding_key(f) for f in res["findings"]} | {text_key(f) for f in res["findings"]}
        # 이번에 열지 못한 페이지의 광고는 '사라짐'이 아니라 '확인 못 함'이다
        opened = {page_key(u) for u in res.get("pages", [])}
        # 제외한 iframe·첨부 등 때문에 검출이 줄었을 수 있는 페이지의 광고는 삭제로 해석하지 않는다.
        # 제외 주소 자체는 열지 않았으므로 opened 에 없다. 다른 페이지는 평소처럼 견준다.
        cov = res.get("coverage") or {}
        excluded_pages = {page_key(u) for u in cov.get("excluded_pages") or []}
        if cov.get("excluded_count") and "excluded_pages" not in cov:
            excluded_pages = opened         # 옛 결과(페이지별 기록 없음)는 전부 비교하지 않는다
        gone = [{k: f.get(k) for k in ("url", "location", "technique", "extra_finding", "evidence_text")}
                for key, f in prev_rows.items()
                if key not in now and text_key(f) not in now and page_key(f["url"]) in opened
                and page_key(f["url"]) not in excluded_pages and check_kind(f) not in uncompared]
        finished = prev.get("finished")
        return {
            "prev_finished": finished.isoformat(timespec="seconds")
            if hasattr(finished, "isoformat") else finished,
            "prev_count": len(prev_rows),
            "prev_keys": sorted(set(prev_rows) | {text_key(f) for f in prev_rows.values()}),
            "gone_count": len(gone),
            "gone": gone[:GONE_SHOW],
            "uncompared": [CHECK_KINDS[k] for k in uncompared],
            "uncompared_keys": uncompared,
            "excluded_page_count": len(excluded_pages),
        }

    # ---- 조치 상태 ----
    def set_exclusion(self, body):
        with self.lock:
            if self.closing or self.running or self.rechecking or self.search.running:
                raise ValueError("진행 중인 점검·검색이 끝난 뒤 제외 목록을 바꾸십시오.")
            if body.get("action") == "remove":
                self.review_store.set_exclusion(body.get("url"), run_id=(self.result or {}).get("run_id"))
                return
            if body.get("action") != "add" or body.get("confirmed") is not True:
                raise ValueError("원문을 직접 확인했는지 표시하십시오.")
            keys = body.get("keys")
            if not isinstance(keys, list) or not keys or any(not isinstance(k, str) for k in keys):
                raise ValueError("확인한 결과 항목을 선택하십시오.")
            findings = {finding_key(f): f for f in (self.result or {}).get("findings", [])}
            if any(k not in findings for k in keys):
                raise ValueError("현재 결과에 없는 항목입니다. 결과를 다시 여십시오.")
            urls = {exclusion_key(findings[k]["url"]) for k in keys}
            if len(urls) != 1:
                raise ValueError("제외할 페이지 주소를 하나씩 확인하십시오.")
            reason = body.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("직접 확인한 사유를 입력하십시오.")
            patches = {k: dict(status="fp", carried=False, tkey=text_key(findings[k])) for k in keys}
            self.review_store.set_exclusion(urls.pop(), reason,
                                            (self.result or {}).get("run_id"), patches)
            self.review = self.review_store.load()

    def save_review(self, key, patch):
        if "status" in patch:
            # 담당자가 직접 정했으면 이어받은 표시와 지난 조치 확인 결과는 뗀다 (확인된 조치완료와 구분한다)
            patch = dict(patch, carried=False, check="", checked_at="")
        self.save_reviews({key: patch})
        return self.review[key]

    def save_reviews(self, patches, drop=()):
        """여러 항목의 상태와 이력을 한 트랜잭션으로 저장한 뒤 화면 상태를 갱신한다."""
        with self.lock:
            patches = {key: dict(patch) for key, patch in patches.items()}
            for key, patch in patches.items():
                if key in self.tkeys:
                    patch.setdefault("tkey", self.tkeys[key])
            self.review = self.review_store.update(
                patches, drop, (self.result or {}).get("run_id"))


    def _sync_review(self):
        """새 결과의 항목마다 지난 조치 상태를 찾아 붙인다.

        - 옛 키(문구 없이 위치만)로 저장한 기록은 새 키로 옮긴다 (한 번만)
        - 위치가 밀렸어도 같은 페이지·같은 문구를 오탐 처리했으면 오탐 처리를 이어 간다.
          '조치완료'는 잇지 않는다. 지운 광고가 다른 자리에 다시 올라온 것이기 때문이다.
        """
        if not self.result:
            self.tkeys = {}
            return
        findings = self.result.get("findings", [])
        self.tkeys = {finding_key(f): text_key(f) for f in findings}
        fp_by_text = {}
        for row in self.review.values():
            if row.get("status") == "fp" and row.get("tkey"):
                fp_by_text.setdefault(row["tkey"], row)
        patches, drop = {}, []
        for f in findings:
            key, tkey = finding_key(f), text_key(f)
            if key in self.review:
                if "tkey" not in self.review[key]:
                    patches[key] = {"tkey": tkey}
                continue
            old = self.review.get(legacy_key(f))
            if old is not None:
                patches[key] = dict(old, tkey=tkey)
                drop.append(legacy_key(f))
            elif tkey in fp_by_text:
                src = fp_by_text[tkey]
                patches[key] = {"status": "fp", "memo": src.get("memo", ""), "tkey": tkey,
                                "carried": True}
        if patches or drop:
            try:
                self.save_reviews(patches, drop)
            except OSError:
                pass

    # ---- 조치 확인 ----
    def start_recheck(self):
        """광고가 나왔던 페이지만 다시 열어 지워졌는지 확인한다.
        미조치 항목과, 담당자가 직접 조치완료로 적었지만 아직 확인하지 않은 항목을 본다."""
        if self.closing or self.running or self.rechecking or self.search.running or not self.result:
            return False
        exclusions = ScanExclusions(self.review_store.exclusions())
        def unconfirmed(f):
            rev = self.review.get(finding_key(f), {})
            st = rev.get("status", "open")
            return st == "open" or (st == "done" and rev.get("check") not in ("gone", "deleted"))
        targets = [f for f in self.result["findings"] if unconfirmed(f) and not exclusions.contains(f["url"])]
        if not targets:
            return False
        self.rechecking, self.recheck_done, self.recheck_total = True, 0, 0
        self.error, self.stop_requested = None, False
        threading.Thread(target=self._run_recheck, args=(targets,), daemon=True).start()
        return True

    def _run_recheck(self, targets):
        def progress(n, total, url):
            self.recheck_done, self.recheck_total, self.current = n, total, url
        try:
            res = recheck(targets, politeness=self.result.get("politeness"), progress=progress,
                          should_stop=lambda: self.stop_requested,
                          excluded_urls=self.review_store.exclusions())
            now = time.strftime("%Y-%m-%dT%H:%M:%S")
            patches = {}
            for i, outcome in res.items():
                patch = {"check": outcome, "checked_at": now}
                if outcome in ("gone", "deleted"):
                    patch["status"] = "done"
                elif outcome == "present":
                    patch["status"] = "open"     # 조치완료로 적었지만 광고가 아직 있다
                patches[finding_key(targets[i])] = patch
            self.save_reviews(patches)
        except Exception as exc:
            self.error = f"조치 확인 실패: {type(exc).__name__}: {exc}"
        finally:
            self.rechecking = False
            self.stop_requested = False

    # ---- 탐지 키워드 ----
    def edit_keywords(self, body):
        """화면에서 보낸 키워드 추가·삭제·끄기를 반영한다. 실패하면 사람이 읽을 문장을 돌려준다."""
        if self.running:
            return "점검 중에는 키워드를 바꿀 수 없습니다. 점검이 끝난 뒤 바꾸십시오."
        action, cat = body.get("action"), body.get("cat")
        names = {c[0]: c[1] for c in lexicon.CATEGORIES}
        with self.lock:
            st = self.keywords
            if action == "reset":
                st = {"added": {c: [] for c in names}, "off": {c: [] for c in names}}
            else:
                if cat not in names:
                    return "분류를 고르십시오."
                word = lexicon.clean_word(body.get("word", ""))
                if action == "add":
                    if len(word) < 2:
                        return "두 글자 이상 넣으십시오. 한 글자는 정상 글에 너무 자주 나옵니다."
                    home, builtin = lexicon.find_category(word)
                    for c in names:
                        if word in st["added"][c]:
                            home, builtin = c, False
                    if home:
                        tail = " 꺼 두었다면 목록에서 다시 켜십시오." if builtin else ""
                        return f"'{word}'{josa(word, '은', '는')} 이미 '{names[home]}'에 있습니다.{tail}"
                    st["added"][cat].append(word)
                elif action == "remove":
                    if word in st["added"][cat]:
                        st["added"][cat].remove(word)
                elif action == "toggle":
                    off = st["off"][cat]
                    if body.get("on"):
                        if word in off:
                            off.remove(word)
                    elif word not in off:
                        off.append(word)
                else:
                    return "알 수 없는 요청입니다."
            lexicon.save_state(self.out_dir, st)
            self.keywords = st
        return None

    # ---- 탐지 ----
    def start(self, url, max_pages, cloaking=False, attachments=False, search_reflect=False,
              index_urls=None, subdomains=False, polite=False, check_links=False, ocr_images=False,
              extra_types=False, capture=False, snapshots=False, time_limit=1500, continuation=None):
        if self.closing or self.running or self.rechecking or self.search.running:
            return False
        self.started_at = time.time()
        self.time_limit = time_limit
        self.run_exclusions = self.review_store.exclusions()
        self.run_clock = RunClock()
        self.running, self.error, self.notice, self.stop_requested = True, None, None, False
        self.scan_status = {}
        # 지난 점검 목록에서 옛 결과를 보던 중이어도 '새로 생김·사라짐'은 가장 최근 점검과 견준다
        prev = self._read_result(self._last_path()) or self.result
        if prev is not None:
            prev = dict(prev, entry_url=prev.get("entry_url") or self.entry_url)
        self.entry_url, self.pages_done, self.current = url, 0, ""
        self.prev_result = prev
        self.result = None
        threading.Thread(target=self._run,
                         args=(url, max_pages, cloaking, attachments, search_reflect, index_urls,
                               subdomains, polite, check_links, ocr_images, extra_types, capture, snapshots, time_limit, continuation),
                         daemon=True).start()
        return True

    def _run(self, url, max_pages, cloaking=False, attachments=False, search_reflect=False,
             index_urls=None, subdomains=False, polite=False, check_links=False, ocr_images=False,
              extra_types=False, capture=False, snapshots=False, time_limit=1500, continuation=None):
        def progress(n, page_url):
            self.pages_done, self.current = n, page_url
        archive = None
        primary_only = not (extra_types or cloaking or attachments or search_reflect or
                            check_links or ocr_images or index_urls)
        try:
            options = dict(max_pages=max_pages, cloaking=cloaking, attachments=attachments,
                           search_reflect=search_reflect, index_urls=index_urls,
                           subdomains=subdomains, polite=polite, check_links=check_links,
                           ocr_images=ocr_images, primary_only=primary_only, evidence=capture, snapshots=snapshots, time_limit=time_limit,
                           excluded_urls=getattr(self, "run_exclusions", self.review_store.exclusions()))
            if continuation:
                options.update(resume_mod.validate(continuation[1]['resume_state'], url)['settings'])
            archive = RunArchive(self.out_dir, url, options, clock=getattr(self, "run_clock", None) or RunClock())
            if continuation:
                archive.inherit(*continuation)
            worker_options = {k: v for k, v in options.items() if k not in ('evidence', 'snapshots')}
            res = run_scan(url, archive, **worker_options, progress=progress,
                           resume_state=continuation[1]['resume_state'] if continuation else None,
                           status=lambda info: setattr(self, "scan_status", info),
                           evidence_dir=str(archive.path / "evidence") if capture else None,
                           snapshot_dir=str(archive.path / "snapshots") if snapshots else None,
                           should_stop=lambda: self.stop_requested)
            res["run_id"] = archive.id
            if res.get("stopped") == "user" and not res["pages"] and not res.get("resume_state"):
                archive.cancel(res)
                if self.prev_result:
                    self._restore_prev()      # 아무것도 보기 전에 멈췄으면 지난 결과를 그대로 둔다
                # 화면이 되살린 지난 결과를 이번 점검 결과로 보이지 않게 알린다
                self.notice = ("첫 페이지를 열기 전에 중지해 점검한 페이지가 없습니다. "
                               "결과는 저장하지 않았습니다."
                               + (" 지난 점검 결과는 그대로 남아 있습니다." if self.prev_result else ""))
                return
            # 진입 주소부터 열리지 않은 경우(차단·장애)는 지난 결과로 덮지 않고 그대로 알린다
            res["history"] = None if continuation else self._history(self.prev_result, res, archive.meta.get("options"))
            try:
                archive.finish(res, review=self.review)
            except OSError as exc:
                # 쓰기 금지 폴더 등에서 실행했다. 점검한 결과까지 버리지 않고 화면에 남기며 알린다
                res["save_error"] = (f"결과 파일을 쓰지 못했습니다({self.out_dir}): {exc.strerror or exc}. "
                                     "쓰기 가능한 폴더(바탕화면 등)로 프로그램을 옮겨 다시 점검하십시오.")
            self._save_last(res)
            self.result = res
            self._sync_review()
        except Exception as exc:            # 화면에 그대로 보여주기 위해 붙잡아 둔다
            self.error = f"{type(exc).__name__}: {exc}"
            if archive is not None:
                try:
                    archive.fail(exc)
                except OSError as save_exc:
                    self.error += f"; 실패 기록 저장 오류: {save_exc}"
            if self.prev_result:
                self._restore_prev()
        finally:
            self.ended_at = time.time()
            self.running = False

    def _restore_prev(self):
        self.result = self.prev_result
        self.entry_url = self.prev_result.get("entry_url", "")
        self._sync_review()

    # ---- 화면에 넘길 형태 ----
    def _evidence_image(self, key):
        if not key or not self.result:
            return None
        row = self.result.get("evidence", {}).get(key) or {}
        return f"/api/evidence/{row['image']}" if row.get("image") else None

    def payload(self):
        if not self.result:
            return {"findings": [], "pages": [], "meta": None}
        rows = []
        exclusions = ScanExclusions(self.review_store.exclusions())
        hist = self.result.get("history") or None
        prev_keys = set(hist["prev_keys"]) if hist else None
        uncompared = set(hist.get("uncompared_keys") or []) if hist else set()
        # 증거 사진·페이지 사본은 고급 설정에서 켠 점검에만 남는다. 비어 있는 까닭을 화면이 알리도록 넘긴다 (옛 결과는 None)
        opts = self._run_options(self.result)
        saved = {k: (bool(opts.get(k)) if opts is not None else None) for k in ("evidence", "snapshots")}
        # 고급 설정에서 켠 추가 검사. 꺼진 검사의 광고는 0건이어도 깨끗하다는 뜻이 아니므로 화면이 함께 알린다
        checks_on = ([k for k in SWITCHES if check_enabled(opts, k)] if opts is not None else None)
        for i, f in enumerate(self.result["findings"], 1):
            key = finding_key(f)
            rev = self.review.get(key, {"status": "open", "memo": ""})
            rows.append({
                "id": f"f_{i:03d}", "key": key, "url": f["url"],
                "location": f["location"], "technique": f["technique"],
                "evidence_text": f["evidence_text"], "normalized": f["normalized"],
                "reason": f["reason"], "keywords": f["keywords"],
                "extra_finding": f.get("extra_finding"),
                "grade": f.get("grade"), "guide": f.get("guide"),
                "judgement": f.get("judgement"),
                "status": rev.get("status", "open"), "memo": rev.get("memo", ""),
                "scan_excluded": exclusions.contains(f["url"]),
                "check": rev.get("check"), "checked_at": rev.get("checked_at"),
                "is_new": prev_keys is not None and check_kind(f) not in uncompared
                          and not prev_keys.intersection((key, text_key(f), legacy_key(f))),
                "carried": rev.get("carried", False),
                "evidence_key": f.get("evidence_key"),
                "evidence_image": self._evidence_image(f.get("evidence_key")),
                "outer_html": (self.result.get("evidence", {})
                               .get(f.get("evidence_key"), {}).get("html")),
            })
        return {
            "findings": rows,
            "pages": self.result["pages"],
            "meta": {
                "entry_url": self.entry_url,
                **self.resume_info(self.result),
                "session_number": self.result.get('session_number', 1),
                "scan_id": self.result.get('scan_id', self.result.get('run_id')),
                "total_elapsed": self.result.get('total_elapsed', self.result['elapsed']),
                "elapsed_sec": round(self.result["elapsed"], 2),
                "process_elapsed_sec": self.result.get("process_elapsed"),
                "engine_elapsed_sec": self.result.get("engine_elapsed", self.result["elapsed"]),
                "analyzed_count": (self.result.get("coverage") or {}).get("analyzed"),
                "timings": self.result.get("timings"),
                "page_count": len(self.result["pages"]),
                "out_dir": self.out_dir,
                "run_id": self.result.get("run_id"),
                "archive_dir": str(result_dir(self.out_dir, self.result)),
                "finished_at": (self.result["finished"].isoformat(timespec="seconds")
                                if hasattr(self.result.get("finished"), "isoformat")
                                else self.result.get("finished")),
                "stopped": self.result.get("stopped"),
                "save_error": self.result.get("save_error"),
                "coverage": self.result.get("coverage"),
                "coverage_lines": report.coverage_lines(self.result),
                "ocr_unavailable": (self.result.get("ocr_images") or {}).get("unavailable") or None,
                "politeness": self.result.get("politeness"),
                "saved": saved,
                "checks_on": checks_on,
                "recheck": last_recheck(rows),
                "history": ({k: v for k, v in hist.items() if k not in ("prev_keys", "uncompared_keys")}
                            if hist else None),
            },
        }


# 기본 4종(닮은꼴·자모·투명·화면 밖) 밖의 검사. 점검 설정에서 켜야 찾으므로 설정이 다른 점검끼리는 견주지 않는다
CHECK_KINDS = {"extra": "추가 광고 유형", "attachments": "첨부파일", "ocr_images": "그림 속 글자",
               "cloaking": "크롤러 위장", "search_reflect": "검색창", "index_urls": "색인 목록",
               "check_links": "연계 링크"}
# 그중 고급 설정의 켜고 끄는 칸 (색인 목록은 파일을 넣는 칸이라 뺀다)
SWITCHES = [k for k in CHECK_KINDS if k != "index_urls"]
_KIND_OF = {"ATTACHMENT_AD": "attachments", "IMAGE_TEXT_AD": "ocr_images", "CLOAKING": "cloaking",
            "SEARCH_REFLECT": "search_reflect", "SEARCH_INDEXED": "index_urls", "LINK_HIJACKED": "check_links"}


def check_kind(f):
    """이 항목을 찾은 검사. 기본 4종이면 None (항상 견준다)."""
    if f.get("technique") != "ETC":
        return None
    return _KIND_OF.get((f.get("extra_finding") or "").split("(")[0], "extra")


def check_enabled(options, kind):
    options = options or {}
    if kind == "extra":
        return not options.get("primary_only", True)
    return bool(options.get(kind))


def last_recheck(rows):
    """마지막 조치 확인의 시각과 결과별 건수 (저장된 항목별 기록에서 계산해 다시 켜도 남는다)."""
    at = max((r["checked_at"] for r in rows if r.get("checked_at")), default=None)
    if not at:
        return None
    counts = {}
    for r in rows:
        if r.get("checked_at") == at:
            counts[r["check"]] = counts.get(r["check"], 0) + 1
    return {"at": at, "counts": counts}


def _text_of(f):
    text = " ".join((f.get("normalized") or f.get("evidence_text") or "").split())
    # 등급 이름을 바꾸기 전에 저장한 조치 상태도 같은 항목으로 찾도록 옛 이름으로 맞춘다
    return text.replace("[피해 발생 또는 광고 확인됨]", "[피해 확인]")


def josa(word, a, b):
    """낱말 끝 글자에 받침이 있으면 a(은·을), 없으면 b(는·를). 한글이 아니면 받침 없음으로 본다."""
    last = (word or " ").strip()[-1:] or " "
    return a if "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 else b


def _hash(raw):
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def finding_key(f):
    """재탐지해도 같은 검출을 같은 항목으로 인식하기 위한 키.

    문구까지 넣는다. 오탐 처리한 자리에 진짜 광고가 새로 들어오면 다른 항목으로 다시 알려야 한다.
    """
    return _hash(f"{f['url']}|{f['location']}|{f['technique']}|{_text_of(f)}")


def text_key(f):
    """자리를 빼고 페이지·기법·문구로만 알아보는 키.

    게시판에 글이 더해져 순번(nth-of-type)이 밀리면 위치가 달라진다. 같은 페이지의 같은 문구면
    같은 검출로 보고 오탐 처리를 이어 간다 (recheck.still_there 와 같은 기준).
    """
    return _hash(f"{page_key(f['url'])}|{f['technique']}|{f.get('extra_finding') or ''}|{_text_of(f)}")


def legacy_key(f):
    """문구를 키에 넣기 전(2026-10-02 이전)에 저장한 조치 상태를 찾기 위한 옛 키."""
    return _hash(f"{f['url']}|{f['location']}|{f['technique']}")


class Handler(BaseHTTPRequestHandler):
    session: Session = None

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        s = self.session
        if u.path == '/api/search/key':
            return self._send(200, json.dumps(s.search.key_state()), headers={'Cache-Control': 'no-store'})
        if u.path == '/api/search/terms':
            from search_terms import groups, MAX_TERMS
            return self._send(200, json.dumps({'groups': groups(), 'max': MAX_TERMS}, ensure_ascii=False))
        if u.path == '/api/search/status':
            return self._send(200, json.dumps(s.search.status(), ensure_ascii=False))
        if u.path == '/api/search/runs':
            return self._send(200, json.dumps({'runs': s.search.list_runs()}, ensure_ascii=False),
                              headers={'Cache-Control': 'no-store'})
        if u.path == '/api/search/health':
            force = parse_qs(u.query).get('refresh') == ['1']
            return self._send(200, json.dumps(s.search.health(force), ensure_ascii=False))
        if u.path.startswith('/api/search/files/'):
            path = s.search.artifact(unquote(u.path[len('/api/search/files/'):]))
            if path is None:
                return self._send(404, '{}')
            types = {'.html':'text/html; charset=utf-8', '.json':'application/json; charset=utf-8',
                     '.csv':'text/csv; charset=utf-8', '.txt':'text/plain; charset=utf-8', '.png':'image/png'}
            headers = {'X-Content-Type-Options': 'nosniff'}
            if path.name != 'report.html':
                headers['Content-Security-Policy'] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:"
            return self._send(200, path.read_bytes(), types[path.suffix.lower()], headers)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as fp:
                return self._send(200, fp.read(), "text/html; charset=utf-8")
        if u.path == "/favicon.ico":
            # 앱 창의 제목표시줄·작업표시줄 아이콘은 이 파일을 따라간다.
            icon = asset_path("훤히.ico")
            if icon:
                with open(icon, "rb") as fp:
                    return self._send(200, fp.read(), "image/x-icon")
            return self._send(204, b"", "image/x-icon")
        if u.path.startswith("/fonts/"):
            # 화면 글꼴(Pretendard, SIL OFL)을 동봉해 폐쇄망·글꼴 미설치 PC 에서도 같게 보이게 한다
            font = asset_path(os.path.join("fonts", os.path.basename(u.path)))
            if font and font.endswith(".woff2"):
                with open(font, "rb") as fp:
                    return self._send(200, fp.read(), "font/woff2")
            return self._send(404, b"", "text/plain")
        if u.path == "/api/status":
            return self._send(200, json.dumps({
                "running": s.running, "error": s.error,
                "detail": s.scan_status,
                "pages_done": s.pages_done, "current": s.current,
                "time_limit": getattr(s, "time_limit", None),
                "elapsed": round((time.time() if s.running else s.ended_at) - s.started_at, 1)
                if s.started_at else 0,
                "has_result": s.result is not None, "notice": s.notice,
                "stopping": s.running and s.stop_requested,
                "rechecking": s.rechecking, "recheck_done": s.recheck_done,
                "recheck_total": s.recheck_total,
            }, ensure_ascii=False))
        if u.path == "/api/ping":
            s.last_ping = time.time()
            return self._send(200, json.dumps({"ok": True}))
        if u.path == "/api/keywords":
            return self._send(200, json.dumps({"categories": lexicon.describe(s.keywords)},
                                              ensure_ascii=False))
        if u.path == "/api/exclusions":
            return self._send(200, json.dumps({"exclusions": s.review_store.exclusions()}, ensure_ascii=False))
        if u.path == "/api/history.html":
            return self._send(200, history_html(s.out_dir, s.review_store, finding_key),
                              "text/html; charset=utf-8")
        if u.path == "/api/result":
            return self._send(200, json.dumps(s.payload(), ensure_ascii=False))
        if u.path == "/api/runs":
            return self._send(200, json.dumps({"runs": s.list_runs()}, ensure_ascii=False))
        if u.path == "/api/page":
            qs = parse_qs(u.query)
            target = (qs.get("u") or [""])[0]
            sel = (qs.get("sel") or [None])[0]
            name = (s.result or {}).get("snapshots", {}).get(page_key(target)) if s.result else None
            path = os.path.join(result_dir(s.out_dir, s.result), "snapshots", os.path.basename(name)) if name else None
            if not path or not os.path.exists(path):
                return self._send(404, "<p style='font:14px sans-serif;padding:20px'>"
                                       "누리집 화면 사본은 고급 설정의 '방문 페이지 사본 저장'을 "
                                       "켜고 점검해야 저장됩니다.</p>", "text/html; charset=utf-8")
            with open(path, encoding="utf-8", errors="replace") as fp:
                html = fp.read()
            page, csp = snapshot_mod.build(html, target, sel)
            return self._send(200, page, "text/html; charset=utf-8",
                              {"Content-Security-Policy": csp})
        if u.path.startswith("/api/evidence/"):
            name = os.path.basename(u.path)
            path = os.path.join(result_dir(s.out_dir, s.result), "evidence", name)
            if not name.endswith(".png") or not os.path.exists(path):
                return self._send(404, json.dumps({"error": "not found"}))
            with open(path, "rb") as fp:
                return self._send(200, fp.read(), "image/png")
        if u.path == "/api/report.html":
            return self._send(200, report_html.build(s.payload(), s.review),
                              "text/html; charset=utf-8")
        if u.path == "/api/export.csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["번호", "페이지 URL", "위치(CSS 선택자)", "은닉 기법",
                        "판정 근거", "검출 원문", "정규화 결과", "매칭 표현", "조치 상태", "메모",
                        "지난 점검 대비", "조치 확인", "판정 등급", "등급 근거"])
            for r in s.payload()["findings"]:
                level = r.get("judgement") or {}
                w.writerow([csv_text(value) for value in [r["id"], r["url"], r["location"], r["technique"], r["reason"],
                            r["evidence_text"], r["normalized"], " ".join(r["keywords"]),
                            {"open": "미확인", "done": "확인", "fp": "오탐"}.get(r["status"], r["status"]),
                            r["memo"], "새로 생김" if r["is_new"] else "",
                            report_html.check_text(r),
                            label_of(level) or r.get("grade") or "", " / ".join(level.get("reasons") or [])]])
            # 엑셀에서 한글이 깨지지 않도록 BOM 을 붙인다 (result.json 과 달리 CSV 는 무관)
            return self._send(200, buf.getvalue().encode("utf-8-sig"),
                              "text/csv; charset=utf-8")
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("JSON 객체가 아닙니다")
        except Exception:
            return self._send(400, json.dumps({"error": "요청 형식이 올바르지 않습니다."},
                                              ensure_ascii=False))
        try:
            return self._post(urlparse(self.path), self.session, body)
        except Exception as exc:            # 잘못된 값 하나로 화면 요청이 응답 없이 끊기지 않게
            return self._send(400, json.dumps({"error": f"요청을 처리하지 못했습니다: {exc}"},
                                              ensure_ascii=False))

    def _post(self, u, s, body):
        if s.closing and u.path not in ("/api/quit", "/api/bye", "/api/stop", "/api/search/stop"):
            return self._send(409, json.dumps({"error": "결과를 저장하고 프로그램을 종료하는 중입니다."}, ensure_ascii=False))
        if u.path == '/api/search/key':
            # 외부 웹페이지가 로컬 키를 변경하지 못하도록 실제 서버 포트의 로컬 Origin만 허용한다.
            port = self.server.server_address[1]
            allowed = (f'http://127.0.0.1:{port}', f'http://localhost:{port}')
            if self.headers.get('Origin') not in allowed or self.headers.get_content_type() != 'application/json':
                return self._send(403, '{"error":"로컬 프로그램 화면에서 변경하세요."}')
            with s.lock:
                if s.running or s.rechecking or s.search.running:
                    return self._send(409, '{"error":"진행 중인 작업이 끝난 뒤 키를 변경하세요."}')
                try:
                    result = s.search.edit_key(body)
                except ValueError as exc:
                    return self._send(400, json.dumps({'error': str(exc)}, ensure_ascii=False))
                except Exception:
                    return self._send(500, '{"error":"키를 저장하지 못했습니다. 설정 폴더의 쓰기 권한을 확인하세요."}')
            return self._send(200, json.dumps(result), headers={'Cache-Control': 'no-store'})
        if u.path == '/api/search/runs/open':
            # 보던 검색 결과를 바꾸는 요청이므로 키 변경과 같이 로컬 화면의 Origin만 허용한다.
            port = self.server.server_address[1]
            allowed = (f'http://127.0.0.1:{port}', f'http://localhost:{port}')
            if self.headers.get('Origin') not in allowed or self.headers.get_content_type() != 'application/json':
                return self._send(403, '{"error":"로컬 프로그램 화면에서 여십시오."}')
            from ui.search_job import RunBusy
            with s.lock:
                if s.running or s.rechecking:
                    return self._send(409, json.dumps({'error': '점검이 끝난 뒤 지난 검색을 여십시오.'}, ensure_ascii=False))
                try:
                    opened = s.search.open_run(body.get('run_id'))
                except RunBusy as exc:
                    return self._send(409, json.dumps({'error': str(exc)}, ensure_ascii=False))
                except LookupError as exc:
                    return self._send(404, json.dumps({'error': str(exc)}, ensure_ascii=False))
                except ValueError as exc:
                    return self._send(400, json.dumps({'error': str(exc)}, ensure_ascii=False))
            return self._send(200, json.dumps({'ok': True, 'run_id': opened}, ensure_ascii=False))
        if u.path in ('/api/search/start', '/api/search/resume'):
            with s.lock:
                ok = not (s.closing or s.running or s.rechecking or s.search.running)
                if ok:
                    ok = s.search.start(body, resume=u.path.endswith('/resume'))
            return self._send(200 if ok else 409, json.dumps({'ok':ok, 'error':None if ok else '다른 점검 또는 검색이 진행 중입니다.'}, ensure_ascii=False))
        if u.path == '/api/search/stop':
            s.search.stop.set()
            return self._send(200, '{"ok":true}')
        if u.path == "/api/recheck":
            with s.lock:
                ok = s.start_recheck()
            return self._send(200 if ok else 409, json.dumps(
                {"ok": ok, "error": None if ok else "확인할 미확인 항목이 없거나 이미 진행 중입니다."},
                ensure_ascii=False))
        if u.path == "/api/stop":
            if s.running or s.rechecking:
                s.stop_requested = True
            return self._send(200, json.dumps({"ok": True}))
        if u.path == "/api/scan/resume":
            try:
                with s.lock:
                    ok = s.start_resume(body.get('run_id'), scan_seconds(body.get('time_minutes', 25)))
            except (ValueError, OSError, KeyError) as exc:
                return self._send(409, json.dumps({'error': str(exc)}, ensure_ascii=False))
            return self._send(200 if ok else 409, json.dumps({'ok': ok}))
        if u.path == "/api/scan":
            if not str(body.get("url") or "").strip():
                return self._send(400, json.dumps({"error": "점검할 누리집 주소를 입력하십시오."}, ensure_ascii=False))
            url = normalize_entry(body.get("url") or "")
            if not url.startswith(("http://", "https://")):
                return self._send(400, json.dumps({"error": "URL은 http:// 또는 https:// 로 시작해야 합니다."},
                                                  ensure_ascii=False))
            try:
                time_limit = scan_seconds(body.get('time_minutes', 25))
            except ValueError as exc:
                return self._send(400, json.dumps({'error': str(exc)}, ensure_ascii=False))
            # 화면에서 고른 Search Console CSV 는 글자 인코딩을 모르므로 원본 바이트(base64)로 받는다
            index_urls = None
            if body.get("index_csv"):
                index_urls = parse_urls(decode_index(base64.b64decode(body["index_csv"])))
            with s.lock:
                ok = s.start(url, int(body.get("max_pages") or DEFAULT_MAX_PAGES),
                             cloaking=bool(body.get("cloaking")),
                             attachments=bool(body.get("attachments", False)),
                             search_reflect=bool(body.get("search_reflect", False)),
                             index_urls=index_urls,
                             subdomains=bool(body.get("subdomains")),
                             polite=bool(body.get("polite")),
                             check_links=bool(body.get("check_links")),
                             ocr_images=bool(body.get("ocr_images")), extra_types=bool(body.get("extra_types")),
                             capture=bool(body.get("capture")), snapshots=bool(body.get("snapshots")), time_limit=time_limit)
            return self._send(200 if ok else 409,
                              json.dumps({"ok": ok, "error": None if ok else "이미 점검이 진행 중입니다."},
                                         ensure_ascii=False))
        if u.path in ("/api/runs/open", "/api/runs/delete"):
            act = s.open_run if u.path.endswith("open") else s.delete_run
            err = act(body.get("run_id"))
            if err:
                return self._send(409, json.dumps({"error": err}, ensure_ascii=False))
            return self._send(200, json.dumps({"ok": True, "has_result": s.result is not None},
                                              ensure_ascii=False))
        if u.path == "/api/bye":
            s.bye_at = time.time()
            return self._send(200, json.dumps({"ok": True}))
        if u.path == "/api/quit":
            self.server.stop_work()
            try:
                self._send(200, json.dumps({"ok": True}))
            finally:
                self.server.request_shutdown()
            return
        if u.path == "/api/keywords":
            err = s.edit_keywords(body)
            if err:
                return self._send(400, json.dumps({"error": err}, ensure_ascii=False))
            return self._send(200, json.dumps({"categories": lexicon.describe(s.keywords),
                                               "word": lexicon.clean_word(body.get("word", ""))},
                                              ensure_ascii=False))
        if u.path == "/api/keywords/test":
            # 같은 문장이 숨긴 글일 때와 화면에 그대로 보이는 글일 때 판정이 다르므로 둘 다 보여 준다
            text = str(body.get("text") or "")[:2000]
            hidden, shown = classify(text), classify(text, strict=True)
            return self._send(200, json.dumps({
                "normalized": hidden["normalized"], "evidence": hidden["evidence"],
                "hidden": hidden["is_ad"], "visible": shown["is_ad"],
                "homoglyph": hidden["homoglyph"], "jamo": hidden["jamo"],
                # 숨긴 글이면 숨김 자체가 근거가 되므로 은닉 이유를 하나 넣어 등급을 매긴다
                "hidden_level": judge(hidden, ["숨긴 글로 가정"]) if hidden["is_ad"] or hidden.get("review_candidate") else None,
                "visible_level": judge(shown) if shown["is_ad"] or shown.get("review_candidate") else None,
            }, ensure_ascii=False))
        if u.path == "/api/review":
            if not body.get("key"):
                return self._send(400, json.dumps({"error": "key 가 없습니다."}, ensure_ascii=False))
            row = s.save_review(str(body["key"]), {k: str(body[k]) for k in ("status", "memo") if k in body})
            return self._send(200, json.dumps(row, ensure_ascii=False))
        if u.path == "/api/exclusions":
            s.set_exclusion(body)
            return self._send(200, json.dumps({"ok": True}, ensure_ascii=False))
        return self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *a):
        pass


def _watchdog(session, httpd, grace=180, bye_grace=3, wake_gap=10):
    """화면이 닫히면 프로세스를 정리한다.

    창을 닫으면 화면이 /api/bye 를 보낸다. 새로고침이면 몇 초 안에 ping 이 다시 오므로
    그때는 끝내지 않는다. 신호를 못 보내고 꺼진 경우(강제 종료 등)는 ping 이 끊긴 지
    grace 초 뒤에 끝낸다. 창을 닫았으면 탐지 중이라도 끝낸다(결과를 볼 화면이 없다).

    PC 가 절전에서 깨어나면 마지막 신호가 몇 분 전으로 보여, 화면이 신호를 다시 보내기도 전에
    꺼져 버린다('Failed to fetch'). 1초마다 도는 이 반복이 wake_gap 초 넘게 건너뛰었으면 절전으로 보고
    신호 대기를 새로 시작한다. 최소화한 창의 타이머가 늦춰지는 경우도 있어 grace 를 넉넉히 둔다.
    """
    prev = time.time()
    while True:
        time.sleep(1)
        now = time.time()
        if now - prev > wake_gap and session.last_ping:
            session.last_ping = max(session.last_ping, now)
        prev = now
        if session.bye_at and session.last_ping < session.bye_at and now - session.bye_at > bye_grace:
            httpd.request_shutdown()
            return
        if session.running or session.rechecking or session.search.running:
            continue
        if session.last_ping and now - session.last_ping > grace:
            httpd.request_shutdown()
            return


class _Server(ThreadingHTTPServer):
    # Windows 에서는 주소 재사용을 켜 두면 다른 프로세스가 쓰는 포트에도 붙어 버린다.
    # 그러면 이전에 띄운 훤히(구버전일 수도 있다)의 화면이 열린다. 반드시 꺼 둔다.
    allow_reuse_address = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = self.RequestHandlerClass.session
        self.close_window = lambda: None
        self.exit_thread = None
        self.exit_lock = threading.Lock()
        self.exited = False

    def stop_work(self):
        # Keep the server and scan supervisor alive until partial results are sealed.
        with self.session.lock:
            self.session.closing = True
            self.session.stop_requested = True
            self.session.search.stop.set()
        while self.session.running or self.session.rechecking or self.session.search.running:
            time.sleep(0.05)

    def register_window(self, close):
        with self.exit_lock:
            self.close_window = close
            exited = self.exited
        if exited:
            close()

    def request_shutdown(self):
        with self.exit_lock:
            if self.exit_thread is not None:
                return
            self.exit_thread = threading.Thread(target=self._finish_shutdown, daemon=True)
            self.exit_thread.start()

    def _finish_shutdown(self):
        self.stop_work()
        self.shutdown()
        with self.exit_lock:
            self.exited = True
            close = self.close_window
        close()


def _bind(port, tries=20):
    """지정한 포트가 쓰이고 있으면 다음 빈 포트를 쓴다."""
    for p in range(port, port + tries):
        try:
            return _Server(("127.0.0.1", p), Handler)
        except OSError:
            continue
    return _Server(("127.0.0.1", 0), Handler)       # 운영체제가 고른 빈 포트


def serve(out_dir, port=8900, open_browser=True):
    Handler.session = Session(out_dir)
    httpd = _bind(port)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/"

    # 화면(창)은 주 스레드를 써야 하므로 서버를 뒤로 보낸다.
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    print(f"점검 도구를 시작합니다: {url}")

    try:
        if open_browser:
            native = native_ui.available() and native_ui.run(
                url, "훤히 — 공공 누리집 숨은 불법광고 점검 도구",
                on_close=httpd.request_shutdown, register_close=httpd.register_window)
            if native:
                httpd.request_shutdown()
            else:
                window = open_app_window(url)
                httpd.register_window(window.close)
                print("  화면 방식:", window.name)
                threading.Thread(target=_watchdog, args=(Handler.session, httpd), daemon=True).start()
        server_thread.join()
    except KeyboardInterrupt:
        httpd.request_shutdown()
    finally:
        httpd.request_shutdown()
        httpd.exit_thread.join()
        server_thread.join()
        httpd.server_close()
