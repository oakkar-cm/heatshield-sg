# HeatShield SG — Climate Resilience Platform

## Original Problem Statement
AI-powered heat & extreme-weather resilience web app for Singapore citizens: real-time heat alerts, personalised risk scoring, cooling-route navigation, predictive heat-risk map, AI advisory chatbot, and emergency preparedness. Mobile-first responsive PWA + desktop dashboard.

## User Choices
- AI model: **Claude Haiku 4.5** (`claude-haiku-4-5-20251001` via EMERGENT_LLM_KEY)
- Auth: **JWT email/password** (httpOnly cookies)
- Caregiver/SOS alerts: **in-app only**
- Map provider: **Google Maps** (user-provided key)
- Scope: **IT prototype only**

## Architecture
- Frontend: React 19 (CRA/craco) + Tailwind + shadcn/ui, Google Maps (@react-google-maps/api), Recharts, framer-motion, sonner.
- Backend: FastAPI, all routes under `/api`. Modules: `server.py`, `auth.py`, `nea_service.py` (NEA fetch/cache/risk/forecast/routes), `ai_service.py` (Claude), `sg_data.py` (cool spots, checklists, symptom rules).
- DB: MongoDB (users, chat_sessions, sos_events, login_attempts).
- Data: Live NEA data.gov.sg (WBGT v2, air-temperature, rainfall, humidity, 24h forecast).

## User Personas
1. Citizens — daily heat awareness, alerts, safe routes.
2. Elderly/vulnerable — Simplified Mode (larger UI), caregiver contacts, SOS.
3. Outdoor workers — WBGT work/rest guidance.

## Implemented (2026-08-09)
- JWT auth (register/login/logout/me/refresh), brute-force lockout, admin seed.
- Onboarding: user type + health flags → personalised profile.
- Dashboard: live heat level card, personal risk score (profile-weighted), stat tiles, AI recommendations (Claude), next-hours forecast chart, nearest cool spot.
- Heat-risk map: Google Map with WBGT heat-overlay circles, cooling markers, rainfall toggle; graceful fallback list when key not domain-authorized.
- Cooling routes: nearest cool spots + shade/shelter tips + Google Maps walking link.
- AI chatbot: streaming Claude Haiku 4.5, persisted history, suggestion chips.
- Emergency: SOS countdown + in-app caregiver alert, contacts CRUD, symptom checker (heat stroke detection), preparedness checklists + WBGT work/rest guidance.
- Simplified Mode toggle (accessibility).
- Verified: 24/24 backend pytest pass; 6/7 frontend flows pass (map blocked only by external key restriction).

## Known / External Action Item
- **Google Maps `/map`**: user must whitelist the app domain in Google Cloud Console (HTTP referrers) and enable "Maps JavaScript API". Until then, `/map` shows a live station heat-list fallback.

## Backlog
- P1: Migrate deprecated `google.maps.Marker` → `AdvancedMarkerElement`.
- P2: Browser push notifications when thresholds crossed (currently in-app banner).
- P2: Saved locations; email caregiver alerts (Resend); PWA install/service worker.
- P2: Business Track deliverable (out of current scope).
