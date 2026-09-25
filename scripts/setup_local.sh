#!/usr/bin/env bash
# Local (non-Docker) Postgres 16 + pgvector + Redis for KoylaSetu, on macOS or Ubuntu / Debian.
# Safe to run again: anything already installed or running is left alone.
#
#   bash scripts/setup_local.sh            # install + start services, create DB, migrate
#   bash scripts/setup_local.sh --seed     # ... and create the demo users
#
# Windows: see docs/SETUP.md, "Run without Docker".
set -euo pipefail

PG_MAJOR=16
PGVECTOR_VERSION=v0.8.0
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEED_ARG=""
for arg in "$@"; do
  case "$arg" in
    --seed) SEED_ARG="--seed" ;;
    *) echo "Unknown option: $arg (only --seed; set PG_ADMIN_URL for another admin login)"; exit 1 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }

# pgvector is a C extension: if the package manager has no build for this Postgres, compile it.
build_pgvector() {
  local pg_config="$1" sudo_cmd="${2:-}"
  if [[ -f "$("$pg_config" --sharedir)/extension/vector.control" ]]; then
    echo "pgvector already installed"
    return
  fi
  say "Compiling pgvector $PGVECTOR_VERSION"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  git clone --quiet --depth 1 --branch "$PGVECTOR_VERSION" https://github.com/pgvector/pgvector.git "$tmp"
  make -C "$tmp" PG_CONFIG="$pg_config" >/dev/null
  $sudo_cmd make -C "$tmp" PG_CONFIG="$pg_config" install >/dev/null
}

python_ok() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; }

if [[ "$(uname)" == "Darwin" ]]; then
  command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
  say "Installing postgresql@$PG_MAJOR, redis and Python 3.11 with Homebrew"
  brew list "postgresql@$PG_MAJOR" >/dev/null 2>&1 || brew install "postgresql@$PG_MAJOR"
  brew list redis >/dev/null 2>&1 || brew install redis
  # macOS's own python3 is 3.9; the backend needs 3.11+.
  brew list python@3.11 >/dev/null 2>&1 || brew install python@3.11
  PY="$(brew --prefix python@3.11)/bin/python3.11"
  PG_BIN="$(brew --prefix "postgresql@$PG_MAJOR")/bin"
  build_pgvector "$PG_BIN/pg_config"
  say "Starting services"
  brew services start "postgresql@$PG_MAJOR" >/dev/null
  brew services start redis >/dev/null
  # Homebrew's Postgres makes the macOS user a superuser, with no password.
  ADMIN_URL="${PG_ADMIN_URL:-postgresql://$(whoami)@localhost:5432/postgres}"
elif command -v apt-get >/dev/null; then
  say "Installing postgresql-$PG_MAJOR, pgvector and redis with apt"
  sudo apt-get update -qq
  if ! apt-cache show "postgresql-$PG_MAJOR-pgvector" >/dev/null 2>&1; then
    # Not in this release's own repo (e.g. Debian 12): use the official PostgreSQL repo.
    sudo apt-get install -y -qq postgresql-common
    sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
  fi
  sudo apt-get install -y -qq "postgresql-$PG_MAJOR" "postgresql-$PG_MAJOR-pgvector" redis-server python3 python3-venv
  PY="$(command -v python3.12 || command -v python3.11 || command -v python3 || true)"
  say "Starting services"
  sudo service postgresql start >/dev/null || sudo systemctl start postgresql
  sudo service redis-server start >/dev/null || sudo systemctl start redis-server
  # Like Homebrew on macOS: your Linux user becomes a Postgres superuser, reached over the
  # local socket with peer auth. No password is created or changed.
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$(whoami)'" | grep -q 1; then
    sudo -u postgres createuser --superuser "$(whoami)"
  fi
  ADMIN_URL="${PG_ADMIN_URL:-postgresql:///postgres?host=/var/run/postgresql}"
else
  echo "Unsupported system. Install Postgres $PG_MAJOR + pgvector and Redis, then run:"
  echo "  backend/.venv/bin/python scripts/setup_local_db.py --admin-url <superuser URL>"
  exit 1
fi

say "Backend virtualenv"
if [[ -z "$PY" ]] || ! python_ok "$PY"; then
  echo "Python 3.11 or newer is needed (found: ${PY:-none}). Install it and run this again."
  exit 1
fi
cd "$ROOT/backend"
# Rebuild a venv that is too old or half-made (e.g. an earlier run failed before pip existed).
if [[ ! -x .venv/bin/pip ]] || ! python_ok .venv/bin/python; then
  rm -rf .venv
  "$PY" -m venv .venv || { rm -rf .venv; exit 1; }
fi
.venv/bin/python -m pip install -q -r requirements.txt

say "Database, migrations, Redis check"
cd "$ROOT"
backend/.venv/bin/python scripts/setup_local_db.py --admin-url "$ADMIN_URL" --expect-major "$PG_MAJOR" $SEED_ARG
