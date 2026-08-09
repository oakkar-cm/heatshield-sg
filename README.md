# HeatShield SG

Singapore climate-resilience PWA for live heat awareness, cool-spot routing, AI advice, and emergency SOS.

**Repo:** [github.com/oakkar-cm/heatshield-sg](https://github.com/oakkar-cm/heatshield-sg)

## Features

- **Live weather** — NEA heat-stress stations + Open-Meteo location temperature, feels-like, humidity, and hourly forecast
- **Personal heat risk** — score based on live conditions and your profile (age, health, outdoor exposure)
- **Map** — heat stations, rainfall, and real Singapore cool spots
- **Cooling routes** — nearest malls, parks, libraries, community clubs with Google Maps walking directions
- **Ask AI** — Groq-powered chat grounded in live conditions
- **SOS** — logs the event, pushes to your devices, one-tap Call / SMS to caregivers with your location
- **PWA** — Add to Home Screen; Web Push heat alerts (best over HTTPS; iOS needs Home Screen install)

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React (CRA/craco), Tailwind, Google Maps |
| Backend | FastAPI, Motor/MongoDB, JWT auth |
| Weather | NEA data.gov.sg, Open-Meteo |
| AI | Groq (`llama-3.1-8b-instant`) |
| Push | Web Push (VAPID) |

## Quick start

### Prerequisites

- Node.js 18+
- Python 3.11+
- MongoDB running on `localhost:27017`

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

On first run, register an account (or use the seeded admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `backend/.env` if you set them).

## Environment

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | Database name |
| `JWT_SECRET` | Auth signing secret |
| `CORS_ORIGINS` | Allowed frontends (comma-separated) |
| `FRONTEND_URL` | Cookie / CORS frontend origin |
| `GROQ_API_KEY` | Groq API key for AI |
| `GROQ_MODEL` | e.g. `llama-3.1-8b-instant` |
| `VAPID_*` | Web Push keys |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Optional seed admin on startup |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|----------|---------|
| `REACT_APP_BACKEND_URL` | Leave empty for local proxy; set for deployed API |
| `REACT_APP_GOOGLE_MAPS_API_KEY` | Google Maps JavaScript API key |
| `REACT_APP_VAPID_PUBLIC_KEY` | Must match backend VAPID public key |

**Do not commit real `.env` files.** Use `.env.example` as templates.

## Mobile (Add to Home Screen)

1. Serve the app over the network (same Wi‑Fi) or deploy with **HTTPS**.
2. **iPhone (Safari):** Share → **Add to Home Screen**. Open from the icon; enable notifications for lock-screen heat alerts (iOS 16.4+).
3. **Android (Chrome):** Use the in-app **Install app** card, or Chrome menu → Install / Add to Home screen.

Push alerts need a subscribed browser and (on iOS) the installed Home Screen app.

## Project layout

```
heatshield-sg/
├── backend/          # FastAPI API, NEA/Open-Meteo, AI, push, auth
├── frontend/         # React PWA
├── memory/           # Product notes
└── README.md
```

## API highlights

| Endpoint | Description |
|----------|-------------|
| `GET /api/conditions` | Live conditions for lat/lng |
| `GET /api/risk` | Personalised risk (auth) |
| `GET /api/forecast` | Live hourly feels-like forecast |
| `GET /api/cooling/spots` | Nearest cool spots |
| `POST /api/chat` | Streaming AI advice (auth) |
| `POST /api/emergency/sos` | SOS log + push + caregiver links |

## Notes

- Weather text stays simple (temperature, feels like, heat stress) — no technical jargon in the UI.
- Cool spots are curated real Singapore venues; routes open real Google Maps walking directions.
- SOS does not auto-SMS caregivers without your tap (Call / SMS links); it does push to your own devices when subscribed.

## License

Private / project use unless otherwise stated.
