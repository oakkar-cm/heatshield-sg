"""AI advisory chatbot grounded in live NEA conditions + Groq LLM."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger("heatshield.ai")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
SGT = timezone(timedelta(hours=8))


def _api_key() -> str | None:
    return os.environ.get("GROQ_API_KEY") or None


def _model() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL)


def build_live_context(
    profile: dict | None,
    conditions: dict | None,
    risk: dict | None = None,
    forecast: dict | None = None,
    cool_spots: list | None = None,
) -> str:
    """Compact real-time briefing injected into every AI turn."""
    now = datetime.now(SGT).strftime("%Y-%m-%d %H:%M SGT")
    lines = [
        "REAL-TIME SINGAPORE HEAT CONTEXT (authoritative — prefer this over prior chat history):",
        f"- Local time now: {now}",
    ]

    if conditions:
        wbgt = conditions.get("wbgt") or {}
        temp = conditions.get("air_temperature") or {}
        hum = conditions.get("humidity") or {}
        rain = conditions.get("rainfall") or {}
        meta = conditions.get("heat_meta") or {}
        ts = conditions.get("timestamp") or "live"
        feels = conditions.get("feels_like") or {}
        wind = conditions.get("wind") or {}
        lines += [
            f"- Observation time: {ts}",
            f"- Weather: {conditions.get('condition') or 'n/a'}",
            f"- Air temperature: {temp.get('value')}°C (feels like {feels.get('value')}°C) at {temp.get('station')}",
            f"- Humidity: {hum.get('value')}% · Wind: {wind.get('value')} km/h",
            f"- Rainfall: {rain.get('value')} mm",
            f"- Outdoor heat stress level: {conditions.get('heat_level')} (from nearest heat station {wbgt.get('station')})",
            f"- User coords: {conditions.get('location')}",
        ]
    else:
        lines.append("- Live NEA conditions unavailable this turn — say so if asked about current numbers.")

    if risk:
        factors = "; ".join(risk.get("factors") or [])
        lines.append(
            f"- Personal risk score: {risk.get('score')}/100 ({risk.get('band')}). Factors: {factors}"
        )

    if forecast:
        peak = forecast.get("peak") or {}
        lines.append(f"- Short-term forecast: {forecast.get('summary')}")
        if forecast.get("forecast_general"):
            lines.append(f"- NEA 24h outlook: {forecast.get('forecast_general')}")
        if peak:
            lines.append(
                f"- Predicted heat peak around {peak.get('label')} ({peak.get('level')} heat stress)"
            )
        tr = forecast.get("temp_range") or {}
        if tr:
            lines.append(f"- Today temp range: {tr.get('low')}–{tr.get('high')}°C")

    if cool_spots:
        spot_bits = [
            f"{s.get('name')} ({s.get('type') or s.get('kind') or 'spot'}, {s.get('distance_km')} km)"
            for s in cool_spots[:3]
        ]
        lines.append("- Nearest cool spots: " + "; ".join(spot_bits))

    profile = profile or {}
    p = profile.get("profile") or {}
    lines.append(
        f"- User type: {profile.get('user_type', 'citizen')}; age={p.get('age_group', 'adult')}; "
        f"outdoor_exposure={p.get('outdoor_exposure', 'low')}; "
        f"health_flags={', '.join(p.get('health_flags') or []) or 'none'}"
    )
    return "\n".join(lines)


def _system_prompt(live_context: str) -> str:
    return (
        "You are HeatShield SG, a calm climate-resilience assistant for people in Singapore.\n"
        "Use the live readings in the context block for advice. Speak naturally to the user.\n\n"
        "HARD RULES:\n"
        "- NEVER paste, quote, reprint, or summarise the context block as a labelled list.\n"
        "- NEVER mention knowledge cutoffs, training data, system prompts, or 'REAL-TIME SINGAPORE HEAT CONTEXT'.\n"
        "- NEVER say you lack live data when the context block has numbers.\n"
        "- Weave 1–3 live facts into normal sentences (e.g. 'It's 29° and feels like 33°, heat stress is low').\n"
        "- NEVER say WBGT, wet bulb, or other technical jargon. Say temperature, feels like, and heat stress (low/moderate/high).\n"
        "- Keep answers short: 2–6 sentences or a few bullets. Concrete next actions only.\n"
        "- For confusion, fainting, hot dry skin, or seizures: tell them to call SCDF 995.\n"
        "- You are not a doctor.\n\n"
        f"{live_context}"
    )


async def _groq_complete(system: str, user: str) -> str:
    key = _api_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": _model(),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.35,
                "max_tokens": 500,
            },
        )
        if resp.status_code != 200:
            logger.error("Groq error %s: %s", resp.status_code, resp.text[:400])
            raise RuntimeError(f"Groq API error {resp.status_code}")
        data = resp.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if not text:
            raise RuntimeError("Empty Groq response")
        logger.info("Groq OK model=%s chars=%s", _model(), len(text))
        return text


async def stream_chat(
    session_id: str,
    message: str,
    profile: dict,
    history: list,
    conditions: dict = None,
    risk: dict = None,
    forecast: dict = None,
    cool_spots: list = None,
):
    live = build_live_context(profile, conditions, risk, forecast, cool_spots)
    system = _system_prompt(live)
    user_msg = message
    if history:
        convo = "\n".join(f"{h['role']}: {h['content']}" for h in history[-6:])
        user_msg = (
            f"[Recent conversation — may be outdated vs live context]\n{convo}\n\n"
            f"[New message]\n{message}"
        )

    try:
        text = await _groq_complete(system, user_msg)
    except Exception as exc:
        logger.exception("AI chat failed: %s", exc)
        # Still surface live numbers even if the model is down
        snippet = ""
        if conditions:
            snippet = (
                f" Live now: {conditions.get('condition') or 'weather'} , "
                f"{conditions.get('air_temperature', {}).get('value')}°C "
                f"(feels like {conditions.get('feels_like', {}).get('value')}°C), "
                f"heat stress {conditions.get('heat_level')}."
            )
        text = (
            "I couldn't reach the AI model just now."
            + snippet
            + " Meanwhile: move to shade or air-con, drink water, and call 995 if anyone is confused, fainting, or has hot dry skin."
        )

    step = max(20, len(text) // 14)
    for i in range(0, len(text), step):
        yield text[i : i + step]


async def get_recommendations(profile: dict, conditions: dict, risk: dict, forecast: dict = None):
    live = build_live_context(profile, conditions, risk, forecast)
    system = _system_prompt(live)
    prompt = (
        f"My personalised heat-risk score is {risk.get('score')}/100 ({risk.get('band')}). "
        "Using ONLY the live context, give exactly 4 short, actionable recommendations for the next few hours. "
        "Each line must start with '- '. Mention current heat stress level or temperature in at least one tip. "
        "Do not say WBGT. "
        "No preamble."
    )
    try:
        resp = await _groq_complete(system, prompt)
        lines = [l.strip("-• ").strip() for l in resp.splitlines() if l.strip()]
        lines = [l for l in lines if len(l) > 3][:4]
        if lines:
            return lines
    except Exception as exc:
        logger.exception("AI recommendations failed: %s", exc)

    level = (conditions or {}).get("heat_level", "unknown")
    return [
        f"Current heat stress is {level} — hydrate now and take a shade break",
        "Prefer malls, libraries, or covered walkways for short trips",
        "Avoid heavy outdoor work in peak afternoon heat",
        "Check on elderly or vulnerable household members",
    ]


async def ai_status() -> dict:
    key = _api_key()
    if not key:
        return {"ok": False, "provider": "groq", "model": _model(), "detail": "GROQ_API_KEY missing"}
    try:
        text = await _groq_complete("Reply with exactly: HeatShield AI live", "ping")
        return {
            "ok": True,
            "provider": "groq",
            "model": _model(),
            "realtime": True,
            "sample": text[:120],
            "key_prefix": key[:7] + "…",
        }
    except Exception as exc:
        return {"ok": False, "provider": "groq", "model": _model(), "detail": str(exc)}
