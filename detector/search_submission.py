"""검색 노출 근거를 공모전 추가 유형 스키마로 내보낸다."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from fileio import write_json
from findings import classify
from report import TOOL_VERSION


def same_target(url1, url2):
    """두 URL이 같은 점검 대상 호스트(포트 포함 여부 고려)인지 확인한다."""
    p1 = urlsplit(url1 if '://' in url1 else 'https://' + url1)
    p2 = urlsplit(url2 if '://' in url2 else 'https://' + url2)
    if p1.netloc == p2.netloc:
        return True
    h1 = (p1.hostname or '').lower()
    h2 = (p2.hostname or '').lower()
    if not h1 or not h2 or h1 != h2:
        return False
    if p1.port and p2.port:
        return p1.port == p2.port
    return True


def document(run):
    started = run.get('started_at') or datetime.now().astimezone().isoformat(timespec='seconds')
    finished = max([started] + [run[k] for k in ('rechecked_at', 'finished_at', 'resumed_at', 'retried_at') if run.get(k)],
                   key=datetime.fromisoformat)
    elapsed = max(0, (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds())
    target = run['target']
    rows = []
    seen = set()
    for row in run.get('results', []):
        from search_discovery import in_scope, target_host
        if not in_scope(row['url'], target_host(target), run.get('subdomains', False)):
            continue
        # 검색어가 들어간 URL만으로는 검색에 광고가 노출됐다고 판정하지 않는다.
        params = [(k, v) for k, v in parse_qsl(urlsplit(row['url']).query, keep_blank_values=True)
                  if v and classify(v)['is_ad']]
        for source in row.get('sources', []):
            title, snippet = source.get('title', ''), source.get('snippet', '')
            # 검색 노출 제목·요약은 화면 노출 글이므로 strict=True로 판정해 단순 공공 예방·단속 공고 오탐을 방지한다.
            if not classify(title + '\n' + snippet, strict=True)['is_ad']:
                continue
            status = row.get('status', '미검사')
            code = 'SEARCH_INDEXED_AD(검색 노출 광고)'
            if row.get('http_status') in (404, 410):
                code = 'SEARCH_REMOVED_AD(삭제 응답 URL의 검색 노출 잔존)'
            elif params:
                code = 'SEARCH_PARAMETER_AD(광고 파라미터 URL의 검색 노출)'
            elif row.get('findings') and status != '확인 불가':
                code = 'SEARCH_LIVE_AD(현재 페이지 광고의 검색 노출)'
            # API 결과에는 실제 검색 DOM 선택자가 없으므로 기본 위치를 구성하되,
            # SEARCH_LIVE_AD 인 경우 현재 페이지에서 실제 검출된 위치(CSS 선택자)를 병기한다.
            base_location = (f"검색 결과: {source.get('engine', '')}; "
                             f"검색 URL={source.get('search_url', '')}; 페이지={source.get('page', '')}; "
                             f"대상 링크={row['url']}")
            live_locs = [f['location'] for f in row.get('findings', []) if f.get('location')]
            if code.startswith('SEARCH_LIVE_AD') and live_locs:
                location = f"{base_location}; 웹페이지 위치={live_locs[0]}"
            else:
                location = base_location
            key = (row['url'], location)
            if key in seen:
                continue
            seen.add(key)
            evidence = (f"검색 제목: {title}\n검색 요약: {snippet}\n"
                        f"검색 시각: {source.get('searched_at', '')}\n"
                        f"현재 상태: {status}; HTTP={row.get('http_status', '미확인')}\n"
                        f"현재 확인 시각: {row.get('checked_at', '')}\n"
                        f"현재 상태 설명: {row.get('detail', '')}")
            if params:
                evidence += '\n광고 파라미터: ' + json.dumps(params, ensure_ascii=False)
            for finding in row.get('findings', []):
                evidence += f"\n현재 페이지 근거 [{finding.get('location', '')}]: {finding.get('evidence_text', '')}"
            rows.append(dict(id=f'e_search_{len(rows)+1:03d}', url=row['url'], is_violation=True,
                             location=location, evidence_text=evidence, technique='ETC', extra_finding=code))
    # 검색 범위를 등록 도메인으로 넓혀도 제출 파일은 사용자가 입력한 주소로 합쳐진다(publish 가 netloc 으로 비교).
    entry = run.get('entry_url') or run.get('entry_host') or target
    return {'meta': dict(topic='TOPIC', entry_url=entry if '://' in entry else 'https://' + entry,
                         started_at=started, finished_at=finished, elapsed_sec=elapsed, tool_version=TOOL_VERSION),
            'findings': rows}


def summary(run):
    """제출 대상 건수와 추가 유형(extra_finding 코드)별 건수. 화면 안내용."""
    types = {}
    for row in document(run)['findings']:
        code = row['extra_finding'].split('(')[0]
        types[code] = types.get(code, 0) + 1
    return {'count': sum(types.values()), 'types': types}


def export(run, folder):
    path = Path(folder) / 'result_extra.json'
    write_json(str(path), document(run), indent=2)
    return path


def publish(run, folder, output, progress=print):
    """검색별 원본을 보존하고 같은 호스트의 제출 사본에만 합친다.

    동일 검색의 회수/재검사는 이전 항목을 교체한다. 기본 점검 아카이브와
    result.json은 수정하지 않는다. 합본의 시간은 최초 점검~검색 종료 구간이다.
    """
    source = export(run, folder)
    doc = document(run)
    path = Path(output) / 'result_extra.json'
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        from output_schema import check
        errors, items, _, _ = check(str(path), extra=True)
        if errors or items:
            raise ValueError('기존 result_extra.json 형식 오류: 원본을 보존합니다.')
        if not same_target(previous['meta']['entry_url'], doc['meta']['entry_url']):
            progress(f'다른 대상의 제출 결과는 보존했습니다. 이번 검색 제출 파일: {source}')
            return source
        prefix = 'e_search_' + hashlib.sha256(str(Path(folder).resolve()).encode()).hexdigest()[:16] + '_'
        rows = [r for r in previous['findings'] if not r['id'].startswith(prefix)]
        for i, row in enumerate(doc['findings'], 1):
            # 다른 검색 실행에서 같은 검색 위치를 다시 확인했으면 최신 근거로 교체한다.
            key = (row['url'], row['location'], row['technique'])
            rows = [old for old in rows if not (old['id'].startswith('e_search_') and
                    (old['url'], old['location'], old['technique']) == key)]
            rows.append(dict(row, id=f'{prefix}{i:03d}'))
        start = min(previous['meta']['started_at'], doc['meta']['started_at'], key=datetime.fromisoformat)
        end = max(previous['meta']['finished_at'], doc['meta']['finished_at'], key=datetime.fromisoformat)
        doc = {'meta': dict(previous['meta'], started_at=start, finished_at=end,
                            elapsed_sec=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()),
               'findings': rows}
    else:
        prefix = 'e_search_' + hashlib.sha256(str(Path(folder).resolve()).encode()).hexdigest()[:16] + '_'
        for i, row in enumerate(doc['findings'], 1):
            row['id'] = f'{prefix}{i:03d}'
    write_json(str(path), doc, indent=2)
    progress(f'공모전 추가 탐지 결과 저장: {path}')
    return path
