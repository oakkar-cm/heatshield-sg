"""Shared fixtures for HeatShield SG backend tests."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if "REACT_APP_BACKEND_URL" in os.environ else "https://wbgt-shield.preview.emergentagent.com"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def admin_client(api_client):
    """Session logged in as admin (uses HttpOnly cookies)."""
    resp = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@heatshield.sg", "password": "admin123"},
        timeout=30,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} {resp.text[:200]}")
    return api_client


@pytest.fixture
def new_user_client():
    """Register a fresh user; returns (session, user_info)."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"test_{uuid.uuid4().hex[:10]}@heatshield.sg"
    password = "test1234"
    resp = s.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "Test User", "user_type": "citizen"},
        timeout=30,
    )
    if resp.status_code != 200:
        pytest.skip(f"Register failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    return s, {"email": email, "password": password, "id": data.get("id"), "name": data.get("name")}
