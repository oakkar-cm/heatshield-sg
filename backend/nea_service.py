"""NEA data ingestion, caching, risk scoring, forecasting and cooling-route logic."""
import asyncio
import time
import math
import httpx
from sg_data import COOLING_SPOTS

WBGT_URL = "https://api-open.data.gov.sg/v2/real-time/api/weather?api=wbgt"
AIR_TEMP_URL = "https://api.data.gov.sg/v1/environment/air-temperature"
RAINFALL_URL = "https://api.data.gov.sg/v1/environment/rainfall"
HUMIDITY_URL = "https://api.data.gov.sg/v1/environment/relative-humidity"
FORECAST_URL = "https://api.data.gov.sg/v1/environment/24-hour-weather-forecast"
TWO_HOUR_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
# Location-gridded current weather. Multi-model consensus is closer to phone apps than a single run.
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lng}"
    "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
    "weather_code,wind_speed_10m,cloud_cover"
    "&hourly=temperature_2m,apparent_temperature,precipitation_probability,weather_code"
    "&timezone=Asia%2FSingapore&forecast_days=1"
)
# Two models in parallel: fast enough for dashboard, still better than a single run
_OPEN_METEO_MODELS = ("best_match", "ecmwf_ifs025")

_cache = {}
_CACHE_TTL = 90  # seconds
_http: httpx.AsyncClient | None = None
_inflight: dict[str, asyncio.Future] = {}


async def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=12.0, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
    return _http

