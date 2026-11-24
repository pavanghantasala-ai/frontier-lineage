import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY, source TEXT, lab TEXT, title TEXT, url TEXT UNIQUE, published TEXT,
  fetched_at TEXT, text TEXT, status TEXT DEFAULT 'new', note TEXT
);
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY, item_id INTEGER, data TEXT, status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS versions (
  id INTEGER PRIMARY KEY, parent_id INTEGER, card_id INTEGER, label TEXT, config TEXT, diff TEXT,
  status TEXT, created_at TEXT, promoted_at TEXT
);
CREATE TABLE IF NOT EXISTS evals (
  id INTEGER PRIMARY KEY, version_id INTEGER, model_id TEXT, runs INTEGER, metrics TEXT, per_task TEXT,
  samples TEXT, cost_usd REAL, created_at TEXT
);
CREATE TABLE IF NOT EXISTS verdicts (
  id INTEGER PRIMARY KEY, card_id INTEGER, version_id INTEGER, parent_id INTEGER, verdict TEXT, details TEXT,
  published INTEGER DEFAULT 0, decision TEXT, created_at TEXT, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY, kind TEXT, target TEXT, note TEXT, data TEXT, at TEXT
);
"""

_lock = threading.RLock()
_conn = None


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn():
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


JSON_COLS = {"data", "config", "diff", "metrics", "per_task", "samples", "details"}


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLS & d.keys():
        if d[k] is not None:
            d[k] = json.loads(d[k])
    return d


def q(sql, args=()):
    with _lock:
        return [_row(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def insert(table, **values):
    values = {k: json.dumps(v) if k in JSON_COLS and v is not None else v for k, v in values.items()}
    cols = ",".join(values)
    with _lock:
        cur = conn().execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(values))})", tuple(values.values()))
        conn().commit()
        return cur.lastrowid


def update(table, row_id, **values):
    values = {k: json.dumps(v) if k in JSON_COLS and v is not None else v for k, v in values.items()}
    sets = ",".join(f"{k}=?" for k in values)
    with _lock:
        conn().execute(f"UPDATE {table} SET {sets} WHERE id=?", (*values.values(), row_id))
        conn().commit()


def log(kind, target, note="", data=None):
    insert("ledger", kind=kind, target=str(target), note=note, data=json.dumps(data) if data is not None else None, at=now())


def reset():
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        if DB_PATH.exists():
            DB_PATH.unlink()
