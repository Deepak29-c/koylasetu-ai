"""scripts/check_llm.py: the parts that need no model server (issue #14). The full script was
run against a local Ollama; see the PR for its output."""

import importlib.util
from pathlib import Path

from app.core.config import Settings
from app.llm.client import _is_local

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_llm.py"
spec = importlib.util.spec_from_file_location("check_llm", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

TAGS = {
    "models": [
        {"name": "bge-m3:latest", "model": "bge-m3:latest"},
        {"name": "qwen2.5:3b-instruct", "model": "qwen2.5:3b-instruct"},
    ]
}


def test_model_names_are_compared_with_their_tag():
    assert check.normalise_model("bge-m3") == "bge-m3:latest"
    assert check.normalise_model("qwen2.5:3b-instruct") == "qwen2.5:3b-instruct"
    assert check.pulled_models(TAGS) == {"bge-m3:latest", "qwen2.5:3b-instruct"}


def test_no_models_missing_when_both_are_pulled():
    assert check.missing_models(["qwen2.5:3b-instruct", "bge-m3"], TAGS) == []


def test_missing_models_listed_in_order():
    assert check.missing_models(["qwen2.5:7b-instruct", "bge-m3"], TAGS) == ["qwen2.5:7b-instruct"]
    assert check.missing_models(["qwen2.5:3b-instruct", "bge-m3"], {"models": []}) == [
        "qwen2.5:3b-instruct",
        "bge-m3",
    ]
    assert check.missing_models(["bge-m3"], {}) == ["bge-m3"]


def test_pull_command_for_native_and_docker_servers():
    assert check.pull_command("bge-m3", "http://localhost:11434") == "ollama pull bge-m3"
    assert check.pull_command("bge-m3", "http://127.0.0.1:11434") == "ollama pull bge-m3"
    assert (
        check.pull_command("bge-m3", "http://ollama:11434")
        == "docker exec ollama ollama pull bge-m3"
    )


def test_guard_accepts_local_servers():
    for url in ("http://localhost:11434", "http://127.0.0.1:11434", "http://192.168.1.20:11434"):
        assert check.guard_problems(url, False, _is_local) == [], url


def test_guard_refuses_external_calls_flag_and_outside_hosts():
    problems = check.guard_problems("http://localhost:11434", True, _is_local)
    assert len(problems) == 1 and "ALLOW_EXTERNAL_CALLS=true" in problems[0]

    # Public IP address: no DNS lookup needed, so this stays offline.
    problems = check.guard_problems("http://8.8.8.8:11434", False, _is_local)
    assert len(problems) == 1 and "not this machine" in problems[0]

    assert "no host name" in check.guard_problems("not-a-url", False, _is_local)[0]


def test_default_settings_never_allow_outside_calls():
    s = Settings(_env_file=None)
    assert s.allow_external_calls is False
    assert check.guard_problems(s.llm_base_url, s.allow_external_calls, _is_local) == []
    example = (SCRIPT.parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "ALLOW_EXTERNAL_CALLS=false" in example
    assert "EMBED_MODEL=bge-m3" in example
    # A checkout without .env uses the same (documented, laptop-sized) model as .env.example.
    assert f"LLM_MODEL={s.llm_model}\n" in example
    assert f"EMBED_MODEL={s.embed_model}\n" in example
