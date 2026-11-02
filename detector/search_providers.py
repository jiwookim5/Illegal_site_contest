"""엔진별 dork 질의 및 API 수집. API 키를 결과·오류 메시지에 남기지 않는다."""
import html
import json
import os
import re
import time
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

DEFAULT_TEMPLATES = {"google": ["site:{domain} {term}"]}


def key_status(path):
    environment = bool(os.environ.get('SERPAPI_API_KEY'))
    return {'registered': bool(load_keys(path)['SERPAPI_API_KEY']), 'environment': environment}


def store_key(path, value=None):
    """None은 삭제. 다른 설정은 보존하고 키를 원자적으로 교체한다."""
    if os.environ.get('SERPAPI_API_KEY'):
        raise ValueError('환경변수에서 키를 사용 중입니다. 환경변수를 해제한 뒤 프로그램을 다시 실행하세요.')
    if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,512}', value)):
        raise ValueError('API 키는 공백 없이 영문·숫자·밑줄·하이픈 8~512자로 입력하세요.')
    path = Path(path)
    text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    lines = [line for line in text.splitlines() if line.split('=', 1)[0].strip() != 'SERPAPI_API_KEY']
    if value is not None:
        lines.append('SERPAPI_API_KEY=' + value)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.search-key-', suffix='.tmp', delete=False) as fp:
            temporary = Path(fp.name)
            fp.write('\n'.join(lines) + ('\n' if lines else ''))
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_keys(path):
    """추가 의존성 없이 단순 KEY=VALUE 파일을 읽는다. 셸 실행·변수 확장 없음."""
    values = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"\'')
    return {k: os.environ.get(k) or values.get(k, "") for k in ("SERPAPI_API_KEY",)}


def query_plan(engine, host, terms, templates=None):
    if engine not in DEFAULT_TEMPLATES:
        raise ValueError("지원하지 않는 검색엔진")
    patterns = (templates or DEFAULT_TEMPLATES).get(engine, DEFAULT_TEMPLATES[engine])
    if not isinstance(patterns, list) or not 1 <= len(patterns) <= 10:
        raise ValueError(f"{engine}: dork 템플릿을 1~10건 지정하세요.")
    out = []
    for term in terms:
        for pattern in patterns:
            if not isinstance(pattern, str) or "{domain}" not in pattern or "{term}" not in pattern:
                raise ValueError("각 템플릿에는 {domain}, {term}이 필요합니다.")
            try:
                query = pattern.format(domain=host, term=term)
            except (KeyError, ValueError, IndexError, AttributeError):
                raise ValueError("템플릿에는 {domain}, {term}만 사용할 수 있습니다.") from None
            if len(query) > 500:
                raise ValueError("질의는 500자 이하여야 합니다.")
            if (term, query) not in out:
                out.append((term, query))
    return out


class APIError(Exception):
    def __init__(self, message="", detail=None):
        super().__init__(message)
        self.detail = detail      # 응답의 모양만 담은 사전(키·URL·본문 없음). 원인 확인용


# 다음 페이지를 이어서 요청하는 종료 이유. 단어 진행률에서 단어가 아직 끝나지 않았음을 가리킨다.
CONTINUE_REASONS = ('다음 페이지 진행', '다음 페이지 정보 없음: 추가 페이지 확인')


def safe_text(value, key="", limit=200):
    """오류 문구에서 URL·인증 값을 지우고 길이를 제한한다."""
    text = str(value if value is not None else "")
    if key:
        text = text.replace(key, "[키]")
    text = re.sub(r"(?i)(api_key|key|token)=[^\s&\"']+", r"\1=[제거]", text)
    text = re.sub(r"https?://\S+", "[URL]", text)
    return " ".join(text.split())[:limit]


def response_shape(data, key="", page=None):
    """응답 원문 대신 모양만 남긴다: 최상위 키 이름, organic_results_state, error 문구."""
    if not isinstance(data, dict):
        return {"type": type(data).__name__, "page": page}
    shape = {"keys": [safe_text(k, key, 40) for k in list(data)[:40]], "page": page}
    info = data.get("search_information")
    if isinstance(info, dict) and "organic_results_state" in info:
        shape["organic_results_state"] = safe_text(info["organic_results_state"], key, 80)
    if data.get("error"):
        shape["error"] = safe_text(data["error"], key)
    return shape


