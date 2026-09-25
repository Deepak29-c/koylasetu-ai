#!/usr/bin/env bash
# Save or bring back the whole demo state of the Docker setup: the database and the files
# volume (uploaded originals and page images), so a demo does not wait on OCR.
#
#   bash scripts/db_snapshot.sh create [name]      # default name: demo-YYYYMMDD-HHMM
#   bash scripts/db_snapshot.sh restore <name>     # asks first; --yes skips the question
#   bash scripts/db_snapshot.sh list
#
# Writes data/snapshots/<name>.dump (pg_dump custom format) and <name>.files.tar.gz.
# data/ is git-ignored, so snapshots never go in git. Windows PowerShell: db_snapshot.ps1.
#
# Settings (environment): DB_CONTAINER (koyla-db), API_CONTAINER (koyla-api),
# WORKER_CONTAINER (koyla-worker), FILES_VOLUME (read from the api container's /data/files
# mount), POSTGRES_USER / POSTGRES_DB (from .env, else koyla).
set -euo pipefail

# Git Bash on Windows would rewrite /tmp/... and /data/... arguments into Windows paths.
export MSYS_NO_PATHCONV=1

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SNAP_DIR="data/snapshots"

DB_CONTAINER="${DB_CONTAINER:-koyla-db}"
API_CONTAINER="${API_CONTAINER:-koyla-api}"
WORKER_CONTAINER="${WORKER_CONTAINER:-koyla-worker}"
HELPER="koyla-snapshot-helper"

env_value() {
  [[ -f .env ]] || return 0
  sed -n "s/^$1=\(.*\)$/\1/p" .env | tail -n 1 | tr -d '\r'
}
PGUSER="${POSTGRES_USER:-$(env_value POSTGRES_USER)}"
PGUSER="${PGUSER:-koyla}"
PGDB="${POSTGRES_DB:-$(env_value POSTGRES_DB)}"
PGDB="${PGDB:-koyla}"

say() { printf '\n==> %s\n' "$*"; }
die() {
  echo "Error: $*" >&2
  exit 1
}

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

