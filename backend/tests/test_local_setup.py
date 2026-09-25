"""scripts/setup_local_db.py: the parts that need no database (issue #13). The full script was
run twice against a local Postgres 16 + pgvector: second run changes nothing."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "setup_local_db.py"
spec = importlib.util.spec_from_file_location("setup_local_db", SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_env_from_example_points_at_localhost_with_a_secret():
    example = (SCRIPT.parents[1] / ".env.example").read_text(encoding="utf-8")
    env = setup.local_env_text(example, "s3cret-value")
    values = {
        k: v for k, v in (ln.split("=", 1) for ln in env.splitlines() if "=" in ln and ln[0] != "#")
    }
    assert values["DATABASE_URL"] == "postgresql+psycopg://koyla:koyla@localhost:5432/koyla"
    assert values["REDIS_URL"] == "redis://localhost:6379/0"
    assert values["LLM_BASE_URL"] == "http://localhost:11434"
    assert values["JWT_SECRET"] == "s3cret-value"
    assert "@db:" not in env and "redis://redis" not in env
    assert "ALLOW_EXTERNAL_CALLS=false" in env  # everything else kept as in the example


def test_existing_env_is_never_overwritten(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql+psycopg://me:pw@localhost:5433/mydb\n")
    monkeypatch.setattr(setup, "ENV_FILE", env)
    values = setup.ensure_env()
    assert values["DATABASE_URL"].endswith("@localhost:5433/mydb")
    assert env.read_text() == "DATABASE_URL=postgresql+psycopg://me:pw@localhost:5433/mydb\n"


def test_missing_env_is_created(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "ENV_FILE", tmp_path / ".env")
    values = setup.ensure_env()
    assert values["REDIS_URL"] == "redis://localhost:6379/0"
    assert len(values["JWT_SECRET"]) >= 32


def test_read_env_ignores_comments():
    path = SCRIPT.parents[1] / ".env.example"
    values = setup.read_env(path)
    assert values["OCR_ENGINE"] == "paddle"  # "paddle            # paddle | tesseract"


def test_app_db_from_database_url():
    url = "postgresql+psycopg://koyla:p%40ss@localhost:5432/koyla"
    assert setup.app_db(url) == ("koyla", "p@ss", "koyla")


def test_app_db_rejects_names_that_need_quoting():
    with pytest.raises(SystemExit):
        setup.app_db("postgresql+psycopg://Koyla-User:x@localhost/koyla")


@pytest.mark.parametrize(
    "admin, expected",
    [
        ("postgresql://postgres@localhost:5432/postgres", "postgresql://postgres@localhost:5432/koyla"),
        ("postgresql:///postgres?host=/var/run/postgresql", "postgresql:///koyla?host=/var/run/postgresql"),
    ],
)  # fmt: skip
def test_with_database_keeps_host_and_options(admin, expected):
    assert setup.with_database(admin, "koyla") == expected
