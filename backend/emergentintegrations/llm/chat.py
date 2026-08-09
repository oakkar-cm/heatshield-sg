"""Minimal LlmChat-compatible stub using Groq when available, else offline replies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class UserMessage:
    text: str


@dataclass
class TextDelta:
    content: str


@dataclass
class StreamDone:
    pass


class LlmChat:
    def __init__(self, api_key: str | None, session_id: str, system_message: str):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
        self.session_id = session_id
        self.system_message = system_message
        self.provider = "groq"
        self.model = "llama-3.1-8b-instant"

    def with_model(self, provider: str, model: str) -> "LlmChat":
        # Prefer Groq locally; keep names for compatibility
        if os.environ.get("GROQ_API_KEY"):
            self.provider = "groq"
            self.model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        else:
            self.provider = provider
            self.model = model
        return self

    async def send_message(self, message: UserMessage) -> str:
        chunks: list[str] = []
        async for event in self.stream_message(message):
            if isinstance(event, TextDelta):
                chunks.append(event.content)
        return "".join(chunks) or _offline(message.text)

    async def stream_message(self, message: UserMessage) -> AsyncIterator[TextDelta | StreamDone]:
        text = await _complete(self.api_key, self.system_message, message.text, self.model)
        # yield in small chunks for streaming UX
        step = max(24, len(text) // 12)
        for i in range(0, len(text), step):
            yield TextDelta(content=text[i : i + step])
        yield StreamDone()


async def _complete(api_key: str | None, system: str, user: str, model: str) -> str:
    groq_key = os.environ.get("GROQ_API_KEY") or (api_key if api_key and api_key.startswith("gsk_") else None)
    if not groq_key:
        return _offline(user)
    try:
        import httpx

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 400,
                },
            )
            if resp.status_code != 200:
                return _offline(user)
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip() or _offline(user)
    except Exception:
        return _offline(user)


def _offline(message: str) -> str:
    lower = message.lower()
    if any(k in lower for k in ("dizzy", "faint", "confused", "995", "stroke")):
        return (
            "- Move to a cool place and loosen clothing\n"
            "- Sip water if awake and alert\n"
            "- Call SCDF 995 if symptoms worsen or confusion appears\n"
            "- Stay with the person until help arrives"
        )
    return (
        "- Stay hydrated and take shade breaks\n"
        "- Prefer malls, libraries, or covered walkways for short trips\n"
        "- Avoid heavy outdoor work in peak afternoon heat\n"
        "- Check on elderly or vulnerable household members"
    )
