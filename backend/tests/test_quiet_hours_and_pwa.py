"""Backend + PWA-asset tests for HeatShield SG iteration 3:
- PUT /api/push/quiet-hours (auth + persistence + /auth/me exposure)
- PWA assets: /manifest.json, /sw.js, /index.html meta tags
- Route-from-place backend dependency: GET /api/cooling/spots with alt lat/lng
- Regression: /api/locations still works
"""
import os
import re
import uuid
import json
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://wbgt-shield.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------------- Quiet Hours ----------------
class TestQuietHours:
    def test_quiet_hours_requires_auth(self, api_client):
        r = api_client.put(f"{API}/push/quiet-hours",
                           json={"enabled": True, "start": 22, "end": 7}, timeout=15)
        assert r.status_code == 401

    def test_quiet_hours_set_and_persist_on_me(self, new_user_client):
        s, _ = new_user_client
        # Default: /auth/me before any set — quiet_hours may be absent
        me0 = s.get(f"{API}/auth/me", timeout=15).json()
        assert "password_hash" not in me0

        # Enable with default 22 -> 07
        r = s.put(f"{API}/push/quiet-hours",
                  json={"enabled": True, "start": 22, "end": 7}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        payload = r.json()
        assert payload["ok"] is True
        qh = payload["quiet_hours"]
        assert qh == {"enabled": True, "start": 22, "end": 7}

        # Persistence via /auth/me
        me = s.get(f"{API}/auth/me", timeout=15).json()
        assert me.get("quiet_hours") == {"enabled": True, "start": 22, "end": 7}

        # Change window (e.g. 23 -> 6)
        r = s.put(f"{API}/push/quiet-hours",
                  json={"enabled": True, "start": 23, "end": 6}, timeout=15)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=15).json()
        assert me["quiet_hours"] == {"enabled": True, "start": 23, "end": 6}

        # Disable
        r = s.put(f"{API}/push/quiet-hours",
                  json={"enabled": False, "start": 23, "end": 6}, timeout=15)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=15).json()
        assert me["quiet_hours"]["enabled"] is False

    def test_quiet_hours_wraps_modulo_24(self, new_user_client):
        s, _ = new_user_client
        # Out-of-range hours should be normalized via modulo 24 (server: start % 24)
        r = s.put(f"{API}/push/quiet-hours",
                  json={"enabled": True, "start": 25, "end": 30}, timeout=15)
        assert r.status_code == 200
        qh = r.json()["quiet_hours"]
        assert qh["start"] == 1 and qh["end"] == 6

    def test_quiet_hours_invalid_payload(self, new_user_client):
        s, _ = new_user_client
        # Missing enabled -> 422
        r = s.put(f"{API}/push/quiet-hours",
                  json={"start": 22, "end": 7}, timeout=15)
        assert r.status_code in (400, 422)


# ---------------- PWA assets ----------------
class TestPWAAssets:
    def test_manifest_json(self, api_client):
        # manifest is served from web root (not /api). REACT_APP_BACKEND_URL == frontend origin.
        r = api_client.get(f"{BASE_URL}/manifest.json", timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # Required keys
        assert data.get("name")
        assert "HeatShield" in data["name"]
        assert data.get("start_url")
        assert data.get("display") == "standalone"
        assert data.get("theme_color") == "#0A58CA"
        assert isinstance(data.get("icons"), list) and len(data["icons"]) >= 2
        # At least one 192 and one 512 icon
        sizes = {i.get("sizes") for i in data["icons"]}
        assert "192x192" in sizes and "512x512" in sizes

    def test_service_worker(self, api_client):
        r = api_client.get(f"{BASE_URL}/sw.js", timeout=15)
        assert r.status_code == 200
        ctype = r.headers.get("content-type", "")
        # Some CDNs serve as text/plain; accept both js and plain
        assert "javascript" in ctype or "text/plain" in ctype or "text/" in ctype, f"ctype={ctype}"
        body = r.text
        # Must handle push + notification events
        assert "addEventListener(\"push\"" in body or "addEventListener('push'" in body
        assert "notificationclick" in body
        assert "showNotification" in body

    def test_index_html_meta(self, api_client):
        r = api_client.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200
        html = r.text
        # theme-color present with correct HeatShield brand
        assert re.search(r'<meta[^>]+name="theme-color"[^>]+content="#0A58CA"', html), \
            f"missing theme-color meta:\n{html[:800]}"
        # manifest link
        assert re.search(r'<link[^>]+rel="manifest"', html)
        # apple-touch-icon
        assert re.search(r'<link[^>]+rel="apple-touch-icon"', html)


# ---------------- Route-from-place backend surface ----------------
class TestCoolingFromAltLocation:
    def test_cooling_spots_from_two_different_places(self, api_client):
        # Simulate Route-from-place: cooling spots list should re-sort based on origin lat/lng.
        # Marina Bay
        r1 = api_client.get(f"{API}/cooling/spots?lat=1.283&lng=103.859&limit=5", timeout=15)
        assert r1.status_code == 200
        spots1 = r1.json()["spots"]
        # Woodlands
        r2 = api_client.get(f"{API}/cooling/spots?lat=1.437&lng=103.786&limit=5", timeout=15)
        assert r2.status_code == 200
        spots2 = r2.json()["spots"]
        assert len(spots1) == 5 and len(spots2) == 5
        # Ordering differs (Woodlands != Marina Bay closest first)
        ids1 = [s["id"] for s in spots1]
        ids2 = [s["id"] for s in spots2]
        assert ids1 != ids2, f"Same spots returned for far apart origins: {ids1}"
        # Each list sorted ascending by distance
        for spots in (spots1, spots2):
            d = [s["distance_km"] for s in spots]
            assert d == sorted(d)


# ---------------- Regression: /api/locations still works ----------------
class TestLocationsRegression:
    def test_locations_crud_still_works(self, new_user_client):
        s, _ = new_user_client
        r = s.post(f"{API}/locations",
                   json={"label": "Home", "lat": 1.35, "lng": 103.8}, timeout=15)
        assert r.status_code == 200
        assert any(l["label"] == "Home" for l in r.json()["locations"])
        r = s.get(f"{API}/locations", timeout=15)
        assert r.status_code == 200
        assert len(r.json()["locations"]) >= 1
