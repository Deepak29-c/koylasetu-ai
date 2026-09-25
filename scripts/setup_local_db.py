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
    # RQ cannot run on Windows (no fork), so there the API processes uploads itself.
    "INGEST_INLINE": "true" if sys.platform == "win32" else "false",
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
    """Parse .env with python-dotenv, the same parser the backend's settings use (quotes,
    `export KEY=...`, inline comments)."""
    from dotenv import dotenv_values

    return {k: v for k, v in dotenv_values(path).items() if v is not None}


DOCKER_HOSTS = {"db", "redis", "ollama"}


def docker_keys(values: dict[str, str]) -> list[str]:
    """Settings still pointing at docker-compose service names (from a Docker-path .env)."""
    return [
        key
        for key in ("DATABASE_URL", "REDIS_URL", "LLM_BASE_URL")
        if urlparse(values.get(key, "")).hostname in DOCKER_HOSTS
    ]


def fix_env_text(text: str, keys: list[str]) -> str:
    """Point only the given keys at this machine; every other line is kept as it is."""
    lines = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if key in keys:
            line = f"{key}={LOCAL_VALUES[key]}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def ensure_env(fix: bool = False) -> dict[str, str]:
    if ENV_FILE.exists():
        say(".env", f"{ENV_FILE.name} already exists, left as it is")
    else:
        text = local_env_text(ENV_EXAMPLE.read_text(encoding="utf-8"), secrets.token_urlsafe(48))
        ENV_FILE.write_text(text, encoding="utf-8")
        say(".env", "created with localhost settings and a random JWT_SECRET")
        say(".env", "set SEED_DEMO_PASSWORD in .env before sharing the demo logins")
    values = read_env(ENV_FILE)
    if keys := docker_keys(values):
        if not fix:
            raise SystemExit(
                f".env still points at Docker hosts ({', '.join(keys)}). Change them to "
                "localhost, or run again with --fix-env to rewrite just those lines."
            )
        text = fix_env_text(ENV_FILE.read_text(encoding="utf-8"), keys)
        ENV_FILE.write_text(text, encoding="utf-8")
        say(".env", f"pointed {', '.join(keys)} at localhost")
        values = read_env(ENV_FILE)
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


def admin_url_ok(url: str) -> str:
    """The admin login as a plain libpq URL (a SQLAlchemy "+psycopg" URL is accepted too)."""
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    if not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit(
            "--admin-url must be a URL like postgresql://USER:PASSWORD@HOST:5432/postgres"
        )
    return url


def describe(url: str) -> str:
    """Where a URL points, without its password ("localhost:5432", or the socket directory)."""
    u = urlparse(url)
    if u.hostname:
        return f"{u.hostname}:{u.port or 5432}"
    options = dict(p.split("=", 1) for p in u.query.split("&") if "=" in p)
    return options.get("host", "the local socket")


def with_database(url: str, database: str) -> str:
    """Same server and options, other database. (urlparse().geturl() would turn the socket
    form "postgresql:///postgres?host=..." into "postgresql:/...", so edit the text.)"""
    base, sep, query = url.partition("?")
    scheme, rest = base.split("://", 1)
    authority = rest.split("/", 1)[0]
    return f"{scheme}://{authority}/{database}{sep}{query}"


def setup_postgres(
    admin_url: str, role: str, password: str, db: str, expect_major: int | None = None
) -> None:
    import psycopg
    from psycopg import sql

    where = describe(admin_url)
    try:
        admin = psycopg.connect(admin_url, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as e:
        raise SystemExit(
            f"Cannot connect to Postgres as admin at {where}: {e}\n"
            "Is Postgres running? Pass --admin-url postgresql://USER:PASSWORD@localhost:5432/"
            "postgres (a superuser) if the default does not work."
        ) from None
    with admin:
        version = "SELECT current_setting('server_version_num')::int / 10000"
        major = admin.execute(version).fetchone()[0]
        say("postgres", f"connected to Postgres {major} at {where}")
        if expect_major and major != expect_major:
            raise SystemExit(
                f"The Postgres answering at {where} is version {major}, not {expect_major}: "
                "another Postgres is using that port, so the new server could not take it. "
                f"Stop the other one, or point DATABASE_URL and PG_ADMIN_URL at the Postgres "
                f"{expect_major} port (on Debian / Ubuntu, pg_lsclusters shows it)."
            )
        found = admin.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s", [role])
        existing = found.fetchone()
        if existing and existing[0]:
            raise SystemExit(
                f"DATABASE_URL logs in as '{role}', a superuser. The app needs its own login "
                "(e.g. koyla); this script will not change a superuser's password."
            )
        exists = existing is not None
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

    app_url = with_database(admin_url, db)
    with psycopg.connect(app_url, autocommit=True, connect_timeout=5) as conn:
        available = conn.execute(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
        ).fetchone()
        if not available:
            hint = VECTOR_HELP.get(sys.platform, VECTOR_HELP["linux"])
            raise SystemExit(
                f"pgvector is not installed in the Postgres {major} at {where}.\n  {hint}\n"
                "  If you did install it, it was built for a different Postgres version."
            )
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
    parser.add_argument(
        "--fix-env", action="store_true", help="point Docker host names in .env at localhost"
    )
    parser.add_argument("--expect-major", type=int, help="stop if the server is another version")
    parser.add_argument("--skip-redis", action="store_true", help="don't check Redis")
    args = parser.parse_args()

    admin_url = admin_url_ok(args.admin_url)
    values = ensure_env(fix=args.fix_env)
    role, password, db = app_db(values.get("DATABASE_URL", LOCAL_VALUES["DATABASE_URL"]))
    setup_postgres(admin_url, role, password, db, args.expect_major)
    run_backend(["-m", "alembic", "upgrade", "head"], "migrate")
    if args.seed:
        run_backend(["-m", "app.scripts.seed"], "seed")
    redis_ok = args.skip_redis or check_redis(values.get("REDIS_URL", LOCAL_VALUES["REDIS_URL"]))
    print("\nDone." if redis_ok else "\nDone, except Redis (see above).")
    print("Start the API:    cd backend && uvicorn app.main:app --reload")
    print("Start the worker: cd backend && rq worker ingest topics reports  (not native Windows)")


if __name__ == "__main__":
    main()
