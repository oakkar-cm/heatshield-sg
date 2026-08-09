"""Quick multi-user DB check: create two users and read them back."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import store


def main():
    store.init()
    status = store.db_status()
    print("backend:", status)

    a = store.create_user({
        "email": f"multi_a_{store.new_id()[:8]}@test.local",
        "password_hash": "x",
        "name": "User A",
        "role": "user",
        "user_type": "citizen",
        "profile": {"age_group": "adult", "health_flags": [], "outdoor_exposure": "low"},
        "onboarded": True,
        "emergency_contacts": [],
        "saved_locations": [],
        "created_at": store.datetime_iso(),
    })
    b = store.create_user({
        "email": f"multi_b_{store.new_id()[:8]}@test.local",
        "password_hash": "x",
        "name": "User B",
        "role": "user",
        "user_type": "elderly",
        "profile": {"age_group": "elderly", "health_flags": ["Diabetes"], "outdoor_exposure": "low"},
        "onboarded": True,
        "emergency_contacts": [],
        "saved_locations": [],
        "created_at": store.datetime_iso(),
    })
    ra = store.get_user_by_id(a["id"])
    rb = store.get_user_by_id(b["id"])
    assert ra and rb and ra["id"] != rb["id"]
    assert ra["email"] != rb["email"]
    assert rb["profile"]["health_flags"] == ["Diabetes"]
    store.save_chat(f"{a['id']}:default", {"messages": [{"role": "user", "content": "hi-a"}]})
    store.save_chat(f"{b['id']}:default", {"messages": [{"role": "user", "content": "hi-b"}]})
    ca = store.get_chat(f"{a['id']}:default")
    cb = store.get_chat(f"{b['id']}:default")
    assert ca["messages"][0]["content"] == "hi-a"
    assert cb["messages"][0]["content"] == "hi-b"
    print("OK — two users isolated; chat sessions do not collide")
    print("multi_user_safe:", status["multi_user_safe"])
    if os.environ.get("VERCEL") and status["backend"] != "turso":
        print("WARN: On Vercel set TURSO_DATABASE_URL + TURSO_AUTH_TOKEN for real multi-user.")


if __name__ == "__main__":
    main()
