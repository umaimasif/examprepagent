"""Groq LLM wrapper: chat completion + JSON-mode helper."""
import json
from typing import Optional

from groq import Groq

from app import config

_client: Optional[Groq] = None


def client() -> Groq:
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def chat(system: str, user: str, temperature: float = 0.3) -> str:
    """Plain text completion."""
    resp = client().chat.completions.create(
        model=config.GROQ_CHAT_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str, temperature: float = 0.2) -> dict:
    """Completion forced into a JSON object via Groq json_object response format."""
    resp = client().chat.completions.create(
        model=config.GROQ_CHAT_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system + "\nRespond ONLY with valid JSON."},
            {"role": "user", "content": user},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Best-effort salvage: grab the outermost braces.
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start : end + 1])
        raise
