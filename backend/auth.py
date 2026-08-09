"""JWT email/password authentication (SQLite + JWT fallback for serverless)."""
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field

import store

JWT_ALGORITHM = "HS256"
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user: dict) -> str:
    """Embed profile (+ latest push sub) so auth/push work across serverless instances."""
    # Keep one subscription in the JWT so /push/test still works when SQLite /tmp is empty.
    subs = user.get("push_subscriptions") or []
    latest_sub = None
    if isinstance(subs, list) and subs:
        latest_sub = subs[-1] if isinstance(subs[-1], dict) else None
    elif isinstance(user.get("push_subscription"), dict):
        latest_sub = user["push_subscription"]

    payload = {
        "sub": str(user.get("id") or user.get("_id")),
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role", "user"),
        "user_type": user.get("user_type", "citizen"),
        "profile": user.get("profile") or {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
        "onboarded": bool(user.get("onboarded", False)),
        "notify_threshold": user.get("notify_threshold") or "High",
        "quiet_hours": user.get("quiet_hours") or {"enabled": False, "start": 22, "end": 7},
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    if latest_sub and latest_sub.get("endpoint") and latest_sub.get("keys"):
        payload["push_subscription"] = {
            "endpoint": latest_sub["endpoint"],
            "keys": latest_sub["keys"],
            "expirationTime": latest_sub.get("expirationTime"),
        }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _cookie_flags() -> dict:
    frontend = os.environ.get("FRONTEND_URL", "")
    secure = frontend.startswith("https://")
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
    }


def set_auth_cookies(response: Response, access: str, refresh: str):
    flags = _cookie_flags()
    response.set_cookie("access_token", access, max_age=43200, **flags)
    response.set_cookie("refresh_token", refresh, max_age=604800, **flags)


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    user_type: str = "citizen"


class LoginInput(BaseModel):
    email: EmailStr
    password: str


def _public_user(user: dict | None) -> dict:
    if not user:
        raise HTTPException(status_code=500, detail="User record missing")
    user = dict(user)
    user["id"] = str(user.get("id") or user.get("_id"))
    user.pop("_id", None)
    user.pop("password_hash", None)
    user.pop("push_subscriptions", None)
    return user


def _user_from_token(payload: dict) -> dict:
    sub = payload.get("push_subscription")
    return {
        "id": payload["sub"],
        "email": payload.get("email"),
        "name": payload.get("name") or "User",
        "role": payload.get("role", "user"),
        "user_type": payload.get("user_type", "citizen"),
        "profile": payload.get("profile") or {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
        "onboarded": bool(payload.get("onboarded", False)),
        "notify_threshold": payload.get("notify_threshold") or "High",
        "quiet_hours": payload.get("quiet_hours") or {"enabled": False, "start": 22, "end": 7},
        "emergency_contacts": [],
        "saved_locations": [],
        "push_subscriptions": [sub] if isinstance(sub, dict) and sub.get("endpoint") else [],
    }


def _read_access_payload(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(request: Request) -> dict:
    payload = _read_access_payload(request)
    user = store.get_user_by_id(payload["sub"])
    if user:
        return _public_user(user)
    # Serverless: SQLite is per-instance — fall back to claims in the JWT
    return _public_user(_user_from_token(payload))


def get_user_with_push(request: Request, user: dict) -> dict:
    """Full user record including push subscriptions (DB, then JWT claim fallback)."""
    full = store.get_user_by_id(user["id"])
    jwt_subs = []
    try:
        payload = _read_access_payload(request)
        sub = payload.get("push_subscription")
        if isinstance(sub, dict) and sub.get("endpoint") and sub.get("keys"):
            jwt_subs = [sub]
    except HTTPException:
        pass
    if full:
        out = dict(full)
        if not (out.get("push_subscriptions") or []) and jwt_subs:
            out["push_subscriptions"] = jwt_subs
        return out
    return {
        **user,
        "push_subscriptions": jwt_subs,
    }


async def _check_lockout(identifier: str):
    rec = store.get_login_attempt(identifier)
    if rec and rec.get("count", 0) >= 5:
        locked_until = rec.get("locked_until")
        if locked_until and datetime.now(timezone.utc) < datetime.fromisoformat(locked_until):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.")


async def _record_failure(identifier: str):
    rec = store.get_login_attempt(identifier) or {}
    count = rec.get("count", 0) + 1
    update = {"count": count}
    if count >= 5:
        update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    store.upsert_login_attempt(identifier, update)


@auth_router.post("/register")
async def register(data: RegisterInput, response: Response):
    email = data.email.lower()
    if store.get_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        doc = store.create_user({
            "email": email,
            "password_hash": hash_password(data.password),
            "name": data.name,
            "role": "user",
            "user_type": data.user_type,
            "profile": {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
            "onboarded": False,
            "emergency_contacts": [],
            "saved_locations": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        # Concurrent register with same email (unique constraint)
        if store.get_user_by_email(email):
            raise HTTPException(status_code=400, detail="Email already registered") from exc
        raise
    set_auth_cookies(response, create_access_token(doc), create_refresh_token(doc["id"]))
    return _public_user(doc)


@auth_router.post("/login")
async def login(data: LoginInput, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    await _check_lockout(identifier)

    # Ensure seed admin exists on this serverless instance
    await seed_admin()

    user = store.get_user_by_email(email)
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        await _record_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        store.delete_login_attempt(identifier)
    except Exception:
        pass
    set_auth_cookies(response, create_access_token(user), create_refresh_token(user["id"]))
    return _public_user(user)


@auth_router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@auth_router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = store.get_user_by_id(payload["sub"])
    if not user:
        # Minimal user so refresh still works across instances
        user = {"id": payload["sub"], "email": payload.get("email") or "user@heatshield.sg", "name": "User",
                "role": "user", "user_type": "citizen",
                "profile": {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
                "onboarded": True}
    flags = _cookie_flags()
    response.set_cookie(
        "access_token",
        create_access_token(user),
        max_age=43200,
        **flags,
    )
    return {"ok": True}


async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@heatshield.sg").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = store.get_user_by_email(admin_email)
    if existing is None:
        store.create_user({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
            "user_type": "citizen",
            "profile": {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
            "onboarded": True,
            "emergency_contacts": [],
            "saved_locations": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        store.update_user(existing["id"], set_fields={"password_hash": hash_password(admin_password)})
