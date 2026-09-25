"""Prepare a local (non-Docker) database and queue for KoylaSetu. Safe to run again.

    backend/.venv/bin/python scripts/setup_local_db.py            # macOS / Linux
    backend\\.venv\\Scripts\\python scripts\\setup_local_db.py      # Windows
    ... --admin-url postgresql://postgres:secret@localhost:5432/postgres --seed

Steps, each skipped when already done:
1. Create .env from .env.example with localhost hosts and a random JWT secret (never
   overwrites an existing .env).
2. Create the app's database role and database from DATABASE_URL (password kept in sync).
3. Enable the pgvector extension in that database (needs a superuser, and pgvector installed).
4. Apply the migrations (alembic upgrade head) and, with --seed, create the demo users.
5. Check that Redis answers.

Postgres and Redis themselves must already be installed and running: scripts/setup_local.sh
does that on macOS and Ubuntu / Debian; docs/SETUP.md covers Windows. Needs the backend's
Python packages (psycopg, redis), so run it with the backend virtualenv.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
DEFAULT_ADMIN_URL = "postgresql://postgres@localhost:5432/postgres"

# Docker service names in .env.example -> the same service on this machine.
LOCAL_VALUES = {
    "DATABASE_URL": "postgresql+psycopg://koyla:koyla@localhost:5432/koyla",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_BASE_URL": "http://localhost:11434",
    "STORAGE_DIR": "./storage",
    "NEXT_PUBLIC_API_URL": "http://localhost:8000",
}

VECTOR_HELP = {
    "darwin": "Run scripts/setup_local.sh (it compiles pgvector for Homebrew's postgresql@16).",
    "linux": "sudo apt install postgresql-16-pgvector  (or run scripts/setup_local.sh)",
    "win32": "Build pgvector with Visual Studio's nmake: see docs/SETUP.md, 'Run without Docker'.",
}


def say(step: str, message: str) -> None:
    print(f"[{step}] {message}", flush=True)


# --- .env ---------------------------------------------------------------------------------


def local_env_text(example: str, jwt_secret: str) -> str:
    """.env.example rewritten for a machine without Docker."""
    lines = []
    for line in example.splitlines():
        key = line.split("=", 1)[0].strip()
        if key in LOCAL_VALUES and "=" in line:
            line = f"{key}={LOCAL_VALUES[key]}"
        elif key == "JWT_SECRET":
            line = f"JWT_SECRET={jwt_secret}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.split(" #", 1)[0].strip()
    return values


def ensure_env() -> dict[str, str]:
    if ENV_FILE.exists():
        say(".env", f"{ENV_FILE.name} already exists, left as it is")
    else:
        text = local_env_text(ENV_EXAMPLE.read_text(encoding="utf-8"), secrets.token_urlsafe(48))
        ENV_FILE.write_text(text, encoding="utf-8")
        say(".env", "created with localhost settings and a random JWT_SECRET")
        say(".env", "set SEED_DEMO_PASSWORD in .env before sharing the demo logins")
    values = read_env(ENV_FILE)
    for key in ("DATABASE_URL", "REDIS_URL"):
        host = urlparse(values.get(key, "")).hostname
        if host in {"db", "redis"}:
            say(".env", f"warning: {key} points at Docker host '{host}'; use localhost")
    return values


# --- Postgres -------------------------------------------------------------------------------


def app_db(database_url: str) -> tuple[str, str, str]:
    """(role, password, database) from a SQLAlchemy DATABASE_URL."""
    u = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    role, password, db = unquote(u.username or ""), unquote(u.password or ""), u.path.lstrip("/")
    for name in (role, db):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            raise SystemExit(f"DATABASE_URL: use a simple lowercase name, not {name!r}")
    return role, password, db


def with_database(url: str, database: str) -> str:
    """Same server and options, other database. (urlparse().geturl() would turn the socket
    form "postgresql:///postgres?host=..." into "postgresql:/...", so edit the text.)"""
    base, sep, query = url.partition("?")
    scheme, rest = base.split("://", 1)
    authority = rest.split("/", 1)[0]
    return f"{scheme}://{authority}/{database}{sep}{query}"


def setup_postgres(admin_url: str, role: str, password: str, db: str) -> None:
    import psycopg
    from psycopg import sql

    try:
        admin = psycopg.connect(admin_url, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as e:
        raise SystemExit(
            f"Cannot connect to Postgres as admin ({urlparse(admin_url).hostname}): {e}\n"
            "Is Postgres running? Pass --admin-url postgresql://USER:PASSWORD@localhost:5432/"
            "postgres (a superuser) if the default does not work."
        ) from None
    with admin:
        exists = admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role]).fetchone()
        verb = "ALTER" if exists else "CREATE"
        admin.execute(
            sql.SQL(verb + " ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        say("postgres", f"role {role} {'updated' if exists else 'created'}")

        if admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", [db]).fetchone():
            say("postgres", f"database {db} already exists")
        else:
            admin.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(db), sql.Identifier(role)
                )
            )
            say("postgres", f"database {db} created")

    with psycopg.connect(with_database(admin_url, db), autocommit=True) as conn:
        available = conn.execute(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
        ).fetchone()
        if not available:
            hint = VECTOR_HELP.get(sys.platform, VECTOR_HELP["linux"])
            raise SystemExit(f"pgvector is not installed in this Postgres.\n  {hint}")
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()[0]
        conn.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(role)))
        say("postgres", f"pgvector {version} enabled in {db}")


def run_backend(args: list[str], step: str) -> None:
    say(step, " ".join(args))
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    result = subprocess.run([sys.executable, *args], cwd=BACKEND, env=env)
    if result.returncode != 0:
        raise SystemExit(f"{step} failed (exit code {result.returncode})")


# --- Redis --------------------------------------------------------------------------------


def check_redis(redis_url: str) -> bool:
    import redis

    try:
        redis.Redis.from_url(redis_url, socket_connect_timeout=2).ping()
    except redis.RedisError as e:
        say("redis", f"not reachable at {redis_url}: {e}")
        say("redis", "uploads will stay 'Uploaded' until Redis runs (then press Retry)")
        return False
    say("redis", f"ok at {redis_url}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--admin-url",
        default=os.environ.get("PG_ADMIN_URL", DEFAULT_ADMIN_URL),
        help="a Postgres superuser connection (default: $PG_ADMIN_URL or %(default)s)",
    )
    parser.add_argument("--seed", action="store_true", help="also create the demo users")
    parser.add_argument("--skip-redis", action="store_true", help="don't check Redis")
    args = parser.parse_args()

    values = ensure_env()
    role, password, db = app_db(values.get("DATABASE_URL", LOCAL_VALUES["DATABASE_URL"]))
    setup_postgres(args.admin_url, role, password, db)
    run_backend(["-m", "alembic", "upgrade", "head"], "migrate")
    if args.seed:
        run_backend(["-m", "app.scripts.seed"], "seed")
    redis_ok = args.skip_redis or check_redis(values.get("REDIS_URL", LOCAL_VALUES["REDIS_URL"]))
    print("\nDone." if redis_ok else "\nDone, except Redis (see above).")
    print("Start the API:    cd backend && uvicorn app.main:app --reload")
    print("Start the worker: cd backend && rq worker ingest topics reports")


if __name__ == "__main__":
    main()