# WMO Weather interpretation codes → consumer-friendly labels (similar to phone weather apps)
_WMO = {
    0: "Clear",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Cloudy",
    45: "Foggy",
    48: "Foggy",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Heavy Drizzle",
    61: "Light Rain",
    63: "Rain",
    65: "Heavy Rain",
    80: "Light Showers",
    81: "Showers",
    82: "Heavy Showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}

# NEA 2-hour area wording → simple labels closer to iOS Weather
_NEA_CONDITION = {
    "fair": "Clear",
    "fair (day)": "Clear",
    "fair (night)": "Clear",
    "fair & warm": "Clear",
    "partly cloudy": "Partly Cloudy",
    "partly cloudy (day)": "Partly Cloudy",
    "partly cloudy (night)": "Partly Cloudy",
    "cloudy": "Cloudy",
    "hazy": "Hazy",
    "slightly hazy": "Hazy",
    "windy": "Windy",
    "mist": "Mist",
    "fog": "Foggy",
    "light rain": "Light Rain",
    "light showers": "Light Showers",
    "showers": "Showers",
    "moderate rain": "Rain",
    "heavy rain": "Heavy Rain",
    "heavy showers": "Heavy Showers",
    "passing showers": "Showers",
    "thundery showers": "Thunderstorms",
    "heavy thundery showers": "Thunderstorms",
    "heavy thundery showers with gusty winds": "Thunderstorms",
}


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _fetch(url):
    now = time.time()
    cached = _cache.get(url)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    # Deduplicate concurrent fetches for the same URL (dashboard hits /risk + /forecast together)
    existing = _inflight.get(url)
    if existing is not None:
        return await existing

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _inflight[url] = fut
    try:
        client = await _client()
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        _cache[url] = (time.time(), data)
        fut.set_result(data)
        return data
    except Exception as e:
        fut.set_exception(e)
        raise
    finally:
        _inflight.pop(url, None)


def heat_level_meta(level: str):
    m = {
        "low": {"label": "Low", "color": "low", "message": "Conditions are comfortable. Stay hydrated."},
        "moderate": {"label": "Moderate", "color": "moderate", "message": "Take regular breaks and drink water."},
        "high": {"label": "High", "color": "high", "message": "Limit outdoor exertion. Seek shade and hydrate often."},
        "very high": {"label": "Very High", "color": "extreme", "message": "Avoid outdoor activity. Stay in cool areas."},
        "extreme": {"label": "Extreme", "color": "extreme", "message": "Dangerous heat. Remain indoors and cool."},
    }
    return m.get(level.lower(), m["low"])


def _wbgt_to_level(wbgt: float) -> str:
    if wbgt < 31.0:
        return "low"
    if wbgt <= 32.0:
        return "moderate"
    if wbgt <= 33.0:
        return "high"
    return "very high"


async def get_wbgt_stations():
    data = await _fetch(WBGT_URL)
    records = data.get("data", {}).get("records", [])
    if not records:
        return []
    readings = records[0].get("item", {}).get("readings", [])
    out = []
    for r in readings:
        loc = r.get("location", {})
        try:
            wbgt = float(r.get("wbgt"))
        except (TypeError, ValueError):
            continue
        stress = (r.get("heatStress") or _wbgt_to_level(wbgt)).lower()
        out.append({
            "station_id": r.get("station", {}).get("id"),
            "name": r.get("station", {}).get("name"),
            "lat": float(loc.get("latitude")),
            "lng": float(loc.get("longitude")),
            "wbgt": wbgt,
            "level": stress if stress in ("low", "moderate", "high", "very high") else _wbgt_to_level(wbgt),
        })
    return out


async def _latest_station_readings(url):
    data = await _fetch(url)
    stations = {s["id"]: s for s in data.get("metadata", {}).get("stations", [])}
    items = data.get("items", [])
    if not items:
        return [], None
    latest = items[-1]
    ts = latest.get("timestamp")
    out = []
    for rd in latest.get("readings", []):
        st = stations.get(rd["station_id"])
        if not st:
            continue
        out.append({
            "station_id": rd["station_id"],
            "name": st["name"],
            "lat": st["location"]["latitude"],
            "lng": st["location"]["longitude"],
            "value": rd["value"],
        })
    return out, ts


def _nearest(items, lat, lng):
    best, best_d = None, 1e9
    for it in items:
        d = _haversine(lat, lng, it["lat"], it["lng"])
        if d < best_d:
            best, best_d = it, d
    return best, (round(best_d, 2) if best else None)


async def get_air_temperature():
    return await _latest_station_readings(AIR_TEMP_URL)


async def get_rainfall():
    return await _latest_station_readings(RAINFALL_URL)


async def get_humidity():
    return await _latest_station_readings(HUMIDITY_URL)


def _weather_label(code) -> str:
    try:
        return _WMO.get(int(code), "Unknown")
    except (TypeError, ValueError):
        return "Unknown"


def _nea_condition_label(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if key in _NEA_CONDITION:
        return _NEA_CONDITION[key]
    # Soft match: keep readable Title Case without "(Day)/(Night)"
    cleaned = raw.replace("(Day)", "").replace("(Night)", "").replace("(day)", "").replace("(night)", "")
    return " ".join(cleaned.split()).title() or None


def _median(values):
    nums = sorted(v for v in values if isinstance(v, (int, float)))
    if not nums:
        return None
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return round((nums[mid - 1] + nums[mid]) / 2, 1)


def _heat_index_c(temp_c: float, rh: float) -> float | None:
    """NWS heat-index style feels-like (common in consumer weather apps)."""
    if temp_c is None or rh is None:
        return None
    # Below ~27°C heat index is not used; fall back to air temp
    t_f = temp_c * 9 / 5 + 32
    if t_f < 80:
        return None
    hi = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 0.00683783 * t_f * t_f
        - 0.05481717 * rh * rh
        + 0.00122874 * t_f * t_f * rh
        + 0.00085282 * t_f * rh * rh
        - 0.00000199 * t_f * t_f * rh * rh
    )
    if rh < 13 and 80 <= t_f <= 112:
        hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t_f - 95)) / 17)
    if rh > 85 and 80 <= t_f <= 87:
        hi += ((rh - 85) / 10) * ((87 - t_f) / 5)
    return round((hi - 32) * 5 / 9, 1)


def _feels_like_c(temp_c, apparent_c, humidity_pct):
    """Prefer heat-index in humid heat (closer to phone apps); else model apparent temp."""
    hi = _heat_index_c(temp_c, humidity_pct) if isinstance(temp_c, (int, float)) and isinstance(humidity_pct, (int, float)) else None
    candidates = [v for v in (apparent_c, hi) if isinstance(v, (int, float))]
    if not candidates:
        return temp_c
    # In Singapore humidity, take the warmer of the two so "feels like" tracks phone apps better
    return round(max(candidates), 1)


