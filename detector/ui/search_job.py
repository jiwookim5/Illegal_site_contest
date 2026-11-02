"""기존 웹 UI에서 실행하는 검색 보조 작업 상태."""
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from search_assist import pipeline
from search_discovery import now as iso_now, registrable_domain, target_host
from review_store import ReviewStore
from search_terms import MAX_TERMS, expand
from search_providers import (CONTINUE_REASONS, check_health, load_keys, resume_searches, retry_errors,
                              key_status, store_key)


class RunBusy(ValueError):
    """검색 중에는 지난 검색을 열 수 없다."""


class SearchJob:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.root = Path(out_dir).resolve() / 'search_results'
        self.config = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
        self.running = False
        self.stop = threading.Event()
        self.logs = []
        self.error = ''
        self.folder = None
        self.run = None
        self.submission = None        # 마지막 검색의 제출 JSON 요약 (건수·유형·파일 위치)
        self.thread = None
        self.scope = None             # 마지막으로 시작한 검색의 범위 {scope, query_host, entry_host, subdomains}
        self.scope_run = None         # self.scope 가 속한 검색의 run (self.run 이 이것이면 self.scope 를 그대로 쓴다)
        self.live = []                # 진행 중인 검색의 질의 기록(수집기가 갱신하는 사전 그대로)
        self.plan = None              # 진행 표시용 {terms, started_at, started(monotonic), ended(monotonic)|None}
        self.health_lock = threading.Lock()
        self.health_cache = None      # (확인 시각 monotonic, 결과)

    HEALTH_TTL = 300      # 연결 상태는 5분간 캐시한다

    def key_state(self):
        with self.health_lock:
            return key_status(self.config/'search.env')

    def edit_key(self, body):
        action = body.get('action')
        if action not in ('save', 'delete'):
            raise ValueError('키 저장 또는 삭제를 선택하세요.')
        if self.running:
            raise ValueError('검색 완료 후 키를 변경하세요.')
        with self.health_lock:
            store_key(self.config/'search.env', body.get('key', '') if action == 'save' else None)
            self.health_cache = None
            return key_status(self.config/'search.env')

    def health(self, force=False, probe=None):
        with self.health_lock:
            cached = self.health_cache
            if cached and not force and time.monotonic() - cached[0] < self.HEALTH_TTL:
                return dict(cached[1], cached=True)
            keys = load_keys(self.config/'search.env')
            result = check_health(keys, probe) if probe else check_health(keys)
            result['checked_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
            self.health_cache = (time.monotonic(), result)
            return dict(result, cached=False)

    ERROR_STATES = ('error', 'pending', 'cancelled')

    def _fresh(self):
        """새 검색이 진행 중이면 수집기가 갱신하는 질의 기록을 그대로 보여 준다(끝나기 전에는 self.run 이 없다)."""
        return self.running and self.plan is not None and self.plan['ended'] is None

    def _in_flight(self, q):
        return self.running and q.get('end_reason') == '처리 중'

    def _scope_info(self):
        if self.scope and (self.running or (self.run is not None and self.run is self.scope_run)):
            return dict(self.scope)
        if not self.run:
            return None
        # 디스크에서 연 지난 검색: 검색과 함께 저장된 값을 쓰고, 예전 검색은 입력한 호스트만 본 것으로 간주한다.
        target = str(self.run.get('target', ''))
        return dict(scope=self.run.get('scope') or 'host', query_host=target,
                    entry_host=str(self.run.get('entry_host') or target), subdomains=bool(self.run.get('subdomains')))

    def _progress(self):
        plan = self.plan
        if not plan:
            return None
        terms = plan['terms']
        index = {t: i for i, t in enumerate(terms)}
        live = list(self.live)
        last = live[-1] if live else None
        flying = bool(last) and self._in_flight(last)
        words_done = 0
        if last and last.get('term') in index:
            ended = (not flying and last.get('state') != 'cancelled' and last.get('end_reason') != '사용자 중지'
                     and last.get('end_reason') not in CONTINUE_REASONS)
            words_done = index[last['term']] + (1 if ended else 0)
        end = plan['ended'] if plan['ended'] is not None else time.monotonic()
        return dict(terms=list(terms), words_total=len(terms), words_done=words_done,
                    queries_done=sum(1 for q in live if not self._in_flight(q)),
                    started_at=plan['started_at'], elapsed_sec=int(end - plan['started']),
                    finished=plan['ended'] is not None,
                    # 수집기는 질의 기록을 error 상태로 만들어 두고 응답이 오면 바꾼다. 처리 중에는 오류로 보이지 않게 한다
                    current=dict(term=last.get('term'), page=last.get('page'), query=last.get('query'),
                                 state='processing' if last.get('state') == 'error' else last.get('state')) if flying else None)

    def status(self):
        run = self.run or {}
        fresh = self._fresh()
        queries = [dict(q) for q in self.live] if fresh else run.get('queries', [])
        count = sum(q.get('new_urls') or 0 for q in queries) if fresh else len(run.get('results', []))
        errors = [dict(term=q.get('term'), page=q.get('page'), state=q.get('state'),
                       reason=q.get('error') or q.get('end_reason') or '', detail=q.get('error_detail'))
                  for q in queries if q.get('state') in self.ERROR_STATES and not self._in_flight(q)]
        return dict(running=self.running, stopping=self.running and self.stop.is_set(),
                    error=self.error, logs=list(self.logs), count=count,
                    queries=queries, submission=None if self.running else self.submission, report=bool(self.folder and (self.folder/'report.html').exists()),
                    resumable=any(q.get('search_id') and q.get('state') in ('pending', 'processing', 'cancelled')
                                  for q in run.get('queries', [])),
                    scope=self._scope_info(), errors=errors, progress=self._progress())

    def start(self, body, resume=False):
        if self.running:
            return False
        if resume:
            if not self.run or not self.folder:
                raise ValueError('회수할 검색 결과가 없습니다.')
            args = None
            if self.run is not self.scope_run:
                self.scope = None        # 다른 검색의 범위를 이 검색의 것으로 보여 주지 않는다
        else:
            entry = target_host(str(body.get('site', '')))
            # domain(기본): 등록 도메인 전체(하위 도메인 포함), host: 입력한 호스트만(하위 도메인은 subdomains 옵션)
            scope = body.get('scope')
            scope = 'domain' if scope is None else scope
            if scope not in ('domain', 'host'):
                raise ValueError('검색 범위는 domain 또는 host 로 지정하세요.')
            host = registrable_domain(entry) if scope == 'domain' else entry
            subdomains = True if scope == 'domain' else body.get('subdomains') is True
            # 유형별 고정 단어 + (고급) 직접 입력·이번 점검에서 찾은 단어
            terms = expand(body.get('groups', []), str(body.get('terms', '')).splitlines())
            engines = body.get('engines', [])
            pages = int(body.get('pages', 2))
            if not terms:
                raise ValueError('검색할 광고 유형을 하나 이상 고르거나 단어를 입력하세요.')
            if len(terms) > MAX_TERMS or any(len(t)>100 for t in terms) or not 1 <= pages <= 10:
                raise ValueError(f'광고단어는 모두 합쳐 {MAX_TERMS}개 이하(각 100자 이하), 페이지는 1~10으로 맞추세요. '
                                 f'지금 {len(terms)}개입니다.')
            if not isinstance(engines, list) or not engines or any(e != 'google' for e in engines):
                raise ValueError('검색엔진을 선택하세요.')
            keys = load_keys(self.config/'search.env')
            if not keys['SERPAPI_API_KEY']:
                raise ValueError('search.env에 SERPAPI_API_KEY를 설정하세요.')
            args = dict(site=host, terms=terms, engines=engines, pages=pages, mode='api',
                        keys_path=self.config/'search.env', dorks_path=self.config/'search_dorks.json',
                        output=self.root, inspect=body.get('inspect') is True,
                        subdomains=subdomains, include_omitted=body.get('include_omitted') is True,
                        entry_host=entry, scope=scope, on_query=self._track,
                        excluded_urls=ReviewStore(self.out_dir).exclusions())
        self._begin(args)
        return True

    def retry_errors(self):
        """state 가 error 인 질의만 같은 페이지를 다시 요청한다(검색 호출량을 쓴다). 시작하면 True, 이미 진행 중이면 False."""
        if self.running:
            return False
        if not self.run or not self.folder:
            raise ValueError('다시 시도할 검색 결과가 없습니다.')
        if not any(q.get('state') == 'error' for q in self.run.get('queries', [])):
            raise ValueError('다시 시도할 오류 질의가 없습니다.')
        if not load_keys(self.config/'search.env')['SERPAPI_API_KEY']:
            raise ValueError('search.env에 SERPAPI_API_KEY를 설정하세요.')
        self._begin('retry')
        return True

    def _begin(self, args):
        if isinstance(args, dict):        # 새 검색: 진행 정보와 범위를 초기화한다
            terms = list(dict.fromkeys(t.strip() for t in args['terms'] if t.strip()))
            self.live = []
            self.plan = dict(terms=terms, started_at=iso_now(), started=time.monotonic(), ended=None)
            self.scope = dict(scope=args['scope'], query_host=args['site'], entry_host=args['entry_host'],
                              subdomains=args['subdomains'])
            self.scope_run = None
        self.running = True
        self.error = ''
        self.submission = None
        self.logs = []
        self.stop.clear()
        self.thread = threading.Thread(target=self._work, args=(args,), daemon=True)
        self.thread.start()

    def _track(self, record):
        if not self.live or self.live[-1] is not record:
            self.live.append(record)

    def _log(self, message):
        self.logs = (self.logs + [str(message)])[-100:]

    def _work(self, args):
        try:
            if args is None:
                resume_searches(self.run, self.folder, load_keys(self.config/'search.env'), self._log, self.stop.is_set)
            elif args == 'retry':
                retry_errors(self.run, self.folder, load_keys(self.config/'search.env'), self._log, self.stop.is_set)
            else:
                self.run, self.folder = pipeline(**args, progress=self._log, should_stop=self.stop.is_set)
                self.scope_run = self.run
            from search_submission import publish, summary
            written = publish(self.run, self.folder, self.root.parent, self._log)
            self.submission = dict(summary(self.run), file=str(written),
                                   merged=Path(written).parent == self.root.parent)
        except Exception as exc:
            # 외부 예외에 인증 URL이 포함될 수 있으므로 원문은 UI에 내보내지 않는다.
            self.error = f'검색 작업을 완료하지 못했습니다 ({type(exc).__name__}). 설정과 저장 폴더를 확인하세요.'
        finally:
            if isinstance(args, dict) and self.plan:
                self.plan['ended'] = time.monotonic()
            self.running = False

    def artifact(self, relative):
        target_folder = self.folder
        # 1. relative 경로의 첫 번째 구성요소가 지난 검색 폴더명인 경우 지원 (/api/search/files/<run_id>/report.html)
        rel_path = Path(relative)
        parts = rel_path.parts
        if parts:
            first = parts[0]
            candidate = (self.root / first).resolve()
            if candidate.parent == self.root.resolve() and candidate.is_dir() and (candidate / 'results.json').is_file():
                target_folder = candidate
                relative = str(Path(*parts[1:])) if len(parts) > 1 else 'report.html'
        # 2. 현재 활성 폴더가 없으면 가장 최근 검색 폴더를 기본으로 사용
        if not target_folder:
            runs = self.list_runs()
            if runs:
                candidate = (self.root / runs[0]['id']).resolve()
                if candidate.parent == self.root.resolve() and candidate.is_dir():
                    target_folder = candidate
        if not target_folder:
            return None
        base = target_folder.resolve()
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            return None
        # 설정·키 파일을 제공하지 않고 생성된 보고서/증거만 연다.
        if path.suffix.lower() not in ('.html', '.json', '.csv', '.txt', '.png'):
            return None
        return path

    # ---- 지난 검색 기록 (디스크의 out/search_results/<대상>_<날짜>_<시각>_<해시>/) ----
    MAX_RUNS = 50

    def _run_summary(self, folder):
        """results.json 에서 목록에 필요한 값만 뽑는다. 파일이 바뀌지 않았으면 캐시를 쓴다. 손상·없음은 None."""
        path = folder/'results.json'
        try:
            stat = path.stat()
            key = (stat.st_mtime_ns, stat.st_size)
            cache = self.__dict__.setdefault('_run_cache', {})
            hit = cache.get(folder.name)
            if hit and hit[0] == key:
                return hit[1]
            run = json.loads(path.read_text(encoding='utf-8-sig'))
            if not (isinstance(run, dict) and isinstance(run.get('results'), list)
                    and isinstance(run.get('queries'), list)):
                return None
            submission = None
            try:
                extra = json.loads((folder/'result_extra.json').read_text(encoding='utf-8-sig'))
                if isinstance(extra.get('findings'), list):
                    submission = len(extra['findings'])
            except (OSError, ValueError, AttributeError):
                pass
            info = dict(id=folder.name, target=str(run.get('target', '')), started_at=str(run.get('started_at', '')),
                        queries=len(run['queries']), urls=len(run['results']), submission=submission,
                        has_report=(folder/'report.html').is_file(), stopped=bool(run.get('stopped')))
        except (OSError, ValueError, TypeError):
            return None
        cache[folder.name] = (key, info)
        return info

    def list_runs(self):
        """results.json 이 있는 지난 검색을 최근 것부터 최대 MAX_RUNS 건."""
        try:
            folders = [p for p in self.root.iterdir() if p.is_dir() and (p/'results.json').is_file()]
        except OSError:
            return []
        runs = []
        for folder in folders:
            info = self._run_summary(folder)
            if info:
                runs.append(info)
        runs.sort(key=lambda r: (r['started_at'], r['id']), reverse=True)
        runs = runs[:self.MAX_RUNS]
        live = {r['id'] for r in runs}
        for name in [n for n in self.__dict__.get('_run_cache', {}) if n not in live]:
            del self._run_cache[name]
        return runs

    def open_run(self, run_id):
        """지난 검색 하나를 현재 검색 결과로 연다. 진행 중이면 RunBusy, 잘못된 id 는 ValueError, 없으면 LookupError."""
        if self.running:
            raise RunBusy('검색이 끝난 뒤 지난 검색을 여십시오.')
        # 폴더 이름만 허용한다: 경로 구분자·상위 경로·드라이브 표기를 거부하고 root 직속 폴더인지 다시 확인한다.
        if (not isinstance(run_id, str) or not run_id or run_id in ('.', '..') or run_id != Path(run_id).name
                or any(c in run_id for c in '/\\:\0') or '..' in run_id):
            raise ValueError('열 검색 기록이 올바르지 않습니다.')
        folder = (self.root/run_id).resolve()
        if folder.parent != self.root.resolve() or not folder.is_dir() or not (folder/'results.json').is_file():
            raise LookupError('검색 기록을 찾지 못했습니다. 지워졌을 수 있습니다.')
        try:
            run = json.loads((folder/'results.json').read_text(encoding='utf-8-sig'))
            if not (isinstance(run, dict) and isinstance(run.get('results'), list) and isinstance(run.get('queries'), list)):
                raise ValueError('형식 오류')
            from search_submission import summary
            submission = dict(summary(run), file=str(folder/'result_extra.json'), merged=False)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise ValueError('검색 기록 파일이 손상되어 열 수 없습니다.')
        self.run, self.folder, self.submission = run, folder, submission
        self.error = ''
        self.logs = [f'지난 검색을 열었습니다: {folder.name}']
        return folder.name
