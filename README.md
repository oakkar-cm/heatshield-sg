# HeatShield SG

Singapore climate-resilience PWA for live heat awareness, cool-spot routing, AI advice, and emergency SOS.

**Live app:** [https://heatshieldsg.vercel.app](https://heatshieldsg.vercel.app)  
**API:** [https://heatshieldsg-api.vercel.app](https://heatshieldsg-api.vercel.app)  
**Repo:** [github.com/oakkar-cm/heatshield-sg](https://github.com/oakkar-cm/heatshield-sg)

### Demo login

| | |
|--|--|
| Email | `admin@heatshield.sg` |
| Password | `admin123` |

## Features

- **Live weather** — NEA heat-stress stations + Open-Meteo location temperature, feels-like, humidity, and hourly forecast
- **Personal heat risk** — score from live conditions and your profile (age, health flags, outdoor exposure)
- **Onboarding** — user type + optional health conditions (Skip supported)
- **Map** — live NEA heat stations (colour = stress level), cool spots, rainfall gauges overlay
- **Cooling routes** — nearest malls, parks, libraries, community clubs with Google Maps walking directions
- **Ask AI** — ChatGPT-style UI with word-by-word replies; Groq grounded in live Singapore conditions
- **SOS** — logs the event, pushes to your devices, one-tap Call / SMS to caregivers with your location
- **PWA + push** — Add to Home Screen; Web Push heat alerts (iOS needs Home Screen install)

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React (CRA/craco), Tailwind, Google Maps |
| Backend | FastAPI, SQLite, JWT auth |
| Hosting | Vercel (frontend + serverless API) |
| Weather | NEA data.gov.sg, Open-Meteo |
| AI | Groq (`llama-3.1-8b-instant`) |
| Push | Web Push (VAPID) |

## Architecture (production)

```
Browser  →  https://heatshieldsg.vercel.app
              │
              ├─ static React PWA
              └─ /api/*  (Vercel rewrite)
                    │
                    ▼
              https://heatshieldsg-api.vercel.app  (FastAPI)
```

- Frontend proxies `/api` to the API so auth cookies stay same-origin.
- SQLite on Vercel is per-instance (`/tmp`); JWT embeds profile / push subscription so auth and onboarding survive cold starts.
- Background heat monitor is skipped on Vercel; a daily cron hits `/api/cron/heat-alerts`. Prefer **Test alert** / SOS for reliable push demos.

## Quick start (local)

### Prerequisites

- Node.js 18+
- Python 3.11+

No MongoDB. The API uses a local **SQLite** file (`backend/data/heatshield.db`).

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set JWT_SECRET, GROQ_API_KEY, VAPID keys, etc.
uvicorn server:app --host 127.0.0.1 --port 8001
```

API: `http://127.0.0.1:8001`

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Set REACT_APP_GOOGLE_MAPS_API_KEY and REACT_APP_VAPID_PUBLIC_KEY
# Keep REACT_APP_BACKEND_URL empty to use the CRA proxy → 8001
npm start
```

App: `http://localhost:3000`

## Deploy on Vercel

### API project (`heatshieldsg-api`)

| Setting | Value |
|---------|--------|
| Root Directory | `backend` |
| Entry | `app.py` (exports FastAPI `app`) |

Set env vars from `backend/.env.example` (at least `JWT_SECRET`, `FRONTEND_URL`, `CORS_ORIGINS`, `GROQ_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`).

### Frontend project (`heatshieldsg`)

| Setting | Value |
|---------|--------|
| Root Directory | `frontend` |
| Build | `npm run build` (see `frontend/vercel.json`) |
| Output | `build` |

| Variable | Value |
|----------|--------|
| `REACT_APP_BACKEND_URL` | leave empty (use same-origin `/api` proxy) |
| `REACT_APP_GOOGLE_MAPS_API_KEY` | Maps JavaScript API key |
| `REACT_APP_VAPID_PUBLIC_KEY` | same as backend public key |

In Google Cloud, allow HTTP referrer `https://heatshieldsg.vercel.app/*` for the Maps key.

`frontend/vercel.json` rewrites `/api/:path*` → `https://heatshieldsg-api.vercel.app/api/:path*`.

### Optional: Render (long-lived API)

See `render.yaml` if you want a persistent process (better for continuous heat-alert monitoring than Vercel serverless).

## Environment

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `SQLITE_PATH` | Optional SQLite path (default `data/heatshield.db`; Vercel uses `/tmp`) |
| `JWT_SECRET` | Auth signing secret |
| `CORS_ORIGINS` | Allowed frontends (comma-separated) |
| `FRONTEND_URL` | Cookie Secure flag + frontend origin (`https://heatshieldsg.vercel.app`) |
| `GROQ_API_KEY` | Groq API key for AI |
| `GROQ_MODEL` | e.g. `llama-3.1-8b-instant` |
| `VAPID_*` | Web Push keys |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Seed admin on startup |
| `CRON_SECRET` | Optional bearer for `/api/cron/heat-alerts` |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|----------|---------|
| `REACT_APP_BACKEND_URL` | Empty for local proxy / Vercel rewrite; set only for a direct API URL |
| `REACT_APP_GOOGLE_MAPS_API_KEY` | Google Maps JavaScript API key |
| `REACT_APP_VAPID_PUBLIC_KEY` | Must match backend VAPID public key |

**Do not commit real `.env` files.** Use `.env.example` as templates.

## Mobile (Add to Home Screen)

1. Use the live HTTPS app (or LAN + HTTPS).
2. **iPhone (Safari):** Share → **Add to Home Screen**. Open from the icon; enable notifications for lock-screen alerts (iOS 16.4+).
3. **Android (Chrome):** in-app **Install app** card, or Chrome menu → Install / Add to Home screen.

Push needs notification permission. On iPhone, only the installed Home Screen app can receive Web Push.

## Map legend

| Colour | Meaning |
|--------|---------|
| Green / amber / red pins | Live NEA heat-stress stations (Low → Very High) |
| Blue pins | Cool spots (malls, parks, libraries, CCs) |
| Cyan / blue (rainfall toggle) | NEA rain gauges — cyan = 0 mm, blue = raining |

If **Show rainfall** looks unchanged, Singapore may simply have **0 mm** at all gauges; the status line under the button reports that.

## Project layout

```
heatshield-sg/
├── backend/          # FastAPI API, NEA/Open-Meteo, AI, push, auth
│   ├── app.py        # Vercel entry
│   ├── server.py
│   └── vercel.json   # daily heat-alert cron
├── frontend/         # React PWA
│   └── vercel.json   # /api proxy + SPA rewrites
├── memory/           # Product notes
└── README.md
```

## API highlights

| Endpoint | Description |
|----------|-------------|
| `GET /api/conditions` | Live conditions for lat/lng |
| `GET /api/risk` | Personalised risk (auth) |
| `GET /api/forecast` | Live hourly feels-like forecast |
| `GET /api/map/wbgt` | Heat-stress stations |
| `GET /api/map/rainfall` | Rain gauges |
| `GET /api/cooling/spots` | Nearest cool spots |
| `POST /api/chat` | AI advice JSON `{ reply }` (auth) |
| `POST /api/emergency/sos` | SOS log + push + caregiver links |
| `POST /api/push/test` | Send a test notification (auth) |
| `GET /api/cron/heat-alerts` | Cron tick for heat alerts |

## Notes

- Weather copy stays simple (temperature, feels like, heat stress) — no WBGT jargon in the UI.
- Cool spots are curated real Singapore venues; routes open Google Maps walking directions.
- SOS does not auto-SMS caregivers without your tap (Call / SMS links); it can push to your own devices when subscribed.
- Design-sprint IT prototype: SQLite + JWT; not a full production multi-region database.

## License

Private / project use unless otherwise stated.
