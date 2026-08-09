"""Backend tests for HeatShield SG new features:
- Saved Locations CRUD (/api/locations)
- Web Push (VAPID public key, subscribe/unsubscribe, threshold, test-without-sub)
"""
import os
import uuid
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://wbgt-shield.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------------- Saved Locations ----------------
class TestSavedLocations:
    def test_locations_requires_auth(self, api_client):
        r = api_client.get(f"{API}/locations", timeout=15)
        assert r.status_code == 401

    def test_locations_full_crud(self, new_user_client):
        s, _ = new_user_client
        # Empty list initially
        r = s.get(f"{API}/locations", timeout=15)
        assert r.status_code == 200
        assert r.json()["locations"] == []

        # Add Home
        r = s.post(f"{API}/locations", json={"label": "Home", "lat": 1.3521, "lng": 103.8198}, timeout=15)
        assert r.status_code == 200
        locs = r.json()["locations"]
        assert len(locs) == 1
        assert locs[0]["label"] == "Home"
        assert locs[0]["lat"] == 1.3521
        assert locs[0]["lng"] == 103.8198
        assert "id" in locs[0] and isinstance(locs[0]["id"], str) and len(locs[0]["id"]) > 0
        home_id = locs[0]["id"]

        # Add Work
        r = s.post(f"{API}/locations", json={"label": "Work", "lat": 1.3000, "lng": 103.8500}, timeout=15)
        assert r.status_code == 200
        locs = r.json()["locations"]
        assert len(locs) == 2
        assert {l["label"] for l in locs} == {"Home", "Work"}

        # Verify persisted via GET
        r = s.get(f"{API}/locations", timeout=15)
        assert r.status_code == 200
        got = r.json()["locations"]
        assert len(got) == 2
        assert {l["label"] for l in got} == {"Home", "Work"}

        # Adding Home again should REPLACE (not duplicate) — dedupe by label
        r = s.post(f"{API}/locations", json={"label": "Home", "lat": 1.4000, "lng": 103.9000}, timeout=15)
        assert r.status_code == 200
        got = r.json()["locations"]
        home = [l for l in got if l["label"] == "Home"]
        assert len(home) == 1, f"Home duplicated: {got}"
        assert home[0]["lat"] == 1.4000

        # Delete original home_id (should not error even if replaced) — delete Work instead
        work_id = next(l["id"] for l in got if l["label"] == "Work")
        d = s.delete(f"{API}/locations/{work_id}", timeout=15)
        assert d.status_code == 200
        remaining = d.json()["locations"]
        assert not any(l["id"] == work_id for l in remaining)
        assert len(remaining) == 1 and remaining[0]["label"] == "Home"

        # Delete unknown id — should still return 200 with unchanged list
        d = s.delete(f"{API}/locations/{uuid.uuid4().hex[:24]}", timeout=15)
        assert d.status_code == 200

    def test_locations_expose_on_me(self, new_user_client):
        s, _ = new_user_client
        s.post(f"{API}/locations", json={"label": "Home", "lat": 1.35, "lng": 103.8}, timeout=15)
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert isinstance(me.get("saved_locations", []), list)
        assert any(l["label"] == "Home" for l in me["saved_locations"])


# ---------------- Web Push ----------------
class TestWebPush:
    def test_vapid_public_key(self, api_client):
        r = api_client.get(f"{API}/push/vapid-public-key", timeout=15)
        assert r.status_code == 200
        key = r.json().get("public_key")
        assert isinstance(key, str) and len(key) > 30
        # VAPID keys are URL-safe base64; must start with "B" (uncompressed EC point marker)
        assert key.startswith("B"), f"Unexpected VAPID key format: {key[:8]}"

    def test_subscribe_requires_auth(self, api_client):
        r = api_client.post(
            f"{API}/push/subscribe",
            json={"subscription": {"endpoint": "https://x", "keys": {"p256dh": "a", "auth": "b"}}},
            timeout=15,
        )
        assert r.status_code == 401

    def test_test_push_requires_auth(self, api_client):
        r = api_client.post(f"{API}/push/test", timeout=15)
        assert r.status_code == 401

    def test_test_push_without_subscription_returns_400(self, new_user_client):
        s, _ = new_user_client
        r = s.post(f"{API}/push/test", timeout=20)
        assert r.status_code == 400, r.text[:200]
        detail = r.json().get("detail", "")
        assert "subscription" in detail.lower() or "notification" in detail.lower()

    def test_subscribe_then_test_and_unsubscribe(self, new_user_client):
        """Store a fake subscription (webpush will fail transport but sub is stored;
        test endpoint returns ok=True since sent counter treats non-410 as 'sent')."""
        s, _ = new_user_client
        fake_sub = {
            "endpoint": f"https://fcm.googleapis.com/fcm/send/fake-{uuid.uuid4().hex[:12]}",
            "expirationTime": None,
            "keys": {
                # 32-byte P-256 public key base64url-encoded (fake but well-formed length)
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "auth": "tBHItJI5svbpez7KI4CCXg",
            },
        }
        r = s.post(f"{API}/push/subscribe", json={"subscription": fake_sub}, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # /auth/me intentionally does NOT expose push_subscriptions (server-only, contains auth secret).
        me = s.get(f"{API}/auth/me", timeout=15).json()
        assert "push_subscriptions" not in me, "push_subscriptions must not be exposed on /auth/me"

        # /push/test — sub exists; transport to fake endpoint fails but is treated non-fatally
        # (send_push returns True on non-410 errors, so 'sent' >= 1)
        r = s.post(f"{API}/push/test", timeout=30)
        # Real FCM will return 4xx/410 for the fake endpoint; either 200 (kept) or 400 (stale/pruned) is acceptable
        assert r.status_code in (200, 400), f"Unexpected {r.status_code}: {r.text[:200]}"
        if r.status_code == 200:
            assert r.json().get("ok") is True

        # Unsubscribe (uses the same fake_sub endpoint we stored)
        r = s.post(f"{API}/push/unsubscribe", json={"subscription": fake_sub}, timeout=15)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=15).json()
        # push_subscriptions is intentionally stripped from /auth/me; just verify /push/test now 400s.

        # /push/test again should now be 400
        r = s.post(f"{API}/push/test", timeout=15)
        assert r.status_code == 400

    def test_threshold_update_and_persistence(self, new_user_client):
        s, _ = new_user_client
        for value in ["Moderate", "High", "Very High"]:
            r = s.put(f"{API}/push/threshold", json={"threshold": value}, timeout=15)
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True
            assert data["threshold"] == value
            # Verify on /auth/me
            me = s.get(f"{API}/auth/me", timeout=15).json()
            assert me.get("notify_threshold") == value

    def test_threshold_requires_auth(self, api_client):
        r = api_client.put(f"{API}/push/threshold", json={"threshold": "High"}, timeout=15)
        assert r.status_code == 401


# ---------------- Regression sanity: /auth/me shape unaffected ----------------
class TestAuthMeShape:
    def test_admin_me_has_no_leaks(self, admin_client):
        r = admin_client.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == "admin@heatshield.sg"
        assert "password_hash" not in me
        assert "_id" not in me
        # New fields may or may not be present depending on prior state — do not assert values
