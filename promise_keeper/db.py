"""SQLite storage. One table, one file on disk, nothing leaves the machine."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from . import config

ISO = "%Y-%m-%dT%H:%M:%S"
SCHEMA = """
CREATE TABLE IF NOT EXISTS promises (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    commitment    TEXT NOT NULL,
    person        TEXT,
    deadline      TEXT,
    deadline_text TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | done
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    source_text   TEXT
)
"""


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime(ISO) if dt else None


def _parse(s: str | None) -> datetime | None:
    return datetime.strptime(s, ISO) if s else None


def _to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("deadline", "created_at", "completed_at"):
        d[key] = _parse(d[key])
    return d


def init_db(db_path=None) -> None:
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(SCHEMA)


def add_promise(commitment: str, person: str | None = None, deadline: datetime | None = None,
                deadline_text: str | None = None, source_text: str | None = None,
                db_path=None, now: datetime | None = None) -> int:
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO promises (commitment, person, deadline, deadline_text, created_at, source_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (commitment.strip(), (person or "").strip() or None, _fmt(deadline), deadline_text,
             _fmt(now or datetime.now()), source_text),
        )
        return cur.lastrowid


def list_promises(status: str | None = None, db_path=None) -> list[dict]:
    """status: 'pending', 'done' or None for everything. Soonest deadline first."""
    init_db(db_path)
    query = "SELECT * FROM promises"
    args: tuple = ()
    if status:
        query += " WHERE status = ?"
        args = (status,)
    query += " ORDER BY deadline IS NULL, deadline, id"
    with closing(_connect(db_path)) as conn:
        return [_to_dict(r) for r in conn.execute(query, args)]


def mark_done(promise_id: int, db_path=None, now: datetime | None = None) -> None:
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("UPDATE promises SET status='done', completed_at=? WHERE id=?",
                     (_fmt(now or datetime.now()), promise_id))


def snooze(promise_id: int, days: int = 1, db_path=None, now: datetime | None = None) -> None:
    """Push the deadline back. If it's already past (or unset), count from now."""
    now = now or datetime.now()
    with closing(_connect(db_path)) as conn, conn:
        row = conn.execute("SELECT deadline FROM promises WHERE id=?", (promise_id,)).fetchone()
        if row is None:
            return
        current = _parse(row["deadline"])
        base = current if current and current > now else now
        conn.execute("UPDATE promises SET deadline=? WHERE id=?",
                     (_fmt(base + timedelta(days=days)), promise_id))


def delete(promise_id: int, db_path=None) -> None:
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM promises WHERE id=?", (promise_id,))


def update_promise(promise_id: int, commitment: str, person: str | None = None,
                   deadline: datetime | None = None, db_path=None) -> None:
    """Edit the text, person and deadline of an existing promise."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("UPDATE promises SET commitment=?, person=?, deadline=? WHERE id=?",
                     (commitment.strip(), (person or "").strip() or None, _fmt(deadline), promise_id))


def reopen(promise_id: int, db_path=None) -> None:
    """Undo 'done'."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("UPDATE promises SET status='pending', completed_at=NULL WHERE id=?", (promise_id,))
