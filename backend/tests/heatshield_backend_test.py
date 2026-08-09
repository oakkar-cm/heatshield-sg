"""End-to-end backend tests for HeatShield SG.

Covers:
- Health, NEA data (conditions, wbgt map, rainfall map, forecast)
- Cooling spots + route
- Emergency: symptoms, symptom-check, checklists, contacts CRUD, SOS
- Auth: register, login, me, logout, refresh, wrong-password 401
- Profile update / onboarding
- AI: recommendations (Claude Haiku 4.5), chat streaming
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://wbgt-shield.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------------- Health & public NEA ----------------
class TestHealthAndNEA:
    def test_root(self, api_client):
        r = api_client.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_conditions_singapore(self, api_client):
        r = api_client.get(f"{API}/conditions?lat=1.3521&lng=103.8198", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Fields present
        for k in ("wbgt", "air_temperature", "rainfall", "humidity", "heat_level", "heat_meta"):
            assert k in data, f"Missing {k}"
        # Real live NEA data should give sensible numbers
        assert data["heat_level"] in ("low", "moderate", "high", "very high", "extreme")
        assert isinstance(data["heat_meta"], dict) and "label" in data["heat_meta"]
        temp = data["air_temperature"].get("value")
        assert temp is None or (10 < float(temp) < 45), f"unrealistic temp {temp}"

    def test_map_wbgt(self, api_client):
        r = api_client.get(f"{API}/map/wbgt", timeout=30)
        assert r.status_code == 200
        stations = r.json()["stations"]
        assert isinstance(stations, list)
        # Live source might return empty briefly but usually >0
        for s in stations:
            assert "lat" in s and "lng" in s and "wbgt" in s and "level" in s

    def test_map_rainfall(self, api_client):
        r = api_client.get(f"{API}/map/rainfall", timeout=30)
        assert r.status_code == 200
        payload = r.json()
        assert "stations" in payload
        assert isinstance(payload["stations"], list)

    def test_forecast(self, api_client):
        r = api_client.get(f"{API}/forecast?lat=1.3521&lng=103.8198", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "points" in data and len(data["points"]) == 9
        assert "peak" in data and "summary" in data


# ---------------- Cooling ----------------
class TestCooling:
    def test_cooling_spots(self, api_client):
        r = api_client.get(f"{API}/cooling/spots?lat=1.3521&lng=103.8198&limit=5", timeout=15)
        assert r.status_code == 200
        spots = r.json()["spots"]
        assert len(spots) == 5
        # Sorted by distance ascending
        distances = [s["distance_km"] for s in spots]
        assert distances == sorted(distances)
        for s in spots:
            assert {"id", "name", "type", "lat", "lng", "amenities", "distance_km"} <= set(s.keys())

    def test_cooling_all(self, api_client):
        r = api_client.get(f"{API}/cooling/all", timeout=15)
        assert r.status_code == 200
        assert len(r.json()["spots"]) >= 10

    def test_cooling_route(self, api_client):
        r = api_client.get(f"{API}/cooling/route?spot_id=cs1&lat=1.3521&lng=103.8198", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["destination"]["id"] == "cs1"
        assert "walking_url" in data and "google.com/maps/dir" in data["walking_url"]
        assert "travelmode=walking" in data["walking_url"]
        assert isinstance(data["tips"], list) and len(data["tips"]) >= 2

    def test_cooling_route_not_found(self, api_client):
        r = api_client.get(f"{API}/cooling/route?spot_id=nope&lat=1.35&lng=103.8", timeout=15)
        assert r.status_code == 404


# ---------------- Emergency (public) ----------------
class TestEmergencyPublic:
    def test_symptom_list(self, api_client):
        r = api_client.get(f"{API}/emergency/symptoms", timeout=15)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()["symptoms"]]
        assert "confusion" in ids and "fainting" in ids

    def test_symptom_check_heatstroke(self, api_client):
        r = api_client.post(f"{API}/emergency/symptom-check", json={"symptoms": ["confusion", "fainting"]}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["condition"] == "Possible Heat Stroke"
        assert data["severity"] == "emergency"
        assert any("995" in a for a in data["advice"])

    def test_symptom_check_exhaustion(self, api_client):
        r = api_client.post(f"{API}/emergency/symptom-check", json={"symptoms": ["dizziness", "headache"]}, timeout=15)
        assert r.status_code == 200
        assert r.json()["condition"] == "Heat Exhaustion"

    def test_checklists(self, api_client):
        r = api_client.get(f"{API}/emergency/checklists", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "checklists" in data and "work_rest" in data
        assert len(data["work_rest"]) == 4


# ---------------- Auth ----------------
class TestAuth:
    def test_me_unauthenticated(self, api_client):
        r = api_client.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_login_wrong_password(self, api_client):
        r = api_client.post(f"{API}/auth/login", json={"email": "admin@heatshield.sg", "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_admin_login_and_me(self, admin_client):
        r = admin_client.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == "admin@heatshield.sg"
        assert me.get("onboarded") is True
        # Never leak hashed password
        assert "password_hash" not in me
        assert "_id" not in me

    def test_register_and_flow(self, new_user_client):
        s, info = new_user_client
        # /auth/me works
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == info["email"]
        assert me.get("onboarded") is False
        # Refresh works
        rr = s.post(f"{API}/auth/refresh", timeout=15)
        assert rr.status_code == 200
        # Logout
        lo = s.post(f"{API}/auth/logout", timeout=15)
        assert lo.status_code == 200
        # After logout, /me must 401
        assert s.get(f"{API}/auth/me", timeout=15).status_code == 401

    def test_register_duplicate(self, api_client):
        email = f"dup_{uuid.uuid4().hex[:8]}@heatshield.sg"
        payload = {"email": email, "password": "test1234", "name": "Dup", "user_type": "citizen"}
        r1 = api_client.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r1.status_code == 200
        r2 = api_client.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r2.status_code == 400


# ---------------- Profile / onboarding ----------------
class TestProfile:
    def test_update_profile_onboarding(self, new_user_client):
        s, _ = new_user_client
        r = s.put(f"{API}/profile", json={
            "user_type": "elderly",
            "age_group": "elderly",
            "outdoor_exposure": "low",
            "health_flags": ["Heart condition"],
            "onboarded": True,
        }, timeout=15)
        assert r.status_code == 200
        prof = r.json()
        assert prof["user_type"] == "elderly"
        assert prof["onboarded"] is True
        assert prof["profile"]["health_flags"] == ["Heart condition"]
        assert "_id" not in prof
        assert "password_hash" not in prof


# ---------------- Personalised risk ----------------
class TestRisk:
    def test_risk_admin(self, admin_client):
        r = admin_client.get(f"{API}/risk?lat=1.3521&lng=103.8198", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert 0 <= data["risk"]["score"] <= 100
        assert data["risk"]["band"] in ("Low", "Moderate", "High", "Very High")
        assert isinstance(data["risk"]["factors"], list) and len(data["risk"]["factors"]) >= 1


# ---------------- Emergency (authenticated) ----------------
class TestEmergencyAuth:
    def test_contacts_crud_and_sos(self, admin_client):
        # Clean list
        r = admin_client.get(f"{API}/emergency/contacts", timeout=15)
        assert r.status_code == 200
        # ADD
        r = admin_client.post(f"{API}/emergency/contacts",
                              json={"name": "TEST_Caregiver", "phone": "+6591234567", "relation": "Son"}, timeout=15)
        assert r.status_code == 200
        contacts = r.json()["contacts"]
        assert any(c["name"] == "TEST_Caregiver" for c in contacts)
        cid = next(c["id"] for c in contacts if c["name"] == "TEST_Caregiver")
        # SOS returns caregiver alert
        sos = admin_client.post(f"{API}/emergency/sos", json={"lat": 1.35, "lng": 103.82}, timeout=15)
        assert sos.status_code == 200
        sd = sos.json()
        assert sd["ok"] is True
        assert "995" in sd["emergency_numbers"]["SCDF Ambulance"]
        assert sd["location_link"] and "google.com/maps" in sd["location_link"]
        # DELETE
        d = admin_client.delete(f"{API}/emergency/contacts/{cid}", timeout=15)
        assert d.status_code == 200
        assert not any(c["id"] == cid for c in d.json()["contacts"])


# ---------------- AI (Claude Haiku 4.5) ----------------
class TestAI:
    def test_recommendations_real_llm(self, admin_client):
        r = admin_client.get(f"{API}/recommendations?lat=1.3521&lng=103.8198", timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        tips = data["recommendations"]
        assert isinstance(tips, list) and len(tips) == 4
        # Must not be the hardcoded fallback list
        fallback = {"Stay hydrated", "Avoid midday sun", "Seek shade or air-con", "Check on vulnerable people"}
        assert set(tips) != fallback, f"Got hardcoded fallback list -> LLM likely not called: {tips}"
        # Reasonable text
        for t in tips:
            assert isinstance(t, str) and len(t) > 5

    def test_chat_streaming_singapore_advice(self, admin_client):
        # HeatShield SG is a topic-locked assistant (climate/heat safety only), so we probe on-topic.
        url = f"{API}/chat"
        payload = {"message": "In one sentence, what is WBGT?", "session_id": "pytest-wbgt"}
        with admin_client.post(url, json=payload, stream=True, timeout=90) as r:
            assert r.status_code == 200, r.text[:400]
            chunks = []
            t0 = time.time()
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    chunks.append(chunk)
                if time.time() - t0 > 60:
                    break
            full = "".join(chunks).strip()
            assert full, "Empty stream"
            assert "WBGT" in full or "wet" in full.lower() or "bulb" in full.lower(), f"Off-topic reply: {full[:400]}"
        # Second turn - Singapore heat advice
        payload2 = {"message": "Give me one short tip to stay cool during peak WBGT in Singapore.",
                    "session_id": "pytest-advice", "lat": 1.3521, "lng": 103.8198}
        with admin_client.post(url, json=payload2, stream=True, timeout=90) as r:
            assert r.status_code == 200
            body = ""
            t0 = time.time()
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                body += chunk or ""
                if time.time() - t0 > 60:
                    break
            assert len(body) > 20, f"Reply too short: {body!r}"
            low = body.lower()
            assert any(k in low for k in ["water", "shade", "air", "hydrat", "cool", "wbgt", "heat"]), (
                f"Reply not on topic: {body[:400]}")

    def test_chat_history_persisted(self, admin_client):
        # After previous test, history for pytest-wbgt should have messages
        r = admin_client.get(f"{API}/chat/history?session_id=pytest-wbgt", timeout=15)
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert isinstance(msgs, list) and len(msgs) >= 2
        assert msgs[-2]["role"] == "user"
        assert msgs[-1]["role"] == "assistant"
        assert len(msgs[-1]["content"]) > 20
