"""DB adapters: local SQLite (dev) or Turso/libSQL HTTP (shared multi-user on Vercel)."""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("heatshield.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
    identifier TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_key TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sos_events (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


class LocalSqlite:
    """Process-local SQLite with WAL — fine for one machine / many concurrent requests."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.commit()
        logger.info("DB: local SQLite at %s", path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def execute(self, sql: str, params: tuple | list = ()) -> list[dict]:
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, params)
            if cur.description:
                rows = [dict(r) for r in cur.fetchall()]
            else:
                rows = []
            conn.commit()
            return rows

    def executescript(self, script: str) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(script)
            conn.commit()


class TursoHttp:
    """Shared remote SQLite via Turso HTTP pipeline — safe for many Vercel instances."""

    def __init__(self, url: str, token: str):
        self.url = url.strip().rstrip("/")
        if self.url.startswith("libsql://"):
            self.url = "https://" + self.url[len("libsql://") :]
        elif self.url.startswith("wss://"):
            self.url = "https://" + self.url[len("wss://") :]
        self.token = token.strip()
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=self.url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.executescript(_SCHEMA)
        logger.info("DB: Turso/libSQL at %s", self.url)

    def _arg(self, value: Any) -> dict:
        if value is None:
            return {"type": "null"}
        if isinstance(value, bool):
            return {"type": "integer", "value": "1" if value else "0"}
        if isinstance(value, int):
            return {"type": "integer", "value": str(value)}
        if isinstance(value, float):
            return {"type": "float", "value": str(value)}
        return {"type": "text", "value": str(value)}

    def _pipeline(self, sql: str, params: tuple | list = ()) -> list[dict]:
        body = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": [self._arg(p) for p in params],
                    },
                },
                {"type": "close"},
            ]
        }
        with self._lock:
            r = self._client.post("/v2/pipeline", json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"Turso HTTP {r.status_code}: {r.text[:300]}")
        payload = r.json()
        results = payload.get("results") or []
        if not results:
            return []
        first = results[0]
        if first.get("type") == "error":
            err = first.get("error") or first
            raise RuntimeError(f"Turso SQL error: {err}")
        resp = first.get("response") or {}
        result = resp.get("result") or {}
        cols = [c.get("name") for c in (result.get("cols") or [])]
        rows_out = []
        for row in result.get("rows") or []:
            item = {}
            for i, col in enumerate(cols):
                cell = row[i] if i < len(row) else None
                if isinstance(cell, dict):
                    if cell.get("type") == "null":
                        item[col] = None
                    else:
                        item[col] = cell.get("value")
                else:
                    item[col] = cell
            rows_out.append(item)
        return rows_out

    def execute(self, sql: str, params: tuple | list = ()) -> list[dict]:
        return self._pipeline(sql, params)

    def executescript(self, script: str) -> None:
        # Split on semicolons; skip empties
        for stmt in script.split(";"):
            sql = stmt.strip()
            if sql:
                self._pipeline(sql)


_db: LocalSqlite | TursoHttp | None = None


def _pick_local_path(preferred: str | None = None) -> str:
    candidates = []
    if preferred:
        candidates.append(preferred)
    if os.environ.get("SQLITE_PATH"):
        candidates.append(os.environ["SQLITE_PATH"])
    # On Vercel without Turso, /tmp is last resort (NOT multi-instance safe)
    if os.environ.get("VERCEL"):
        candidates.append("/tmp/heatshield.db")
    candidates.append(str(Path(__file__).parent / "data" / "heatshield.db"))
    for p in candidates:
        try:
            parent = Path(p).parent
            parent.mkdir(parents=True, exist_ok=True)
            probe = parent / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    return "/tmp/heatshield.db"


def init(path: str | None = None):
    """Init shared DB. Prefer Turso when configured (required for multi-user on Vercel)."""
    global _db
    turso_url = (os.environ.get("TURSO_DATABASE_URL") or os.environ.get("LIBSQL_URL") or "").strip()
    turso_token = (os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("LIBSQL_AUTH_TOKEN") or "").strip()
    if turso_url and turso_token:
        _db = TursoHttp(turso_url, turso_token)
        return
    if os.environ.get("VERCEL"):
        logger.warning(
            "VERCEL without TURSO_DATABASE_URL/TURSO_AUTH_TOKEN — "
            "SQLite /tmp is NOT shared across instances; multi-user data will be lost."
        )
    _db = LocalSqlite(_pick_local_path(path))


def get_db() -> LocalSqlite | TursoHttp:
    if _db is None:
        init()
    assert _db is not None
    return _db


def backend_name() -> str:
    db = get_db()
    if isinstance(db, TursoHttp):
        return "turso"
    return "sqlite"
