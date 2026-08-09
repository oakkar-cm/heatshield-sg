from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import logging
import asyncio
from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

import auth
import store
import nea_service as nea
import ai_service as ai
import push_service as push
from sg_data import (COOLING_SPOTS, PREPAREDNESS_CHECKLISTS, WORK_REST_GUIDANCE,
                     SYMPTOMS, assess_symptoms)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heatshield")

app = FastAPI(title="HeatShield SG")
api = APIRouter(prefix="/api")

SG_LAT, SG_LNG = 1.3521, 103.8198


class ProfileUpdate(BaseModel):
    user_type: Optional[str] = None
    age_group: Optional[str] = None
    health_flags: Optional[List[str]] = None
    outdoor_exposure: Optional[str] = None
    onboarded: Optional[bool] = None


class EmergencyContact(BaseModel):
    name: str
    phone: str
    relation: Optional[str] = ""


class ChatInput(BaseModel):
    message: str
    session_id: str = "default"
    lat: Optional[float] = None
    lng: Optional[float] = None


class SymptomInput(BaseModel):
    symptoms: List[str]


class SosInput(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None


class SavedLocationInput(BaseModel):
    label: str
    lat: float
    lng: float


class PushSubscribeInput(BaseModel):
    subscription: dict


class NotifyThresholdInput(BaseModel):
    threshold: str


class QuietHoursInput(BaseModel):
    enabled: bool
    start: int = Field(ge=0, le=23)
    end: int = Field(ge=0, le=23)


@api.get("/")
async def root():
    return {"message": "HeatShield SG API", "status": "ok", "storage": "sqlite"}


@api.get("/conditions")
async def conditions(lat: float = SG_LAT, lng: float = SG_LNG):
    return await nea.get_conditions(lat, lng)


@api.get("/map/wbgt")
async def map_wbgt():
    return {"stations": await nea.get_wbgt_stations()}


@api.get("/map/rainfall")
async def map_rainfall():
    items, ts = await nea.get_rainfall()
    return {"stations": items, "timestamp": ts}


@api.get("/forecast")
async def forecast(lat: float = SG_LAT, lng: float = SG_LNG):
    return await nea.get_forecast(lat, lng)


@api.get("/risk")
async def risk(lat: float = SG_LAT, lng: float = SG_LNG, user: dict = Depends(auth.get_current_user)):
    cond = await nea.get_conditions(lat, lng)
    scored = nea.compute_risk(cond, user.get("profile", {}))
    return {"conditions": cond, "risk": scored, "user_type": user.get("user_type")}


@api.get("/cooling/spots")
async def cooling_spots(lat: float = SG_LAT, lng: float = SG_LNG, limit: int = 5):
    return {"spots": nea.nearest_cooling_spots(lat, lng, limit)}


@api.get("/cooling/all")
async def cooling_all():
    return {"spots": COOLING_SPOTS}


@api.get("/cooling/route")
async def cooling_route(spot_id: str, lat: float = SG_LAT, lng: float = SG_LNG):
    dest = next((s for s in COOLING_SPOTS if s["id"] == spot_id), None)
    if not dest:
        raise HTTPException(status_code=404, detail="Cooling spot not found")
    d = nea._haversine(lat, lng, dest["lat"], dest["lng"])
    return nea.build_route(lat, lng, {**dest, "distance_km": round(d, 2)})


@api.get("/emergency/symptoms")
async def symptom_list():
    return {"symptoms": SYMPTOMS}


@api.post("/emergency/symptom-check")
async def symptom_check(data: SymptomInput):
    return assess_symptoms(data.symptoms)


@api.get("/emergency/checklists")
async def checklists():
    return {"checklists": PREPAREDNESS_CHECKLISTS, "work_rest": WORK_REST_GUIDANCE}


@api.get("/emergency/contacts")
async def get_contacts(user: dict = Depends(auth.get_current_user)):
    full = store.get_user_by_id(user["id"])
    return {"contacts": (full or {}).get("emergency_contacts", [])}


@api.post("/emergency/contacts")
async def add_contact(c: EmergencyContact, user: dict = Depends(auth.get_current_user)):
    contact = c.model_dump()
    contact["id"] = store.new_id()
    doc = store.update_user(user["id"], push={"emergency_contacts": contact})
    return {"contacts": doc.get("emergency_contacts", [])}


@api.delete("/emergency/contacts/{contact_id}")
async def delete_contact(contact_id: str, user: dict = Depends(auth.get_current_user)):
    doc = store.update_user(user["id"], pull={"emergency_contacts": {"id": contact_id}})
    return {"contacts": (doc or {}).get("emergency_contacts", [])}


@api.post("/emergency/sos")
async def sos(data: SosInput, user: dict = Depends(auth.get_current_user)):
    full = store.get_user_by_id(user["id"]) or {}
    contacts = full.get("emergency_contacts", []) or []
    maps_link = None
    if data.lat is not None and data.lng is not None:
        maps_link = f"https://www.google.com/maps?q={data.lat},{data.lng}"

    name = user.get("name") or "HeatShield user"
    sms_body = f"SOS from {name}. I need help."
    if maps_link:
        sms_body += f" My location: {maps_link}"

    alert_contacts = []
    for c in contacts:
        phone = "".join(ch for ch in str(c.get("phone") or "") if ch.isdigit() or ch == "+")
        alert_contacts.append({
            **c,
            "tel_url": f"tel:{phone}" if phone else None,
            "sms_url": f"sms:{phone}?body={quote(sms_body)}" if phone else None,
        })

    push_sent = 0
    try:
        push_sent = await push.push_to_user(full, {
            "title": "SOS activated",
            "body": f"{name} triggered SOS" + (f". Location: {maps_link}" if maps_link else ""),
            "url": "/emergency",
        })
    except Exception as exc:
        logger.warning("SOS push failed: %s", exc)

    event = {
        "user_id": user["id"],
        "name": name,
        "lat": data.lat,
        "lng": data.lng,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "caregivers": [c.get("name") for c in contacts],
        "push_sent": push_sent,
        "location_link": maps_link,
    }
    store.add_sos(event)

    if contacts:
        message = (
            f"SOS logged. Push sent to {push_sent} of your device(s). "
            f"Tap Call or SMS below to reach your {len(contacts)} caregiver(s) now."
        )
    else:
        message = (
            f"SOS logged. Push sent to {push_sent} of your device(s). "
            "Add caregivers for one-tap Call/SMS, or dial 995 for a medical emergency."
        )

    return {
        "ok": True,
        "message": message,
        "contacts": alert_contacts,
        "push_sent": push_sent,
        "location_link": maps_link,
        "emergency_numbers": {"SCDF Ambulance": "995", "Police": "999", "NEA": "1800-2255-632"},
    }


@api.put("/profile")
async def update_profile(data: ProfileUpdate, user: dict = Depends(auth.get_current_user)):
    updates = {}
    if data.user_type is not None:
        updates["user_type"] = data.user_type
    if data.onboarded is not None:
        updates["onboarded"] = data.onboarded
    if data.age_group is not None:
        updates["profile.age_group"] = data.age_group
    if data.health_flags is not None:
        updates["profile.health_flags"] = data.health_flags
    if data.outdoor_exposure is not None:
        updates["profile.outdoor_exposure"] = data.outdoor_exposure
    doc = store.update_user(user["id"], set_fields=updates) if updates else store.get_user_by_id(user["id"])
    return auth._public_user(doc)


@api.get("/ai/status")
async def ai_status():
    return await ai.ai_status()


@api.get("/recommendations")
async def recommendations(lat: float = SG_LAT, lng: float = SG_LNG, user: dict = Depends(auth.get_current_user)):
    cond = await nea.get_conditions(lat, lng)
    scored = nea.compute_risk(cond, user.get("profile", {}))
    forecast = await nea.get_forecast(lat, lng)
    profile = {"user_type": user.get("user_type"), "profile": user.get("profile", {})}
    tips = await ai.get_recommendations(profile, cond, scored, forecast)
    return {"recommendations": tips, "risk": scored, "conditions": cond, "forecast_summary": forecast.get("summary")}


@api.post("/chat")
async def chat(data: ChatInput, user: dict = Depends(auth.get_current_user)):
    """Return full reply as JSON — more reliable than streaming through Vercel proxies."""
    profile = {"user_type": user.get("user_type"), "profile": user.get("profile", {})}
    session_key = f"{user['id']}:{data.session_id}"
    history_doc = store.get_chat(session_key)
    history = history_doc.get("messages", []) if history_doc else []

    lat = data.lat if data.lat is not None else SG_LAT
    lng = data.lng if data.lng is not None else SG_LNG
    cond = None
    forecast = None
    risk = None
    spots = []
    try:
        cond = await nea.get_conditions(lat, lng)
        forecast = await nea.get_forecast(lat, lng)
        risk = nea.compute_risk(cond, user.get("profile", {}))
        spots = nea.nearest_cooling_spots(lat, lng, limit=3)
    except Exception as exc:
        logger.warning("Live context fetch failed: %s", exc)

    full = ""
    async for chunk in ai.stream_chat(
        session_key, data.message, profile, history, cond, risk, forecast, spots,
    ):
        full += chunk

    new_history = history + [
        {"role": "user", "content": data.message},
        {"role": "assistant", "content": full},
    ]
    try:
        store.save_chat(session_key, {
            "session_key": session_key,
            "user_id": user["id"],
            "messages": new_history[-40:],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.warning("chat history save failed: %s", exc)

    return {
        "reply": full,
        "heat_level": (cond or {}).get("heat_level"),
        "temp": ((cond or {}).get("air_temperature") or {}).get("value"),
    }


@api.get("/chat/history")
async def chat_history(session_id: str = "default", user: dict = Depends(auth.get_current_user)):
    doc = store.get_chat(f"{user['id']}:{session_id}")
    return {"messages": doc.get("messages", []) if doc else []}


@api.get("/locations")
async def get_locations(user: dict = Depends(auth.get_current_user)):
    full = store.get_user_by_id(user["id"])
    return {"locations": (full or {}).get("saved_locations", [])}


@api.post("/locations")
async def add_location(data: SavedLocationInput, user: dict = Depends(auth.get_current_user)):
    loc = {"id": store.new_id(), "label": data.label, "lat": data.lat, "lng": data.lng}
    store.update_user(user["id"], pull={"saved_locations": {"label": data.label}})
    doc = store.update_user(user["id"], push={"saved_locations": loc})
    return {"locations": doc.get("saved_locations", [])}


@api.delete("/locations/{loc_id}")
async def delete_location(loc_id: str, user: dict = Depends(auth.get_current_user)):
    doc = store.update_user(user["id"], pull={"saved_locations": {"id": loc_id}})
    return {"locations": (doc or {}).get("saved_locations", [])}


@api.get("/push/vapid-public-key")
async def vapid_public_key():
    return {"public_key": os.environ.get("VAPID_PUBLIC_KEY")}


@api.post("/push/subscribe")
async def push_subscribe(data: PushSubscribeInput, user: dict = Depends(auth.get_current_user)):
    endpoint = data.subscription.get("endpoint")
    store.update_user(user["id"], pull={"push_subscriptions": {"endpoint": endpoint}})
    store.update_user(user["id"], push={"push_subscriptions": data.subscription})
    return {"ok": True}


@api.post("/push/unsubscribe")
async def push_unsubscribe(data: PushSubscribeInput, user: dict = Depends(auth.get_current_user)):
    endpoint = data.subscription.get("endpoint")
    store.update_user(user["id"], pull={"push_subscriptions": {"endpoint": endpoint}})
    return {"ok": True}


@api.put("/push/threshold")
async def set_threshold(data: NotifyThresholdInput, user: dict = Depends(auth.get_current_user)):
    store.update_user(user["id"], set_fields={"notify_threshold": data.threshold})
    return {"ok": True, "threshold": data.threshold}


@api.put("/push/quiet-hours")
async def set_quiet_hours(data: QuietHoursInput, user: dict = Depends(auth.get_current_user)):
    qh = {"enabled": data.enabled, "start": data.start % 24, "end": data.end % 24}
    store.update_user(user["id"], set_fields={"quiet_hours": qh})
    return {"ok": True, "quiet_hours": qh}


@api.post("/push/test")
async def push_test(user: dict = Depends(auth.get_current_user)):
    full = store.get_user_by_id(user["id"])
    payload = {
        "title": "HeatShield SG test alert",
        "body": "Notifications are on. You'll be alerted here even with the app closed.",
        "url": "/",
        "tag": "heat-test",
    }
    sent = await push.push_to_user(full, payload)
    if sent == 0:
        raise HTTPException(status_code=400, detail="No active push subscription. Enable notifications first.")
    return {"ok": True, "sent": sent}


app.include_router(auth.auth_router)
app.include_router(api)

_cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors if _cors != ["*"] else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    store.init()
    await auth.seed_admin()
    # Background monitor needs a long-lived process (skip on Vercel serverless)
    if not os.environ.get("VERCEL"):
        asyncio.create_task(push.monitor_loop(nea.get_conditions, nea.compute_risk))
    logger.info("HeatShield SG API ready (SQLite)")
