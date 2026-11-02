"""Versioned JSON checkpoints; no executable serialization or truncated frontier."""
import hashlib
import json
from pathlib import Path
import sys

VERSION = 1


def pack(value):
    if isinstance(value, dict):
        return {'$dict': [[pack(k), pack(v)] for k, v in value.items()]}
    if isinstance(value, set):
        return {'$set': [pack(v) for v in value]}
    if isinstance(value, tuple):
        return {'$tuple': [pack(v) for v in value]}
    if isinstance(value, list):
        return [pack(v) for v in value]
    return value


def unpack(value):
    if isinstance(value, list):
        return [unpack(v) for v in value]
    if isinstance(value, dict):
        if '$dict' in value:
            return {unpack(k): unpack(v) for k, v in value['$dict']}
        if '$set' in value:
            return set(unpack(v) for v in value['$set'])
        if '$tuple' in value:
            return tuple(unpack(v) for v in value['$tuple'])
        raise ValueError('재개 상태 형식이 잘못되었습니다.')
    return value


def engine_id():
    files = [Path(sys.executable)] if getattr(sys, 'frozen', False) else sorted(Path(__file__).parent.glob('*.py'))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def rules_id():
    import lexicon
    rules = {c[0]: getattr(lexicon, c[0]) for c in lexicon.CATEGORIES}
    return hashlib.sha256(json.dumps(rules, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def capture(obj, names):
    return {name: getattr(obj, name) for name in names} if obj else {}


def restore(obj, values):
    if obj:
        for name, value in values.items():
            setattr(obj, name, value)


def validate(state, entry=None):
    if not isinstance(state, dict) or state.get('version') != VERSION or 'data' not in state:
        raise ValueError('이 기록에는 이어서 점검할 상태가 없습니다. 새 점검을 시작하십시오.')
    if state.get('engine') != engine_id():
        raise ValueError('탐지 프로그램이 변경되어 기존 기록을 이어갈 수 없습니다. 새 점검을 시작하십시오.')
    if entry is not None and state.get('entry') != entry:
        raise ValueError('재개할 누리집 주소가 다릅니다.')
    try:
        saved = unpack(state['data'])
        fields = {'settings': dict, 'seen': set, 'queued': set, 'queue_content': list,
                  'queue_normal': list, 'queue_streak': int, 'low_queue': list, 'retry_queue': list,
                  'results': list, 'visited_pages': list, 'completed_keys': set, 'analyzed': int,
                  'contents': set, 'trap_counts': dict, 'trap_skipped': int, 'login_redirects': list,
                  'login_dirs': set, 'failed': list, 'gone': list, 'retried': set, 'retrying': set,
                  'iframe_urls': set, 'snapshots': dict, 'evidence': dict, 'cloaking_checked': int,
                  'invalid_candidates': int, 'rejected_candidates': list, 'index_done': set,
                  'scope_hosts': set, 'scope_bases': set, 'auxiliary': dict, 'session_probed': set,
                  'deferred_pages': set}
        if not isinstance(saved, dict) or 'current_url' not in saved or any(
                not isinstance(saved.get(k), kind) for k, kind in fields.items()):
            raise ValueError('missing checkpoint fields')
        return saved
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError('재개 상태가 불완전하거나 손상되었습니다. 새 점검을 시작하십시오.') from exc
