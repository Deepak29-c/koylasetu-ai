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
[[ "${1:-}" == "--seed" ]] && SEED_ARG="--seed"

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
  git clone --quiet --depth 1 --branch "$PGVECTOR_VERSION" https://github.com/pgvector/pgvector.git "$tmp"
  make -C "$tmp" PG_CONFIG="$pg_config" >/dev/null
  $sudo_cmd make -C "$tmp" PG_CONFIG="$pg_config" install >/dev/null
  rm -rf "$tmp"
}

if [[ "$(uname)" == "Darwin" ]]; then
  command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
  say "Installing postgresql@$PG_MAJOR and redis with Homebrew"
  brew list "postgresql@$PG_MAJOR" >/dev/null 2>&1 || brew install "postgresql@$PG_MAJOR"
  brew list redis >/dev/null 2>&1 || brew install redis
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
  sudo apt-get install -y -qq "postgresql-$PG_MAJOR" "postgresql-$PG_MAJOR-pgvector" redis-server
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
cd "$ROOT/backend"
if [[ ! -x .venv/bin/python ]]; then
  PY="$(command -v python3.11 || command -v python3.12 || command -v python3)"
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q -r requirements.txt

say "Database, migrations, Redis check"
cd "$ROOT"
backend/.venv/bin/python scripts/setup_local_db.py --admin-url "$ADMIN_URL" $SEED_ARG