async def get_local_weather(lat: float, lng: float):
    """Gridded current weather via multi-model consensus (closer to phone weather apps)."""
    # Round coords so nearby refreshes share cache
    lat_r, lng_r = round(lat, 3), round(lng, 3)

    async def _one(model: str):
        url = OPEN_METEO_URL.format(lat=lat_r, lng=lng_r)
        if model and model != "best_match":
            url = f"{url}&models={model}"
        data = await _fetch(url)
        return data.get("current") or {}

    results = await asyncio.gather(*[_one(m) for m in _OPEN_METEO_MODELS], return_exceptions=True)
    snapshots = []
    for cur in results:
        if isinstance(cur, Exception):
            continue
        if cur.get("temperature_2m") is None:
            continue
        snapshots.append(cur)

    if not snapshots:
        return None

    temp = _median([c.get("temperature_2m") for c in snapshots])
    apparent = _median([c.get("apparent_temperature") for c in snapshots])
    humidity = _median([c.get("relative_humidity_2m") for c in snapshots])
    precip = _median([c.get("precipitation") for c in snapshots])
    wind = _median([c.get("wind_speed_10m") for c in snapshots])
    clouds = _median([c.get("cloud_cover") for c in snapshots])
    # Mode-ish: prefer majority weather code from models
    codes = [c.get("weather_code") for c in snapshots if c.get("weather_code") is not None]
    code = None
    if codes:
        code = max(set(codes), key=codes.count)

    return {
        "temperature_c": temp,
        "feels_like_c": _feels_like_c(temp, apparent, humidity),
        "humidity_pct": humidity,
        "precipitation_mm": precip if precip is not None else 0,
        "wind_kmh": wind,
        "cloud_cover_pct": clouds,
        "weather_code": code,
        "condition": _weather_label(code),
        "observed_at": snapshots[0].get("time"),
        "source": "open-meteo-consensus",
    }


async def get_area_forecast(lat: float, lng: float):
    """NEA 2-hour area forecast nearest to the user."""
    try:
        data = await _fetch(TWO_HOUR_URL)
    except Exception:
        return None
    areas = {a["name"]: a["label_location"] for a in data.get("area_metadata", [])}
    items = data.get("items") or []
    if not items:
        return None
    forecasts = items[0].get("forecasts") or []
    best, best_d, best_name = None, 1e9, None
    for f in forecasts:
        name = f.get("area")
        loc = areas.get(name)
        if not loc:
            continue
        d = _haversine(lat, lng, loc["latitude"], loc["longitude"])
        if d < best_d:
            best, best_d, best_name = f.get("forecast"), d, name
    if best is None:
        return None
    return {"area": best_name, "forecast": best, "distance_km": round(best_d, 2)}


async def get_conditions(lat: float, lng: float):
    """Live snapshot: location weather (app-style) + NEA WBGT / rainfall stations."""
    cache_key = f"conditions:{round(lat, 3)}:{round(lng, 3)}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]

    existing = _inflight.get(cache_key)
    if existing is not None:
        return await existing

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _inflight[cache_key] = fut
    try:
        result = await _build_conditions(lat, lng)
        _cache[cache_key] = (time.time(), result)
        fut.set_result(result)
        return result
    except Exception as e:
        fut.set_exception(e)
        raise
    finally:
        _inflight.pop(cache_key, None)


