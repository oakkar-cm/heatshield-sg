"""Simple SQLite JSON store — no MongoDB needed for the design sprint."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_db_path: str | None = None


def _pick_path(preferred: str | None = None) -> str:
    candidates = []
    if preferred:
        candidates.append(preferred)
    if os.environ.get("SQLITE_PATH"):
        candidates.append(os.environ["SQLITE_PATH"])
    # Prefer writable temp on serverless / Linux hosts
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


def init(path: str | None = None) -> None:
    global _db_path
    _db_path = _pick_path(path)
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_db_path, check_same_thread=False) as conn:
        conn.executescript(
            """
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
        )
        conn.commit()


def _connect() -> sqlite3.Connection:
    if not _db_path:
        init()
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def new_id() -> str:
    return uuid.uuid4().hex


def _dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _loads(raw: str) -> dict:
    return json.loads(raw)


def get_user_by_id(user_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT id, data FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    doc = _loads(row["data"])
    doc["_id"] = row["id"]
    doc["id"] = row["id"]
    return doc


def get_user_by_email(email: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT id, data FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if not row:
        return None
    doc = _loads(row["data"])
    doc["_id"] = row["id"]
    doc["id"] = row["id"]
    return doc


def create_user(doc: dict) -> dict:
    uid = doc.get("id") or doc.get("_id") or new_id()
    email = doc["email"].lower()
    payload = {k: v for k, v in doc.items() if k not in ("id", "_id")}
    payload["email"] = email
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, data) VALUES (?, ?, ?)",
            (uid, email, _dumps(payload)),
        )
        conn.commit()
    out = dict(payload)
    out["_id"] = uid
    out["id"] = uid
    return out


def _apply_set(doc: dict, updates: dict) -> dict:
    out = dict(doc)
    for key, value in updates.items():
        if "." in key:
            root, child = key.split(".", 1)
            base = dict(out.get(root) or {})
            base[child] = value
            out[root] = base
        else:
            out[key] = value
    return out


def update_user(user_id: str, *, set_fields: dict | None = None, push: dict | None = None, pull: dict | None = None) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT id, email, data FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        doc = _loads(row["data"])
        if set_fields:
            doc = _apply_set(doc, set_fields)
        if push:
            for field, value in push.items():
                arr = list(doc.get(field) or [])
                arr.append(value)
                doc[field] = arr
        if pull:
            for field, matcher in pull.items():
                arr = list(doc.get(field) or [])
                if isinstance(matcher, dict) and "$in" in matcher:
                    # pull by nested key in {"endpoint": {"$in": [...]}} style used for push subs
                    # Not used in our simplified API — keep for safety
                    pass
                elif isinstance(matcher, dict):
                    def match(item: Any) -> bool:
                        if not isinstance(item, dict):
                            return False
                        return all(item.get(k) == v for k, v in matcher.items())
                    doc[field] = [x for x in arr if not match(x)]
                else:
                    doc[field] = [x for x in arr if x != matcher]
        email = (doc.get("email") or row["email"]).lower()
        doc["email"] = email
        conn.execute(
            "UPDATE users SET email = ?, data = ? WHERE id = ?",
            (email, _dumps({k: v for k, v in doc.items() if k not in ("id", "_id")}), user_id),
        )
        conn.commit()
    doc["_id"] = user_id
    doc["id"] = user_id
    return doc


def pull_push_endpoints(user_id: str, endpoints: list[str]) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None
    subs = [s for s in (user.get("push_subscriptions") or []) if s.get("endpoint") not in endpoints]
    return update_user(user_id, set_fields={"push_subscriptions": subs})


def list_users_with_push() -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT id, data FROM users").fetchall()
    out = []
    for row in rows:
        doc = _loads(row["data"])
        subs = doc.get("push_subscriptions") or []
        if subs:
            doc["_id"] = row["id"]
            doc["id"] = row["id"]
            out.append(doc)
    return out


def get_login_attempt(identifier: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT data FROM login_attempts WHERE identifier = ?", (identifier,)).fetchone()
    return _loads(row["data"]) if row else None


def upsert_login_attempt(identifier: str, data: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO login_attempts (identifier, data) VALUES (?, ?) "
            "ON CONFLICT(identifier) DO UPDATE SET data = excluded.data",
            (identifier, _dumps(data)),
        )
        conn.commit()


def delete_login_attempt(identifier: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM login_attempts WHERE identifier = ?", (identifier,))
        conn.commit()


def get_chat(session_key: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT data FROM chat_sessions WHERE session_key = ?", (session_key,)).fetchone()
    return _loads(row["data"]) if row else None


def save_chat(session_key: str, data: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (session_key, data) VALUES (?, ?) "
            "ON CONFLICT(session_key) DO UPDATE SET data = excluded.data",
            (session_key, _dumps(data)),
        )
        conn.commit()


def add_sos(event: dict) -> None:
    eid = new_id()
    with _lock, _connect() as conn:
        conn.execute("INSERT INTO sos_events (id, data) VALUES (?, ?)", (eid, _dumps(event)))
        conn.commit()
