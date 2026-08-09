from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import logging
import asyncio
from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

import auth
import nea_service as nea
import ai_service as ai
import push_service as push
from sg_data import (COOLING_SPOTS, PREPAREDNESS_CHECKLISTS, WORK_REST_GUIDANCE,
                     SYMPTOMS, assess_symptoms)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heatshield")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="HeatShield SG")
api = APIRouter(prefix="/api")

# Singapore centre fallback
SG_LAT, SG_LNG = 1.3521, 103.8198


# ---------- Models ----------
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
    start: int = Field(ge=0, le=23)  # hour 0-23 (SG time)
    end: int = Field(ge=0, le=23)


# ---------- Health ----------
@api.get("/")
async def root():
    return {"message": "HeatShield SG API", "status": "ok"}


# ---------- NEA data ----------
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


# ---------- Personalised risk ----------
@api.get("/risk")
async def risk(lat: float = SG_LAT, lng: float = SG_LNG, user: dict = Depends(auth.get_current_user)):
    cond = await nea.get_conditions(lat, lng)
    profile = {"user_type": user.get("user_type"), **{"profile": user.get("profile", {})}}
    scored = nea.compute_risk(cond, user.get("profile", {}))
    return {"conditions": cond, "risk": scored, "user_type": user.get("user_type")}


# ---------- Cooling routes ----------
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


# ---------- Emergency ----------
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
    return {"contacts": user.get("emergency_contacts", [])}


@api.post("/emergency/contacts")
async def add_contact(c: EmergencyContact, user: dict = Depends(auth.get_current_user)):
    contact = c.model_dump()
    contact["id"] = str(ObjectId())
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$push": {"emergency_contacts": contact}})
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    return {"contacts": doc.get("emergency_contacts", [])}


@api.delete("/emergency/contacts/{contact_id}")
async def delete_contact(contact_id: str, user: dict = Depends(auth.get_current_user)):
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$pull": {"emergency_contacts": {"id": contact_id}}})
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    return {"contacts": doc.get("emergency_contacts", [])}


