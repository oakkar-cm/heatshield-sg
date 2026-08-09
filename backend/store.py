"""User/chat/SOS store — local SQLite or shared Turso (multi-user safe on Vercel)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import db as dbmod


def init(path: str | None = None) -> None:
    dbmod.init(path)


def new_id() -> str:
    return uuid.uuid4().hex


def datetime_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _loads(raw: str | None) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def get_user_by_id(user_id: str) -> dict | None:
    rows = dbmod.get_db().execute("SELECT id, data FROM users WHERE id = ?", (user_id,))
    if not rows:
        return None
    doc = _loads(rows[0]["data"])
    doc["_id"] = rows[0]["id"]
    doc["id"] = rows[0]["id"]
    return doc


def get_user_by_email(email: str) -> dict | None:
    rows = dbmod.get_db().execute("SELECT id, data FROM users WHERE email = ?", (email.lower(),))
    if not rows:
        return None
    doc = _loads(rows[0]["data"])
    doc["_id"] = rows[0]["id"]
    doc["id"] = rows[0]["id"]
    return doc


def create_user(doc: dict) -> dict:
    uid = doc.get("id") or doc.get("_id") or new_id()
    email = doc["email"].lower()
    payload = {k: v for k, v in doc.items() if k not in ("id", "_id")}
    payload["email"] = email
    dbmod.get_db().execute(
        "INSERT INTO users (id, email, data) VALUES (?, ?, ?)",
        (uid, email, _dumps(payload)),
    )
    out = dict(payload)
    out["_id"] = uid
    out["id"] = uid
    return out


def ensure_user(claims: dict) -> dict:
    """Create a row from JWT/session claims when missing."""
    uid = str(claims.get("id") or claims.get("_id") or "")
    email = (claims.get("email") or "").lower().strip()
    if uid:
        existing = get_user_by_id(uid)
        if existing:
            return existing
    if email:
        existing = get_user_by_email(email)
        if existing:
            return existing
    if not uid:
        uid = new_id()
    if not email:
        email = f"{uid}@heatshield.local"
    try:
        return create_user({
            "id": uid,
            "email": email,
            "password_hash": claims.get("password_hash") or "",
            "name": claims.get("name") or "User",
            "role": claims.get("role", "user"),
            "user_type": claims.get("user_type", "citizen"),
            "profile": claims.get("profile") or {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
            "onboarded": bool(claims.get("onboarded", False)),
            "emergency_contacts": claims.get("emergency_contacts") or [],
            "saved_locations": claims.get("saved_locations") or [],
            "notify_threshold": claims.get("notify_threshold") or "High",
            "quiet_hours": claims.get("quiet_hours") or {"enabled": False, "start": 22, "end": 7},
            "push_subscriptions": claims.get("push_subscriptions") or [],
            "created_at": datetime_iso(),
        })
    except Exception:
        existing = get_user_by_email(email) or (get_user_by_id(uid) if uid else None)
        if existing:
            return existing
        raise


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
    row_list = dbmod.get_db().execute("SELECT id, email, data FROM users WHERE id = ?", (user_id,))
    if not row_list:
        return None
    row = row_list[0]
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
    dbmod.get_db().execute(
        "UPDATE users SET email = ?, data = ? WHERE id = ?",
        (email, _dumps({k: v for k, v in doc.items() if k not in ("id", "_id")}), user_id),
    )
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
    rows = dbmod.get_db().execute("SELECT id, data FROM users")
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
    rows = dbmod.get_db().execute("SELECT data FROM login_attempts WHERE identifier = ?", (identifier,))
    return _loads(rows[0]["data"]) if rows else None


def upsert_login_attempt(identifier: str, data: dict) -> None:
    dbmod.get_db().execute(
        "INSERT INTO login_attempts (identifier, data) VALUES (?, ?) "
        "ON CONFLICT(identifier) DO UPDATE SET data = excluded.data",
        (identifier, _dumps(data)),
    )


def delete_login_attempt(identifier: str) -> None:
    dbmod.get_db().execute("DELETE FROM login_attempts WHERE identifier = ?", (identifier,))


def get_chat(session_key: str) -> dict | None:
    rows = dbmod.get_db().execute("SELECT data FROM chat_sessions WHERE session_key = ?", (session_key,))
    return _loads(rows[0]["data"]) if rows else None


def save_chat(session_key: str, data: dict) -> None:
    dbmod.get_db().execute(
        "INSERT INTO chat_sessions (session_key, data) VALUES (?, ?) "
        "ON CONFLICT(session_key) DO UPDATE SET data = excluded.data",
        (session_key, _dumps(data)),
    )


def add_sos(event: dict) -> None:
    eid = new_id()
    dbmod.get_db().execute("INSERT INTO sos_events (id, data) VALUES (?, ?)", (eid, _dumps(event)))


def db_status() -> dict:
    return {
        "backend": dbmod.backend_name(),
        "multi_user_safe": dbmod.backend_name() == "turso" or not __import__("os").environ.get("VERCEL"),
    }