async def _build_conditions(lat: float, lng: float):
    """Fetch all weather sources in parallel, then assemble the snapshot."""
    wbgt_stations, temp_pack, rain_pack, hum_pack, local, area_fc = await asyncio.gather(
        get_wbgt_stations(),
        get_air_temperature(),
        get_rainfall(),
        get_humidity(),
        get_local_weather(lat, lng),
        get_area_forecast(lat, lng),
    )
    temps, temp_ts = temp_pack
    rains, _ = rain_pack
    hums, _ = hum_pack

    w, wd = _nearest(wbgt_stations, lat, lng)
    t, td = _nearest(temps, lat, lng)
    r, rd = _nearest(rains, lat, lng)
    h, hd = _nearest(hums, lat, lng)

    # Prefer location-gridded air temp/humidity (matches phone weather apps better).
    # NEA air-temp feed can be sparse (sometimes a single station island-wide).
    air_value = local["temperature_c"] if local and local.get("temperature_c") is not None else (t["value"] if t else None)
    air_station = "Your location" if local and local.get("temperature_c") is not None else (t["name"] if t else None)
    air_dist = 0.0 if local and local.get("temperature_c") is not None else td
    hum_value = local["humidity_pct"] if local and local.get("humidity_pct") is not None else (h["value"] if h else None)
    rain_value = (
        local["precipitation_mm"]
        if local and local.get("precipitation_mm") is not None
        else (r["value"] if r else 0)
    )

    level = w["level"] if w else "low"
    meta = heat_level_meta(level)
    # Prefer NEA area wording for Singapore (closer to local / phone-app condition text)
    condition = _nea_condition_label((area_fc or {}).get("forecast")) or (local or {}).get("condition")

    return {
        "timestamp": (local or {}).get("observed_at") or temp_ts,
        "location": {"lat": lat, "lng": lng},
        "condition": condition,
        "feels_like": {"value": (local or {}).get("feels_like_c"), "unit": "deg C"},
        "wind": {"value": (local or {}).get("wind_kmh"), "unit": "km/h"},
        "cloud_cover": {"value": (local or {}).get("cloud_cover_pct"), "unit": "%"},
        "wbgt": {"value": w["wbgt"] if w else None, "station": w["name"] if w else None, "distance_km": wd},
        "air_temperature": {
            "value": air_value,
            "station": air_station,
            "distance_km": air_dist,
            "nea_station": t["name"] if t else None,
            "nea_value": t["value"] if t else None,
            "source": "open-meteo-consensus" if local and local.get("temperature_c") is not None else "nea",
        },
        "rainfall": {
            "value": rain_value,
            "station": r["name"] if r else None,
            "distance_km": rd,
        },
        "humidity": {
            "value": hum_value,
            "station": "Your location" if local and local.get("humidity_pct") is not None else (h["name"] if h else None),
            "distance_km": 0.0 if local and local.get("humidity_pct") is not None else hd,
            "source": "open-meteo-consensus" if local and local.get("humidity_pct") is not None else "nea",
        },
        "area_forecast": area_fc,
        "heat_level": level,
        "heat_meta": meta,
    }


def compute_risk(conditions: dict, profile: dict):
    """Personalised heat-risk score 0-100 from conditions + user profile."""
    level = conditions.get("heat_level", "low")
    base = {"low": 20, "moderate": 45, "high": 70, "very high": 90}.get(level, 20)
    score = base

    temp = conditions.get("air_temperature", {}).get("value")
    if isinstance(temp, (int, float)):
        if temp >= 34:
            score += 12
        elif temp >= 32:
            score += 6

    hum = conditions.get("humidity", {}).get("value")
    if isinstance(hum, (int, float)) and hum >= 75:
        score += 6

    profile = profile or {}
    age = profile.get("age_group", "adult")
    if age == "elderly":
        score += 15
    elif age == "child":
        score += 10

    flags = profile.get("health_flags", []) or []
    score += min(len(flags) * 6, 18)

    exposure = profile.get("outdoor_exposure", "low")
    if exposure == "high":
        score += 12
    elif exposure == "medium":
        score += 6

    score = max(0, min(100, round(score)))
    if score < 35:
        band, color = "Low", "low"
    elif score < 60:
        band, color = "Moderate", "moderate"
    elif score < 80:
        band, color = "High", "high"
    else:
        band, color = "Very High", "extreme"

    factors = []
    if age == "elderly":
        factors.append("Elderly are more vulnerable to heat stress")
    if flags:
        factors.append(f"{len(flags)} health condition(s) increase your risk")
    if exposure == "high":
        factors.append("High outdoor exposure raises heat load")
    if isinstance(temp, (int, float)) and temp >= 32:
        factors.append(f"Air temperature is {temp}°C")
    if not factors:
        factors.append("Conditions are currently favourable")

    return {"score": score, "band": band, "color": color, "factors": factors}


def _feels_to_level(feels: float) -> str:
    """Map feels-like °C to a simple heat-stress band for forecast points."""
    if feels < 30:
        return "low"
    if feels < 32:
        return "moderate"
    if feels < 34:
        return "high"
    return "very high"


