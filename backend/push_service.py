"""Web Push (VAPID) helpers + background heat-alert monitor."""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pywebpush import webpush, WebPushException

import store

logger = logging.getLogger("heatshield.push")

BAND_RANK = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}


def in_quiet_hours(qh: dict, hour: int) -> bool:
    if not qh or not qh.get("enabled"):
        return False
    start, end = qh.get("start", 22), qh.get("end", 7)
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _vapid_private():
    return os.environ.get("VAPID_PRIVATE_KEY")


def _claims_email():
    return os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:alerts@heatshield.sg")


def send_push(subscription: dict, payload: dict) -> bool:
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=_vapid_private(),
            vapid_claims={"sub": _claims_email()},
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            return False
        logger.warning("web-push failed: %s", e)
        return True
    except Exception as e:
        logger.warning("web-push error: %s", e)
        return True


async def push_to_user(user: dict, payload: dict):
    uid = user.get("id") or user.get("_id")
    full = store.get_user_by_id(str(uid)) if uid else None
    subs = (full or user).get("push_subscriptions", []) or []
    if not subs:
        return 0
    sent = 0
    stale = []
    loop = asyncio.get_event_loop()
    for sub in subs:
        ok = await loop.run_in_executor(None, send_push, sub, payload)
        if ok:
            sent += 1
        else:
            stale.append(sub.get("endpoint"))
    if stale and uid:
        store.pull_push_endpoints(str(uid), [e for e in stale if e])
    return sent


async def monitor_loop(get_conditions, compute_risk, interval=600):
    await asyncio.sleep(20)
    while True:
        try:
            sg_hour = datetime.now(timezone(timedelta(hours=8))).hour
            for user in store.list_users_with_push():
                try:
                    if in_quiet_hours(user.get("quiet_hours"), sg_hour):
                        continue
                    locs = user.get("saved_locations", []) or []
                    home = next((l for l in locs if l.get("label") == "Home"), None) or (locs[0] if locs else None)
                    if not home:
                        continue
                    cond = await get_conditions(home["lat"], home["lng"])
                    risk = compute_risk(cond, user.get("profile", {}))
                    threshold = user.get("notify_threshold", "High")
                    if BAND_RANK.get(risk["band"], 0) < BAND_RANK.get(threshold, 2):
                        if user.get("last_notified_band") and BAND_RANK.get(user["last_notified_band"], 0) >= BAND_RANK.get(threshold, 2):
                            store.update_user(user["id"], set_fields={"last_notified_band": risk["band"]})
                        continue
                    if user.get("last_notified_band") == risk["band"]:
                        continue
                    payload = {
                        "title": f"{risk['band']} heat risk near {home.get('label', 'you')}",
                        "body": cond["heat_meta"]["message"] + f" (risk {risk['score']}/100)",
                        "url": "/",
                        "tag": "heat-alert",
                    }
                    await push_to_user(user, payload)
                    store.update_user(user["id"], set_fields={"last_notified_band": risk["band"]})
                except Exception as e:
                    logger.warning("monitor user error: %s", e)
        except Exception as e:
            logger.warning("monitor loop error: %s", e)
        await asyncio.sleep(interval)
