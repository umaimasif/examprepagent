"""Embedding provider. Groq has no embeddings endpoint, so we use Jina's
free embeddings API by default. Swap providers via EMBEDDINGS_PROVIDER."""
from typing import List

import httpx

from app import config

JINA_URL = "https://api.jina.ai/v1/embeddings"


def embed(texts: List[str], *, is_query: bool = False) -> List[List[float]]:
    """Return one embedding vector per input text."""
    if not texts:
        return []
    provider = config.EMBEDDINGS_PROVIDER.lower()
    if provider == "jina":
        return _embed_jina(texts, is_query=is_query)
    raise RuntimeError(f"Unknown EMBEDDINGS_PROVIDER: {provider}")


def embed_one(text: str, *, is_query: bool = False) -> List[float]:
    return embed([text], is_query=is_query)[0]


def _embed_jina(texts: List[str], *, is_query: bool) -> List[List[float]]:
    if not config.JINA_API_KEY:
        raise RuntimeError("JINA_API_KEY is not set")
    payload = {
        "model": config.JINA_MODEL,
        "task": "retrieval.query" if is_query else "retrieval.passage",
        "dimensions": config.EMBEDDING_DIM,
        "input": texts,
    }
    headers = {
        "Authorization": f"Bearer {config.JINA_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=60) as http:
        resp = http.post(JINA_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
    # Jina preserves input order.
    return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]
