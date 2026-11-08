"""SQLite-backed persistence for single-instance ClipConvert production jobs.

The SQLite file and MEDIA_DIR must be on the SAME Railway persistent volume.
Do not run multiple replicas against this SQLite database or local media files.
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


class StateStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS records(
                kind TEXT NOT NULL,
                id TEXT NOT NULL,
                payload TEXT NOT NULL,
                changed REAL NOT NULL,
                PRIMARY KEY(kind,id)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS records_by_kind ON records(kind)")
            db.execute("""CREATE TABLE IF NOT EXISTS daily_counters(
                day TEXT NOT NULL,
                metric TEXT NOT NULL,
                amount INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(day,metric)
            )""")
            db.commit()

    def _connection(self):
        return sqlite3.connect(self.path, timeout=15)

    def load(self, kind):
        with self.lock, self._connection() as db:
            rows = db.execute("SELECT id,payload FROM records WHERE kind=?", (kind,)).fetchall()
        result = {}
        for key, payload in rows:
            try:
                result[key] = json.loads(payload)
            except (ValueError, TypeError):
                continue
        return result

    def put(self, kind, key, value):
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with self.lock, self._connection() as db:
            db.execute(
                """INSERT INTO records(kind,id,payload,changed) VALUES(?,?,?,?)
                   ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,
                   changed=excluded.changed""",
                (kind, str(key), payload, time.time()))
            db.commit()

    def drop(self, kind, key):
        with self.lock, self._connection() as db:
            db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, str(key)))
            db.commit()

    def prune(self, kind, older_than_seconds):
        threshold=time.time()-float(older_than_seconds)
        with self.lock, self._connection() as db:
            result=db.execute("DELETE FROM records WHERE kind=? AND changed < ?",
                              (kind,threshold))
            db.commit()
            return result.rowcount


    def messages(self, limit=100):
        with self.lock, self._connection() as db:
            rows = db.execute(
                "SELECT id,payload FROM records WHERE kind='contact' ORDER BY changed DESC LIMIT ?",
                (max(1, min(200, int(limit))),)).fetchall()
        messages = []
        for key, payload in rows:
            try:
                messages.append({"id": key, **json.loads(payload)})
            except (ValueError, TypeError):
                pass
        return messages

    def increment(self, metric, amount=1):
        if not isinstance(metric,str) or len(metric)>96:
            raise ValueError("Invalid metric name")
        day=datetime.now(timezone.utc).date().isoformat()
        with self.lock, self._connection() as db:
            db.execute(
                """INSERT INTO daily_counters(day,metric,amount) VALUES(?,?,?)
                   ON CONFLICT(day,metric) DO UPDATE SET amount=amount+excluded.amount""",
                (day,metric,int(amount)))
            db.commit()

    def daily_summary(self, days=14):
        days=max(1,min(31,int(days)))
        threshold=(datetime.now(timezone.utc).date()-timedelta(days=days-1)).isoformat()
        with self.lock, self._connection() as db:
            rows=db.execute(
                "SELECT day,metric,amount FROM daily_counters WHERE day >= ? ORDER BY day",
                (threshold,)).fetchall()
        result={}
        for day,metric,value in rows:
            result.setdefault(day,{})[metric]=int(value)
        return result


def database_path(media):
    return Path(os.getenv("STATE_DB", str(Path(media) / "state.sqlite3")))