@api.post("/emergency/sos")
async def sos(data: SosInput, user: dict = Depends(auth.get_current_user)):
    """Real SOS: log event, push to this user's devices, return call/SMS links for caregivers."""
    contacts = user.get("emergency_contacts", []) or []
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
        push_sent = await push.push_to_user(db, user, {
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
    await db.sos_events.insert_one(dict(event))

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


# ---------- Profile ----------
@api.put("/profile")
async def update_profile(data: ProfileUpdate, user: dict = Depends(auth.get_current_user)):
    updates = {}
    if data.user_type is not None:
        updates["user_type"] = data.user_type
    if data.onboarded is not None:
        updates["onboarded"] = data.onboarded
    prof = {}
    if data.age_group is not None:
        prof["age_group"] = data.age_group
    if data.health_flags is not None:
        prof["health_flags"] = data.health_flags
    if data.outdoor_exposure is not None:
        prof["outdoor_exposure"] = data.outdoor_exposure
    for k, v in prof.items():
        updates[f"profile.{k}"] = v
    if updates:
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": updates})
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    doc["id"] = str(doc.pop("_id"))
    doc.pop("password_hash", None)
    return doc


# ---------- AI ----------
@api.get("/ai/status")
async def ai_status():
    """Public health check — confirms the LLM provider is live."""
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
    profile = {"user_type": user.get("user_type"), "profile": user.get("profile", {})}
    session_key = f"{user['id']}:{data.session_id}"

    history_doc = await db.chat_sessions.find_one({"session_key": session_key})
    history = history_doc.get("messages", []) if history_doc else []

    # Always pull fresh NEA + forecast for this turn (fallback to Singapore centre)
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

    async def gen():
        full = ""
        async for chunk in ai.stream_chat(
            session_key,
            data.message,
            profile,
            history,
            cond,
            risk,
            forecast,
            spots,
        ):
            full += chunk
            yield chunk
        new_history = history + [
            {"role": "user", "content": data.message},
            {"role": "assistant", "content": full},
        ]
        await db.chat_sessions.update_one(
            {"session_key": session_key},
            {"$set": {"session_key": session_key, "user_id": user["id"], "messages": new_history[-40:],
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    if cond:
        headers["X-HeatShield-Heat-Level"] = str(cond.get("heat_level", ""))
        headers["X-HeatShield-WBGT"] = str((cond.get("wbgt") or {}).get("value", ""))
        headers["X-HeatShield-Temp"] = str((cond.get("air_temperature") or {}).get("value", ""))

    return StreamingResponse(gen(), media_type="text/plain", headers=headers)


@api.get("/chat/history")
async def chat_history(session_id: str = "default", user: dict = Depends(auth.get_current_user)):
    doc = await db.chat_sessions.find_one({"session_key": f"{user['id']}:{session_id}"})
    return {"messages": doc.get("messages", []) if doc else []}


# ---------- Saved locations ----------
@api.get("/locations")
async def get_locations(user: dict = Depends(auth.get_current_user)):
    return {"locations": user.get("saved_locations", [])}


@api.post("/locations")
async def add_location(data: SavedLocationInput, user: dict = Depends(auth.get_current_user)):
    loc = {"id": str(ObjectId()), "label": data.label, "lat": data.lat, "lng": data.lng}
    # replace an existing same-label (Home/Work) rather than duplicate
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$pull": {"saved_locations": {"label": data.label}}})
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$push": {"saved_locations": loc}})
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    return {"locations": doc.get("saved_locations", [])}


@api.delete("/locations/{loc_id}")
async def delete_location(loc_id: str, user: dict = Depends(auth.get_current_user)):
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$pull": {"saved_locations": {"id": loc_id}}})
    doc = await db.users.find_one({"_id": ObjectId(user["id"])})
    return {"locations": doc.get("saved_locations", [])}


# ---------- Web Push ----------
@api.get("/push/vapid-public-key")
async def vapid_public_key():
    return {"public_key": os.environ.get("VAPID_PUBLIC_KEY")}


@api.post("/push/subscribe")
async def push_subscribe(data: PushSubscribeInput, user: dict = Depends(auth.get_current_user)):
    endpoint = data.subscription.get("endpoint")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$pull": {"push_subscriptions": {"endpoint": endpoint}}})
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$push": {"push_subscriptions": data.subscription}})
    return {"ok": True}


@api.post("/push/unsubscribe")
async def push_unsubscribe(data: PushSubscribeInput, user: dict = Depends(auth.get_current_user)):
    endpoint = data.subscription.get("endpoint")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$pull": {"push_subscriptions": {"endpoint": endpoint}}})
    return {"ok": True}


@api.put("/push/threshold")
async def set_threshold(data: NotifyThresholdInput, user: dict = Depends(auth.get_current_user)):
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"notify_threshold": data.threshold}})
    return {"ok": True, "threshold": data.threshold}


@api.put("/push/quiet-hours")
async def set_quiet_hours(data: QuietHoursInput, user: dict = Depends(auth.get_current_user)):
    qh = {"enabled": data.enabled, "start": data.start % 24, "end": data.end % 24}
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"quiet_hours": qh}})
    return {"ok": True, "quiet_hours": qh}


@api.post("/push/test")
async def push_test(user: dict = Depends(auth.get_current_user)):
    full = await db.users.find_one({"_id": ObjectId(user["id"])})
    u = {**full, "id": str(full["_id"])}
    payload = {
        "title": "HeatShield SG test alert",
        "body": "Notifications are on. You'll be alerted here even with the app closed.",
        "url": "/",
        "tag": "heat-test",
    }
    sent = await push.push_to_user(db, u, payload)
    if sent == 0:
        raise HTTPException(status_code=400, detail="No active push subscription. Enable notifications first.")
    return {"ok": True, "sent": sent}


# ---------- Wire up ----------
app.include_router(auth.auth_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    auth.init_auth(db)
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await auth.seed_admin(db)
    asyncio.create_task(push.monitor_loop(db, nea.get_conditions, nea.compute_risk))
    logger.info("HeatShield SG API ready")


@app.on_event("shutdown")
async def shutdown():
    client.close()