running() { [[ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" == "true" ]]; }

files_volume() {
  if [[ -n "${FILES_VOLUME:-}" ]]; then
    echo "$FILES_VOLUME"
    return
  fi
  local c v
  for c in "$API_CONTAINER" "$WORKER_CONTAINER"; do
    v="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data/files"}}{{.Name}}{{end}}{{end}}' "$c" 2>/dev/null || true)"
    if [[ -n "$v" ]]; then
      echo "$v"
      return
    fi
  done
  # docker compose names volumes <project>_<volume>; the project is the folder name.
  echo "$(basename "$ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')_files"
}

# A short-lived container with the files volume mounted, for tar and docker cp.
start_helper() {
  local volume="$1" image
  image="$(docker inspect -f '{{.Config.Image}}' "$DB_CONTAINER")"
  docker rm -f "$HELPER" >/dev/null 2>&1 || true
  docker run -d --name "$HELPER" -v "$volume:/data/files" --entrypoint sleep "$image" 3600 >/dev/null
}
stop_helper() { docker rm -f "$HELPER" >/dev/null 2>&1 || true; }

check_name() {
  [[ "$1" =~ ^[A-Za-z0-9._-]+$ ]] || die "a snapshot name may only use letters, digits, '.', '_' and '-'"
}

need_db() {
  command -v docker >/dev/null || die "docker was not found"
  running "$DB_CONTAINER" || die "the database container '$DB_CONTAINER' is not running (docker compose up -d db)"
}

create() {
  local name="${1:-demo-$(date +%Y%m%d-%H%M)}" volume
  check_name "$name"
  need_db
  mkdir -p "$SNAP_DIR"
  local dump="$SNAP_DIR/$name.dump" files="$SNAP_DIR/$name.files.tar.gz"
  [[ -e "$dump" || -e "$files" ]] && die "snapshot '$name' already exists in $SNAP_DIR"

  say "Dumping database '$PGDB' from $DB_CONTAINER"
  # Dump inside the container and copy the file out: a binary dump must not pass through a
  # text pipe on Windows.
  docker exec "$DB_CONTAINER" pg_dump -U "$PGUSER" -d "$PGDB" -Fc -f /tmp/snapshot.dump
  docker cp "$DB_CONTAINER:/tmp/snapshot.dump" "$dump"
  docker exec "$DB_CONTAINER" rm -f /tmp/snapshot.dump

  volume="$(files_volume)"
  docker volume inspect "$volume" >/dev/null 2>&1 || die "files volume '$volume' not found (set FILES_VOLUME)"
  say "Packing files volume '$volume'"
  trap stop_helper EXIT
  start_helper "$volume"
  docker exec "$HELPER" tar czf /tmp/files.tar.gz -C /data/files .
  docker cp "$HELPER:/tmp/files.tar.gz" "$files"
  stop_helper
  trap - EXIT

  say "Saved snapshot '$name'"
  ls -lh "$dump" "$files"
}

restore() {
  local name="" yes=false volume
  for arg in "$@"; do
    case "$arg" in
      -y | --yes) yes=true ;;
      -*) die "unknown option: $arg" ;;
      *) name="$arg" ;;
    esac
  done
  [[ -n "$name" ]] || usage 1
  check_name "$name"
  local dump="$SNAP_DIR/$name.dump" files="$SNAP_DIR/$name.files.tar.gz"
  [[ -f "$dump" ]] || die "$dump not found (bash scripts/db_snapshot.sh list)"
  [[ -f "$files" ]] || echo "Note: $files not found; only the database will be restored."
  need_db
  volume="$(files_volume)"

  if ! $yes; then
    echo "This REPLACES database '$PGDB' in $DB_CONTAINER and every file in volume '$volume'"
    echo "with snapshot '$name'. Anything added since that snapshot is lost."
    read -r -p "Type yes to continue: " answer
    [[ "$answer" == "yes" ]] || die "cancelled, nothing changed"
  fi

  # The api and worker hold database connections and write files; pause them meanwhile.
  PAUSED=()
  for c in "$WORKER_CONTAINER" "$API_CONTAINER"; do
    if running "$c"; then
      docker stop "$c" >/dev/null
      PAUSED+=("$c")
    fi
  done
  trap 'stop_helper; resume' EXIT

  say "Recreating database '$PGDB'"
  docker exec "$DB_CONTAINER" psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 -q \
    -c "DROP DATABASE IF EXISTS \"$PGDB\" WITH (FORCE)" \
    -c "CREATE DATABASE \"$PGDB\" OWNER \"$PGUSER\""
  docker cp "$dump" "$DB_CONTAINER:/tmp/snapshot.dump"
  say "Restoring the dump"
  docker exec "$DB_CONTAINER" pg_restore -U "$PGUSER" -d "$PGDB" --no-owner --exit-on-error /tmp/snapshot.dump
  docker exec "$DB_CONTAINER" rm -f /tmp/snapshot.dump

  if [[ -f "$files" ]]; then
    say "Restoring files volume '$volume'"
    docker volume inspect "$volume" >/dev/null 2>&1 || docker volume create "$volume" >/dev/null
    start_helper "$volume"
    docker cp "$files" "$HELPER:/tmp/files.tar.gz"
    docker exec "$HELPER" sh -c 'find /data/files -mindepth 1 -delete && tar xzf /tmp/files.tar.gz -C /data/files'
    stop_helper
  fi

  trap - EXIT
  resume
  # The api runs "alembic upgrade head" when it starts, so an older snapshot is migrated then.
  say "Restored snapshot '$name'"
}

PAUSED=()
resume() {
  local c
  for c in ${PAUSED[@]+"${PAUSED[@]}"}; do docker start "$c" >/dev/null && echo "Started $c again"; done
  PAUSED=()
}

list() {
  if ! compgen -G "$SNAP_DIR/*.dump" >/dev/null; then
    echo "No snapshots in $SNAP_DIR yet (bash scripts/db_snapshot.sh create)."
    return
  fi
  ls -lh "$SNAP_DIR"/*.dump "$SNAP_DIR"/*.files.tar.gz 2>/dev/null
}

case "${1:-}" in
  create) create "${2:-}" ;;
  restore)
    shift
    restore "$@"
    ;;
  list) list ;;
  -h | --help | help) usage 0 ;;
  *) usage 1 ;;
esac
