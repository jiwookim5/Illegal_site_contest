"""조치 상태와 변경 이력을 같은 SQLite 트랜잭션으로 저장한다."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from scan_exclusions import exclusion_key


class ReviewStore:
    def __init__(self, out_dir):
        root = Path(out_dir)
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "review.sqlite3"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at TEXT NOT NULL, "
                       "run_id TEXT, key TEXT NOT NULL, before_value TEXT, after_value TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS exclusions (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            if not db.execute("SELECT 1 FROM metadata WHERE key='imported'").fetchone():
                legacy = root / "review_state.json"
                rows = json.loads(legacy.read_text(encoding="utf-8")) if legacy.exists() else {}
                if not isinstance(rows, dict) or any(not isinstance(v, dict) for v in rows.values()):
                    raise ValueError("기존 조치 기록 형식이 올바르지 않습니다. 원본을 확인하십시오.")
                self._update(db, rows, (), "legacy-import")
                db.execute("INSERT INTO metadata VALUES ('imported', '1')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _update(db, patches, drop, run_id):
        at = datetime.now(timezone.utc).isoformat()
        for key in dict.fromkeys([*patches, *drop]):
            row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
            before = json.loads(row[0]) if row else None
            after = None if key in drop else dict(before or {"status": "open", "memo": ""}, **patches[key])
            if before == after:
                continue
            before_json = json.dumps(before, ensure_ascii=False) if before is not None else None
            after_json = json.dumps(after, ensure_ascii=False) if after is not None else None
            db.execute("INSERT INTO events(at,run_id,key,before_value,after_value) VALUES(?,?,?,?,?)",
                       (at, run_id, key, before_json, after_json))
            if after is None:
                db.execute("DELETE FROM state WHERE key=?", (key,))
            else:
                db.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (key, after_json))

    def update(self, patches, drop=(), run_id=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._update(db, patches, tuple(drop), run_id)
        return self.load()

    def load(self):
        with self.connect() as db:
            return {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM state")}

    @staticmethod
    def exclusions_at(out_dir):
        """저장소가 있는 폴더의 제외 목록. 없으면 빈 목록을 돌려주고 파일을 만들지 않는다."""
        return ReviewStore(out_dir).exclusions() if (Path(out_dir) / "review.sqlite3").is_file() else []

    def exclusions(self):
        with self.connect() as db:
            return [json.loads(v) for (v,) in db.execute("SELECT value FROM exclusions ORDER BY key")]

    def set_exclusion(self, url, reason=None, run_id=None, patches=None):
        """reason=None이면 해제. 오탐 상태와 제외 기록·이력을 한 번에 저장한다."""
        key = exclusion_key(url)
        if reason is not None and (not isinstance(reason, str) or not reason.strip() or len(reason) > 1000):
            raise ValueError("직접 확인한 사유를 1~1000자로 입력하십시오.")
        at = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            before = db.execute("SELECT value FROM exclusions WHERE key=?", (key,)).fetchone()
            after = (dict(kind="exclusion", url=key, reason=reason.strip(), created_at=at,
                          run_id=run_id) if reason is not None else None)
            if before or after:
                encoded = json.dumps(after, ensure_ascii=False) if after else None
                db.execute("INSERT INTO events(at,run_id,key,before_value,after_value) VALUES(?,?,?,?,?)",
                           (at, run_id, "exclude:" + key, before[0] if before else None, encoded))
                if after:
                    db.execute("INSERT OR REPLACE INTO exclusions VALUES(?,?)", (key, encoded))
                else:
                    db.execute("DELETE FROM exclusions WHERE key=?", (key,))
            self._update(db, patches or {}, (), run_id)

    def history(self, key=None, limit=200):
        with self.connect() as db:
            sql = "SELECT id,at,run_id,key,before_value,after_value FROM events"
            args = ()
            if key is not None:
                sql += " WHERE key=?"
                args = (key,)
            rows = db.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
            return [dict(id=i, at=at, run_id=run, key=k,
                         before=json.loads(b) if b else None, after=json.loads(a) if a else None)
                    for i, at, run, k, b, a in rows]
