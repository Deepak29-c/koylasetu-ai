"""Client for the local model server (Ollama in dev, vLLM later). Chat + embeddings.

On-premise rule: the model server must be on this machine or the local network. Any other
host is refused unless ALLOW_EXTERNAL_CALLS=true, so government text never goes to a cloud API
by accident.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

EMBED_DIM = 1024  # BGE-M3


class LlmUnavailable(Exception):
    """The model server could not be reached or returned an error."""


class ExternalCallBlocked(LlmUnavailable):
    pass


def _is_local(host: str) -> bool:
    if host in {"localhost", "ollama", "vllm", "host.docker.internal"}:
        return True
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    return all(
        ipaddress.ip_address(a).is_private or ipaddress.ip_address(a).is_loopback for a in addrs
    )


def base_url() -> str:
    s = get_settings()
    host = urlparse(s.llm_base_url).hostname or ""
    if not s.allow_external_calls and not _is_local(host):
        raise ExternalCallBlocked(
            f"LLM_BASE_URL host '{host}' is not local and ALLOW_EXTERNAL_CALLS=false"
        )
    return s.llm_base_url.rstrip("/")


def _post(path: str, payload: dict, timeout: float) -> dict:
    url = f"{base_url()}{path}"
    try:
        res = httpx.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as e:
        raise LlmUnavailable(f"model server not reachable at {url}: {e}") from e
    if res.status_code != 200:
        raise LlmUnavailable(f"model server error {res.status_code}: {res.text[:300]}")
    return res.json()


def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    timeout: float = 300,
    json_schema: dict | None = None,
) -> str:
    """One-shot chat completion. Low temperature by default (guide 17.2). With `json_schema`
    the model server constrains the reply to JSON of that shape (validate it anyway)."""
    payload = {
        "model": get_settings().llm_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": get_settings().llm_num_ctx},
    }
    if json_schema is not None:
        payload["format"] = json_schema
    data = _post("/api/chat", payload, timeout)
    return data.get("message", {}).get("content", "").strip()


def embed_texts(texts: list[str], timeout: float = 300) -> list[list[float]]:
    model = get_settings().embed_model
    data = _post("/api/embed", {"model": model, "input": texts}, timeout)
    vectors = data.get("embeddings", [])
    if len(vectors) != len(texts) or any(len(v) != EMBED_DIM for v in vectors):
        raise LlmUnavailable(f"expected {len(texts)} vectors of size {EMBED_DIM} from {model}")
    return vectors
