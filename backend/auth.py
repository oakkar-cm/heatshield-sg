"""JWT email/password authentication (SQLite-backed)."""
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


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _cookie_flags() -> dict:
    # Frontend proxies /api on the same domain, so Lax first-party cookies work in the browser.
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
    response.set_cookie("access_token", access, max_age=900, **flags)
    response.set_cookie("refresh_token", refresh, max_age=604800, **flags)


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    user_type: str = "citizen"


class LoginInput(BaseModel):
    email: EmailStr
    password: str


def _public_user(user: dict) -> dict:
    user = dict(user)
    user["id"] = str(user.get("id") or user.get("_id"))
    user.pop("_id", None)
    user.pop("password_hash", None)
    user.pop("push_subscriptions", None)
    return user


async def get_current_user(request: Request) -> dict:
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
        user = store.get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return _public_user(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


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
    uid = doc["id"]
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
    return _public_user(doc)


@auth_router.post("/login")
async def login(data: LoginInput, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    await _check_lockout(identifier)
    user = store.get_user_by_email(email)
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        await _record_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    store.delete_login_attempt(identifier)
    uid = user["id"]
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
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
        raise HTTPException(status_code=401, detail="User not found")
    flags = _cookie_flags()
    response.set_cookie(
        "access_token",
        create_access_token(user["id"], user["email"]),
        max_age=900,
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
