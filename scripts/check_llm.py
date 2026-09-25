"""Check that the local AI model server (Ollama) is ready for KoylaSetu (issue #14).

Run it with the backend venv from the backend/ folder, so it reads the same .env as the app:

    cd backend
    .venv/Scripts/python ../scripts/check_llm.py      # Linux/macOS: .venv/bin/python

It checks, in order, and stops at the first step that fails:
  1. LLM_BASE_URL is local (the same guard as app/llm/client.py) and ALLOW_EXTERNAL_CALLS=false
  2. the model server answers
  3. both models are pulled (LLM_MODEL writes answers, EMBED_MODEL makes search embeddings);
     any missing one is listed with the exact `ollama pull` command
  4. a real embedding comes back with 1024 numbers (BGE-M3)
  5. a tiny chat prompt gets an answer
and prints how long each step took. Exit code 0 = ready, 1 = not ready.

It only talks to the model server in LLM_BASE_URL, through the app's own client.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlparse

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

# The same model-name comparison as the admin System status screen.
from app.llm.client import missing_models, normalise_model, pulled_models  # noqa: E402, F401

# Hosts that are docker-compose service names: pull through the container, not the host.
DOCKER_HOSTS = {"ollama", "host.docker.internal"}

CHAT_SYSTEM = "You are a test. Reply with one short sentence."
CHAT_USER = "Say hello and name the capital of India."
EMBED_TEXT = "Coal production of NCL in FY 2023-24 was 136.15 MT."


def pull_command(model: str, base_url: str) -> str:
    """The exact command that downloads a model into the server at `base_url`."""
    host = urlparse(base_url).hostname or ""
    if host in DOCKER_HOSTS:
        return f"docker exec ollama ollama pull {model}"
    return f"ollama pull {model}"


def guard_problems(llm_base_url: str, allow_external_calls: bool, is_local) -> list[str]:
    """Reasons the settings could send our text to a machine outside this network.
    `is_local` is the client's own host check (app.llm.client._is_local)."""
    problems = []
    if allow_external_calls:
        problems.append(
            "ALLOW_EXTERNAL_CALLS=true: set it to false, so the app can never call an "
            "outside AI service"
        )
    host = urlparse(llm_base_url).hostname or ""
    if not host:
        problems.append(f"LLM_BASE_URL '{llm_base_url}' has no host name")
    elif not is_local(host):
        problems.append(
            f"LLM_BASE_URL host '{host}' is not this machine or the local network "
            "(use http://localhost:11434)"
        )
    return problems


def _step(label: str, ok: bool, detail: str, seconds: float | None = None) -> None:
    timing = f" ({seconds:.1f} s)" if seconds is not None else ""
    print(f"[{'OK' if ok else 'FAIL'}] {label}{timing}: {detail}")


def main() -> int:
    import httpx

    from app.core.config import get_settings
    from app.llm import client

    s = get_settings()
    print(
        f"LLM_BASE_URL={s.llm_base_url}  LLM_MODEL={s.llm_model}  EMBED_MODEL={s.embed_model}  "
        f"LLM_NUM_CTX={s.llm_num_ctx}  ALLOW_EXTERNAL_CALLS={str(s.allow_external_calls).lower()}"
    )

    problems = guard_problems(s.llm_base_url, s.allow_external_calls, client._is_local)
    _step("1. local-only", not problems, "; ".join(problems) or "model server is local")
    if problems:
        return 1
    base = client.base_url()

    t = time.perf_counter()
    try:
        version = httpx.get(f"{base}/api/version", timeout=10).json().get("version", "?")
        tags = httpx.get(f"{base}/api/tags", timeout=10).json()
    except (httpx.HTTPError, ValueError) as e:
        hint = "start it: open the Ollama app, or run `ollama serve`"
        if urlparse(base).hostname in DOCKER_HOSTS:
            hint = (
                "'ollama' is the Docker service name: run `docker compose up -d ollama`, or "
                "set LLM_BASE_URL=http://localhost:11434 in .env when Ollama runs natively"
            )
        _step("2. server", False, f"no answer from {base} ({e.__class__.__name__}); {hint}")
        return 1
    _step("2. server", True, f"Ollama {version} at {base}", time.perf_counter() - t)

    missing = missing_models([s.llm_model, s.embed_model], tags)
    if missing:
        cmds = "; ".join(pull_command(m, base) for m in missing)
        _step("3. models", False, f"missing {', '.join(missing)}; run: {cmds}")
        return 1
    _step("3. models", True, f"{s.llm_model} and {s.embed_model} are pulled")

    t = time.perf_counter()
    try:
        vectors = client.embed_texts([EMBED_TEXT])
    except client.LlmUnavailable as e:
        _step("4. embedding", False, str(e))
        return 1
    _step("4. embedding", True, f"{len(vectors[0])} dimensions", time.perf_counter() - t)

    t = time.perf_counter()
    try:
        answer = client.chat(CHAT_SYSTEM, CHAT_USER)
    except client.LlmUnavailable as e:
        _step("5. chat", False, str(e))
        return 1
    elapsed = time.perf_counter() - t
    if not answer:
        _step("5. chat", False, "the model returned an empty answer", elapsed)
        return 1
    _step("5. chat", True, repr(answer[:200]), elapsed)
    print("Ready: questions can be answered by the local model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