class SearchPending(APIError):
    def __init__(self, message, state="pending"):
        super().__init__(message)
        self.state = state


def wait_search(params, key, fetch, search_id=None, on_status=lambda **kw: None,
                should_stop=lambda: False, wait_seconds=300, poll_interval=5,
                clock=time.monotonic, sleep=time.sleep):
    """새 검색은 한 번만 제출한다. 이후에는 같은 ID의 보관 결과만 조회한다."""
    started = clock()
    if should_stop():
        raise SearchPending("사용자가 검색 대기를 중지했습니다.", "cancelled")
    if search_id:
        data = {"search_metadata": {"id": search_id, "status": "Processing"}}
    else:
        data = fetch("https://serpapi.com/search.json?" + urlencode({**params, "async": "true"}), {})
    while True:
        metadata = data.get("search_metadata", {})
        status = metadata.get("status", "Unknown")
        returned_id = metadata.get("id")
        if search_id and returned_id and returned_id != search_id:
            raise APIError("보관 결과의 검색 ID가 요청과 다릅니다.")
        search_id = returned_id or search_id
        on_status(search_id=search_id, provider_status=status, elapsed_seconds=round(clock()-started, 1))
        if status == "Success":
            return data
        if status not in ("Processing", "Queued"):
            raise APIError("SerpApi 검색 실패: 계정 대시보드의 검색 상태를 확인하세요.",
                           {"provider_status": safe_text(status, key, 40), "error": safe_text(data.get("error"), key)
                            } if data.get("error") else {"provider_status": safe_text(status, key, 40)})
        if not search_id or not re.fullmatch(r"[A-Za-z0-9_-]+", search_id):
            raise APIError("처리 중 응답에 올바른 검색 ID가 없습니다.")
        if should_stop():
            raise SearchPending("대기를 중지했습니다. 저장된 검색 ID로 나중에 결과를 회수할 수 있습니다.", "cancelled")
        if clock()-started >= wait_seconds:
            raise SearchPending("처리 대기 한도에 도달했습니다. 검색 실패가 아니며 저장된 ID로 결과를 회수할 수 있습니다.")
        remaining = min(poll_interval, max(0, wait_seconds-(clock()-started)))
        while remaining > 0:
            if should_stop():
                raise SearchPending("대기를 중지했습니다. 저장된 검색 ID는 유지됩니다.", "cancelled")
            step = min(.2, remaining)
            sleep(step)
            remaining -= step
        if clock()-started >= wait_seconds:
            raise SearchPending("처리 대기 한도에 도달했습니다. 저장된 ID로 결과를 회수할 수 있습니다.")
        try:
            data = fetch("https://serpapi.com/searches/" + search_id + ".json?" + urlencode({"api_key": key}), {})
        except APIError:
            raise SearchPending("보관 결과 조회에 실패했습니다. 저장된 ID로 나중에 다시 조회하세요.") from None