async def get_forecast(lat: float, lng: float):
    """Next-hours forecast from live Open-Meteo hourly + NEA 24h outlook."""
    from datetime import datetime, timezone, timedelta

    lat_r, lng_r = round(lat, 3), round(lng, 3)
    hourly_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat_r}&longitude={lng_r}"
        "&hourly=temperature_2m,apparent_temperature,precipitation_probability,weather_code"
        "&timezone=Asia%2FSingapore&forecast_days=2"
    )

    om_result, fc_result = await asyncio.gather(
        _fetch(hourly_url),
        _fetch(FORECAST_URL),
        return_exceptions=True,
    )
    if isinstance(fc_result, Exception):
        fc_result = {}
    item = ((fc_result or {}).get("items") or [{}])[0]
    general = item.get("general", {})
    t_high = general.get("temperature", {}).get("high")
    t_low = general.get("temperature", {}).get("low")

    points = []
    peak = {"hour": None, "feels_like": -1, "wbgt": -1, "label": None, "level": "low"}

    if not isinstance(om_result, Exception):
        hourly = om_result.get("hourly") or {}
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        feels_arr = hourly.get("apparent_temperature") or []
        now = datetime.now(timezone(timedelta(hours=8))).replace(minute=0, second=0, microsecond=0)

        for i, ts in enumerate(times):
            if i >= len(temps) or temps[i] is None:
                continue
            try:
                t = datetime.fromisoformat(ts)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone(timedelta(hours=8)))
            except ValueError:
                continue
            if t < now:
                continue
            feels = feels_arr[i] if i < len(feels_arr) and feels_arr[i] is not None else temps[i]
            feels = round(float(feels), 1)
            temp = round(float(temps[i]), 1)
            lvl = _feels_to_level(feels)
            label = f"{t.hour:02d}:00"
            # wbgt key kept for chart/API compatibility — value is live feels-like °C
            points.append({
                "time": label,
                "hour": t.hour,
                "temp": temp,
                "feels_like": feels,
                "wbgt": feels,
                "level": lvl,
            })
            if feels > peak["feels_like"]:
                peak = {"hour": t.hour, "feels_like": feels, "wbgt": feels, "level": lvl, "label": label}
            if len(points) >= 9:
                break

    if not points:
        # Last resort: current conditions only (still live, not a fake curve)
        cond = await get_conditions(lat, lng)
        feels = (cond.get("feels_like") or {}).get("value") or (cond.get("air_temperature") or {}).get("value") or 30
        temp = (cond.get("air_temperature") or {}).get("value") or feels
        lvl = _feels_to_level(float(feels))
        now = datetime.now(timezone(timedelta(hours=8)))
        label = f"{now.hour:02d}:00"
        points = [{"time": label, "hour": now.hour, "temp": temp, "feels_like": feels, "wbgt": feels, "level": lvl}]
        peak = {"hour": now.hour, "feels_like": feels, "wbgt": feels, "level": lvl, "label": label}

    nea_text = general.get("forecast")
    summary = (
        f"Feels-like heat peaks around {peak['label']} "
        f"({heat_level_meta(peak['level'])['label'].lower()} - about {peak['feels_like']} C)."
    )
    if nea_text:
        summary = f"{summary} NEA outlook: {nea_text}."

    return {
        "location": {"lat": lat, "lng": lng},
        "forecast_general": nea_text,
        "temp_range": {"low": t_low, "high": t_high},
        "points": points,
        "peak": peak,
        "summary": summary,
        "source": "open-meteo-hourly+nea",
    }


def nearest_cooling_spots(lat: float, lng: float, limit=5):
    spots = []
    for s in COOLING_SPOTS:
        d = _haversine(lat, lng, s["lat"], s["lng"])
        spots.append({**s, "distance_km": round(d, 2)})
    spots.sort(key=lambda x: x["distance_km"])
    return spots[:limit]


def build_route(lat: float, lng: float, dest: dict):
    """Real Google Maps walking directions to a cool spot, plus practical tips."""
    gmaps = (f"https://www.google.com/maps/dir/?api=1&origin={lat},{lng}"
             f"&destination={dest['lat']},{dest['lng']}&travelmode=walking")
    tips = [
        "Opens real walking directions in Google Maps from your current location",
        "Use covered linkways, void decks, and bus shelters when possible",
    ]
    if "air-con" in dest.get("amenities", []):
        tips.append("This spot is air-conditioned — a reliable place to cool down")
    if dest.get("type") == "park":
        tips.append("In parks, stay on tree-lined paths and rest in shade")
    tips.append("Bring water — refill at malls, libraries, or community clubs along the way")
    return {"destination": dest, "walking_url": gmaps, "tips": tips}