def fetch_json(url, headers):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Hwonhi-SearchAssist/1.0", **headers})
        with urllib.request.urlopen(req, timeout=90) as res:
            return json.loads(res.read(8 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 실패 응답에도 검색 ID가 있다. 제공자의 최종 Error 상태를 보존한다.
        if url.startswith("https://serpapi.com/"):
            try:
                data = json.loads(exc.read(1024 * 1024).decode("utf-8"))
                meta = data.get("search_metadata", {})
                if meta.get("status") == "Error" and re.fullmatch(r"[A-Za-z0-9_-]+", str(meta.get("id", ""))):
                    return {"search_metadata": {"id": meta["id"], "status": "Error"}}
            except (OSError, ValueError, AttributeError):
                pass
        raise APIError(f"API HTTP {exc.code}: 인증·잔여 호출량·서비스 상태를 확인하세요.") from None
    except TimeoutError:
        raise APIError("API 응답 시간 초과(90초). 결과 없음이 아니며 나중에 다시 검색하세요.") from None
    except urllib.error.URLError:
        raise APIError("API 네트워크 연결 실패. 네트워크·프록시 설정을 확인하세요.") from None
    except (OSError, ValueError):
        raise APIError("API 연결 또는 응답 형식 오류") from None


def probe_json(url, headers, timeout=10):
    """(HTTP 상태 코드, JSON 또는 None). 연결 실패는 코드 0. 예외 원문(인증 URL 포함 가능)은 내보내지 않는다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Hwonhi-SearchAssist/1.0", **headers})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read(1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read(64 * 1024).decode("utf-8"))
        except (OSError, ValueError):
            return exc.code, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None


def _failed(code):
    """(상태, 안내, 남은 검색 수)."""
    if code == 0:
        return "network_error", "연결 실패 · 네트워크·프록시를 확인하세요", None
    if code in (401, 403):
        return "auth_failed", f"인증 실패 (HTTP {code}) · 키와 서비스 사용 설정을 확인하세요", None
    if code == 429:
        return "quota_exhausted", "이용 한도 초과 (HTTP 429) · 남은 이용 한도를 확인하세요", None
    return "error", f"응답 오류 (HTTP {code}) · 서비스 상태를 확인하세요", None


def check_serpapi(key, probe=probe_json):
    """SerpApi 계정 조회. 검색이 아니라 계정 정보 API라 검색 호출량을 쓰지 않는다."""
    if not key:
        return "not_configured", "SERPAPI_API_KEY 없음", None
    code, data = probe("https://serpapi.com/account.json?" + urlencode({"api_key": key}), {})
    if code != 200 or not isinstance(data, dict) or data.get("error"):
        return _failed(code if code != 200 else 401)
    left = data.get("total_searches_left", data.get("plan_searches_left"))
    left = left if isinstance(left, int) and not isinstance(left, bool) else None
    if left is not None and left <= 0:
        return "quota_exhausted", "이번 달 남은 검색 0회", 0
    if str(data.get("account_status", "Active")).lower() != "active":
        return "auth_failed", "계정이 활성 상태가 아닙니다", left
    return "ok", "정상" + (f" · 남은 검색 {left:,}회" if left is not None else ""), left


def check_health(keys, probe=probe_json):
    """추가 검색에 쓰는 API 연결 상태. 키 값은 결과에 넣지 않는다."""
    providers = []
    for pid, name, engines, check, key in (
            ("serpapi", "구글 (SerpApi)", ["google"], check_serpapi, keys.get("SERPAPI_API_KEY")),):
        state, message, left = check(key, probe)
        providers.append({"id": pid, "name": name, "engines": engines, "state": state,
                          "message": message, "searches_left": left})
    used = [p for p in providers if p["state"] != "not_configured"]
    if not used:
        overall = "not_configured"
    elif all(p["state"] == "ok" for p in used):
        overall = "ok"
    elif any(p["state"] == "ok" for p in used):
        overall = "partial"
    else:
        overall = "down"
    return {"overall": overall, "providers": providers}

def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))


def api_page(engine, query, page, keys, fetch=fetch_json, *, search_id=None,
             on_status=lambda **kw: None, should_stop=lambda: False, include_omitted=False):
    if engine == "google":
        key = keys.get("SERPAPI_API_KEY")
        if not key:
            raise APIError("SERPAPI_API_KEY가 없습니다. search.env에 설정하세요.")
        params = {"engine": engine, "api_key": key, "q": query, "start": (page - 1) * 10, "hl": "ko", "gl": "kr"}
        if include_omitted:
            params['filter'] = 0
        data = wait_search(params, key, fetch, search_id, on_status, should_stop)
        metadata = data.get("search_metadata", {})
        if metadata.get("status") != "Success":
            raise APIError("SerpApi 검색 실패: 계정 대시보드의 검색 상태를 확인하세요.",
                           {"provider_status": safe_text(metadata.get("status"), key, 40)})
        field = "organic_results"
        items = data.get(field, [])
        shape = response_shape(data, key, page)
        if not isinstance(items, list):
            raise APIError("API 결과 목록 형식이 변경되었습니다.", shape)
        end_hint = None
        # 오류 텍스트를 성공 0건으로 바꾸지 않는다. 명시된 정상 무결과만 허용한다.
        if data.get("error") and not items:
            known_empty = "hasn't returned any results" in str(data["error"]).lower()
            if not known_empty:
                raise APIError("검색 결과 해석 오류: API 대시보드를 확인하세요.", shape)
        elif field not in data:
            # error 없이 결과 필드만 없는 응답: 제공자가 비었다고 밝혔거나(Fully empty),
            # 2페이지 이후면 결과가 끝난 것으로 본다. 그 밖의 모양은 오류로 두고 원인을 남긴다.
            state = shape.get("organic_results_state", "")
            if "empty" in state.lower():
                end_hint = f"결과 없음: 제공자 상태 {state}"
            elif page > 1 and not data.get("error"):
                end_hint = f"결과 끝: {page}페이지에 결과 필드 없음(오류 문구 없음)"
            else:
                raise APIError("API 응답에 검색 결과 필드가 없습니다. 무결과로 확정하지 않습니다.", shape)
        hits = []
        for d in items:
            if not isinstance(d, dict):
                continue
            hits.append({"href": d.get("link", ""), "title": plain(d.get("title")),
                         "snippet": plain(d.get("snippet") or d.get("description")), "link_kind": "main"})
            sitelinks = d.get("sitelinks") or {}
            children = sitelinks if isinstance(sitelinks, list) else [s for kind in ("inline", "expanded") for s in sitelinks.get(kind, [])] if isinstance(sitelinks, dict) else []
            for child in children:
                if isinstance(child, dict) and child.get("link"):
                    hits.append({"href": child["link"], "title": plain(child.get("title")),
                                 "snippet": plain(child.get("snippet") or child.get("description")),
                                 "link_kind": "sitelink", "parent_url": d.get("link", "")})
        pagination = data.get("serpapi_pagination") or data.get("pagination") or {}
        more = bool(pagination.get("next") or pagination.get("next_link"))
        # 제공자 원본 전체에는 인증 정보가 포함될 수 있어 증거 필드는 허용 목록만 저장한다.
        evidence = {"provider": "SerpApi", "search_id": metadata.get("id"),
                    "created_at": metadata.get("created_at"), "hits": hits}
        evidence['search_parameters'] = {k: data.get('search_parameters', {}).get(k) for k in
                                         ('engine', 'q', 'query', 'start', 'filter', 'hl', 'gl', 'device')
                                         if k in data.get('search_parameters', {})}
        messages = data.get('dmca_messages') or {}
        evidence['provider_notices'] = [plain(m.get('content')) for m in messages.get('messages', [])
                                        if isinstance(m, dict)] if isinstance(messages, dict) else []
        if end_hint:
            evidence.update(end_hint=end_hint, response_shape=shape)
        return hits, more, evidence
    raise ValueError("지원하지 않는 검색엔진")


def collect_api(host, terms, engines, folder, keys, pages=5, subdomains=False, templates=None,
                progress=print, should_stop=lambda: False, fetch=fetch_json, include_omitted=False,
                on_query=lambda record: None):
    """on_query(record): 질의 기록을 만들 때와 끝낼 때 부른다(진행 표시용). 같은 사전 객체를 넘긴다."""
    from search_discovery import now, merge_hits, save, search_url
    if not terms or len(terms) > 30 or any(not t.strip() or len(t) > 100 for t in terms) or not 1 <= pages <= 10:
        raise ValueError("광고단어 1~30건(각 100자 이하), 페이지 수 1~10을 지정하세요.")
    if not engines or any(e not in DEFAULT_TEMPLATES for e in engines):
        raise ValueError("검색엔진을 확인하세요.")
    plans = {e: query_plan(e, host, terms, templates) for e in engines}
    folder = Path(folder)
    (folder / "search_evidence").mkdir(parents=True, exist_ok=True)
    run = {"target": host, "subdomains": subdomains, "started_at": now(), "queries": [], "results": [],
           "stopped": False, "limit_reached": False, "mode": "api",
           "notes": []}
    for engine in engines:
        for term, query in plans[engine]:
            if should_stop() or run["limit_reached"]:
                break
            seen_pages = set()
            for number in range(1, pages + 1):
                if should_stop() or run["limit_reached"]:
                    break
                record = {"engine": engine, "query": query, "term": term, "page": number,
                          "searched_at": now(), "search_url": search_url(engine, query, number, include_omitted),
                          "include_omitted": include_omitted,
                          "evidence": {}, "state": "error", "error": "", "target_links": 0,
                          "requested_pages": pages, "end_reason": "처리 중"}
                run["queries"].append(record)
                on_query(record)
                progress(f"API {engine} · {query} · {number}페이지")
                def update_status(**status):
                    previous = record.get("provider_status")
                    record.update(status, state="processing")
                    save(run, folder)
                    if previous != status['provider_status']:
                        progress(f"{engine} · {status['provider_status']} · 검색 ID {status['search_id']}")
                try:
                    hits, more, evidence = api_page(engine, query, number, keys, fetch,
                                                    on_status=update_status, should_stop=should_stop, include_omitted=include_omitted)
                    path = f"search_evidence/{len(run['queries']):04d}.json"
                    (folder / path).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
                    record["evidence"] = {"api": path}
                    record['provider_notices'] = evidence.get('provider_notices', [])
                    before = len(run['results'])
                    record["target_links"] = merge_hits(run, hits, record, host, subdomains)
                    record['new_urls'] = len(run['results']) - before
                    record['excluded_links'] = len(hits) - record['target_links']
                    record['duplicate_or_limited_links'] = record['target_links'] - record['new_urls']
                    record['sitelinks'] = sum(h.get('link_kind') == 'sitelink' for h in hits)
                    record['next_page_reported'] = more
                    record["returned_links"] = len(hits)
                    record["state"] = "collected" if record["target_links"] else "no_target_results" if hits else "no_results"
                    if evidence.get('response_shape'):
                        record['error_detail'] = evidence['response_shape']      # 결과 필드 없는 응답의 모양(원인 확인용)
                    signature = frozenset(h["href"] for h in hits)
                    if signature in seen_pages:
                        record["state"] = "repeated_page"
                        record['end_reason'] = '동일 URL 집합 반복'
                        break
                    seen_pages.add(signature)
                    record['end_reason'] = (evidence.get('end_hint') or '정상 무결과' if not hits else 'URL 상한 도달' if run['limit_reached']
                                            else '설정한 페이지 한도 도달' if number == pages
                                            else '다음 페이지 없음' if not more and engine != 'google'
                                            else '다음 페이지 진행' if more else '다음 페이지 정보 없음: 추가 페이지 확인')
                    if not hits or run['limit_reached'] or (not more and engine != 'google'):
                        break
                except SearchPending as exc:
                    record.update(state=exc.state, error=str(exc), end_reason='사용자 중지' if exc.state == 'cancelled' else '결과 회수 대기')
                    progress(f"{engine} · {exc}")
                    break
                except APIError as exc:
                    record["state"] = "error"
                    record["error"] = str(exc)
                    if exc.detail:
                        record['error_detail'] = exc.detail
                    record['end_reason'] = 'API 오류로 해당 질의 종료'
                    progress(f"{engine} 수집 실패: {exc}")
                    break
                finally:
                    save(run, folder)
                    on_query(record)
                for _ in range(5):
                    if should_stop():
                        break
                    time.sleep(.1)
            if should_stop() and run['queries']:
                run['queries'][-1]['end_reason'] = '사용자 중지'
    run.update(finished_at=now(), stopped=should_stop())
    save(run, folder)
    return run


def resume_searches(run, folder, keys, progress=print, should_stop=lambda: False, fetch=fetch_json):
    """저장된 미완료 질의만 회수. 새 검색 제출이나 다음 페이지 검색은 하지 않는다."""
    from search_discovery import now, merge_hits, save
    folder = Path(folder)
    for number, record in enumerate(run['queries'], 1):
        if should_stop():
            break
        if record.get('state') not in ('processing', 'pending', 'cancelled') or not record.get('search_id'):
            continue
        def update_status(**status):
            record.update(status, state='processing')
            save(run, folder)
        try:
            hits, _, evidence = api_page(record['engine'], record['query'], record['page'], keys, fetch,
                                         search_id=record['search_id'], on_status=update_status, should_stop=should_stop)
            path = f'search_evidence/resumed_{number:04d}.json'
            (folder/'search_evidence').mkdir(exist_ok=True)
            (folder/path).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            record.update(evidence={'api':path}, error='', returned_links=len(hits))
            record['provider_notices'] = evidence.get('provider_notices', [])
            before = len(run['results'])
            record['target_links'] = merge_hits(run, hits, record, run['target'], run.get('subdomains', False))
            record.update(new_urls=len(run['results'])-before, excluded_links=len(hits)-record['target_links'],
                          sitelinks=sum(h.get('link_kind') == 'sitelink' for h in hits),
                          duplicate_or_limited_links=record['target_links']-(len(run['results'])-before),
                          end_reason='저장 ID 결과 회수 완료: 추가 페이지는 요청하지 않음')
            record['state'] = 'collected' if record['target_links'] else 'no_target_results' if hits else 'no_results'
            record.pop('error_detail', None)
            if evidence.get('response_shape'):
                record['error_detail'] = evidence['response_shape']
        except SearchPending as exc:
            record.update(state=exc.state, error=str(exc), end_reason='결과 회수 대기 또는 중지')
        except APIError as exc:
            record.update(state='error', error=str(exc), end_reason='API 오류로 해당 질의 종료')
            if exc.detail:
                record['error_detail'] = exc.detail
        finally:
            save(run, folder)
        progress(f"{record['engine']} · {record['state']} · {record['query']}")
    run['resumed_at'] = now()
    save(run, folder)
    return run


def retry_errors(run, folder, keys, progress=print, should_stop=lambda: False, fetch=fetch_json):
    """state 가 error 인 질의만 같은 페이지를 새 검색으로 다시 요청한다. 다음 페이지는 요청하지 않는다.

    다시 요청하면 검색 호출량을 쓴다. 보관 ID 가 있는 pending/cancelled 질의는 resume_searches 가 맡는다.
    """
    from search_discovery import now, merge_hits, save
    folder = Path(folder)
    for number, record in enumerate(run['queries'], 1):
        if should_stop():
            break
        if record.get('state') != 'error':
            continue
        def update_status(**status):
            record.update(status, state='processing')
            save(run, folder)
        record.update(state='processing', end_reason='처리 중', error='')
        record.pop('search_id', None)
        record.pop('error_detail', None)
        try:
            hits, more, evidence = api_page(record['engine'], record['query'], record['page'], keys, fetch,
                                            on_status=update_status, should_stop=should_stop,
                                            include_omitted=bool(record.get('include_omitted')))
            path = f'search_evidence/retry_{number:04d}.json'
            (folder/'search_evidence').mkdir(exist_ok=True)
            (folder/path).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            record.update(evidence={'api': path}, error='', returned_links=len(hits), next_page_reported=more)
            record['provider_notices'] = evidence.get('provider_notices', [])
            before = len(run['results'])
            record['target_links'] = merge_hits(run, hits, record, run['target'], run.get('subdomains', False))
            record.update(new_urls=len(run['results'])-before, excluded_links=len(hits)-record['target_links'],
                          sitelinks=sum(h.get('link_kind') == 'sitelink' for h in hits),
                          duplicate_or_limited_links=record['target_links']-(len(run['results'])-before),
                          end_reason=evidence.get('end_hint') or '오류 질의 재시도 완료: 다음 페이지는 요청하지 않음')
            record['state'] = 'collected' if record['target_links'] else 'no_target_results' if hits else 'no_results'
            if evidence.get('response_shape'):
                record['error_detail'] = evidence['response_shape']
        except SearchPending as exc:
            record.update(state=exc.state, error=str(exc), end_reason='결과 회수 대기 또는 중지')
        except APIError as exc:
            record.update(state='error', error=str(exc), end_reason='API 오류로 해당 질의 종료')
            if exc.detail:
                record['error_detail'] = exc.detail
        finally:
            save(run, folder)
        progress(f"재시도 · {record['state']} · {record['query']} · {record['page']}페이지")
    run['retried_at'] = now()
    save(run, folder)
    return run
