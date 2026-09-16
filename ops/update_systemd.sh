#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-}"
PROJECT_DIR="${PROJECT_DIR:-/home/projects/wb}"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:9001/health/ready}"
TARGET_BRANCH="${TARGET_BRANCH:-main}"
VENV_DIR="$BACKEND_DIR/venv"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
STABILIZE_SECONDS="${STABILIZE_SECONDS:-6}"
RELEASE_KEEP="${RELEASE_KEEP:-3}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PREVIOUS_COMMIT=""
NEW_VENV=""
ACTIVATED=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { printf '%b\n' "${YELLOW}$*${NC}"; }
ok() { printf '%b\n' "${GREEN}$*${NC}"; }
fail() { printf '%b\n' "${RED}$*${NC}" >&2; exit 1; }

on_error() {
  local rc=$?
  printf '%b\n' "${RED}Update failed at line ${BASH_LINENO[0]} (exit ${rc}).${NC}" >&2
  if [[ -n "$PREVIOUS_COMMIT" ]]; then
    printf '%s\n' "Previous commit: $PREVIOUS_COMMIT" >&2
  fi
  printf '%s\n' "Current commit:  $(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true)" >&2
  if [[ "$ACTIVATED" == true ]]; then
    printf '%s\n' "The new runtime was already activated; inspect service logs before retrying." >&2
  else
    printf '%s\n' "Application services were not intentionally restarted." >&2
  fi
  exit "$rc"
}
trap on_error ERR

run_root() {
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

check_python() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "WB Insight requires Python 3.12. Install python3.12 + python3.12-venv before updating."
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Python 3.12 required, got {sys.version.split()[0]}")
print(f"python={sys.version.split()[0]}")
PY
}

check_node() {
  node - <<'NODE'
const [major, minor] = process.versions.node.split('.').map(Number)
const ok = (major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major > 22
if (!ok) {
  console.error(`Node ^20.19.0 or >=22.12.0 required, got ${process.versions.node}`)
  process.exit(1)
}
console.log(`node=${process.versions.node}`)
NODE
}

check_unit_exists() {
  systemctl cat "$1" >/dev/null 2>&1 || fail "Missing systemd unit: $1"
}

check_services_stable() {
  local service
  for service in wb-backend wb-celery wb-celery-beat; do
    if ! systemctl is-active --quiet "$service"; then
      run_root systemctl status "$service" --no-pager -l || true
      run_root journalctl -u "$service" -n 100 --no-pager || true
      fail "Service failed after update: $service"
    fi
  done
}

install_celery_dropins() {
  local worker_src="$PROJECT_DIR/ops/systemd/wb-celery.service.d/10-wb-insight.conf"
  local beat_src="$PROJECT_DIR/ops/systemd/wb-celery-beat.service.d/10-wb-insight.conf"
  [[ -f "$worker_src" ]] || fail "Missing canonical Celery worker drop-in: $worker_src"
  [[ -f "$beat_src" ]] || fail "Missing canonical Celery beat drop-in: $beat_src"

  run_root install -d -m 0755 "$SYSTEMD_DIR/wb-celery.service.d" "$SYSTEMD_DIR/wb-celery-beat.service.d"
  run_root install -m 0644 "$worker_src" "$SYSTEMD_DIR/wb-celery.service.d/10-wb-insight.conf"
  run_root install -m 0644 "$beat_src" "$SYSTEMD_DIR/wb-celery-beat.service.d/10-wb-insight.conf"
  run_root systemctl daemon-reload
}

cleanup_old_release_venvs() {
  [[ "$RELEASE_KEEP" =~ ^[0-9]+$ ]] || return 0
  (( RELEASE_KEEP > 0 )) || return 0

  mapfile -t releases < <(find "$BACKEND_DIR" -maxdepth 1 -mindepth 1 -type d -name 'venv.release.*' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}')
  local index
  for ((index=RELEASE_KEEP; index<${#releases[@]}; index++)); do
    rm -rf -- "${releases[$index]}"
  done
}

log "[preflight] Checking host, repository and systemd contract..."
require_cmd git
require_cmd node
require_cmd npm
require_cmd curl
require_cmd systemctl
require_cmd install
check_python
check_node
[[ -d "$PROJECT_DIR/.git" ]] || fail "Not a Git repository: $PROJECT_DIR"
[[ -f "$BACKEND_DIR/requirements.txt" ]] || fail "Missing backend/requirements.txt"
[[ -f "$FRONTEND_DIR/package-lock.json" ]] || fail "Missing frontend/package-lock.json"
for service in wb-backend wb-celery wb-celery-beat; do
  check_unit_exists "$service"
done

if [[ "$MODE" == "--preflight-only" ]]; then
  ok "Systemd updater preflight passed."
  exit 0
fi
[[ -z "$MODE" ]] || fail "Unknown argument: $MODE"

if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]]; then
  fail "Working tree is not clean. Commit/stash local changes before deployment."
fi

CURRENT_BRANCH="$(git -C "$PROJECT_DIR" branch --show-current)"
[[ "$CURRENT_BRANCH" == "$TARGET_BRANCH" ]] || fail "Expected branch '$TARGET_BRANCH', got '$CURRENT_BRANCH'."
PREVIOUS_COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
log "Current commit: $PREVIOUS_COMMIT"

log "[1/9] Fetching and fast-forwarding $TARGET_BRANCH..."
git -C "$PROJECT_DIR" fetch --prune origin "$TARGET_BRANCH"
git -C "$PROJECT_DIR" merge --ff-only "origin/$TARGET_BRANCH"
NEW_COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
log "Target commit:  $NEW_COMMIT"

log "[2/9] Building a fresh Python 3.12 release environment..."
NEW_VENV="$BACKEND_DIR/venv.release.$STAMP"
"$PYTHON_BIN" -m venv "$NEW_VENV"
"$NEW_VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$NEW_VENV/bin/python" -m pip install --requirement "$BACKEND_DIR/requirements.txt"
(
  cd "$BACKEND_DIR"
  PYTHONPATH=. "$NEW_VENV/bin/python" - <<'PY'
import fastapi
import numpy
import pandas
import models
from celery_app import celery_app

print(f"numpy={numpy.__version__} pandas={pandas.__version__} fastapi={fastapi.__version__}")
print(f"celery_app={celery_app.main}")
PY
  "$NEW_VENV/bin/celery" -A celery_app:celery_app report >/dev/null
  "$NEW_VENV/bin/alembic" --version >/dev/null
)

log "[3/9] Applying database migrations with the new environment..."
(
  cd "$BACKEND_DIR"
  "$NEW_VENV/bin/alembic" upgrade head
)

log "[4/9] Installing frontend dependencies from lockfile..."
(
  cd "$FRONTEND_DIR"
  npm ci
)

log "[5/9] Building frontend..."
(
  cd "$FRONTEND_DIR"
  npm run build
)

log "[6/9] Installing canonical Celery systemd overrides..."
install_celery_dropins
run_root systemctl enable wb-backend wb-celery wb-celery-beat >/dev/null

log "[7/9] Activating the release environment..."
PREVIOUS_VENV="$BACKEND_DIR/venv.previous.$STAMP"
if [[ -L "$VENV_DIR" ]]; then
  PREVIOUS_VENV_TARGET="$(readlink -f "$VENV_DIR")"
  [[ -n "$PREVIOUS_VENV_TARGET" ]] && ln -s "$PREVIOUS_VENV_TARGET" "$PREVIOUS_VENV"
  rm "$VENV_DIR"
elif [[ -d "$VENV_DIR" ]]; then
  mv "$VENV_DIR" "$PREVIOUS_VENV"
elif [[ -e "$VENV_DIR" ]]; then
  fail "Unexpected backend/venv object; expected directory or symlink"
fi
ln -s "$NEW_VENV" "$VENV_DIR"
NEW_VENV=""
ACTIVATED=true

"$VENV_DIR/bin/python" --version
"$VENV_DIR/bin/celery" -A celery_app:celery_app report >/dev/null
"$VENV_DIR/bin/alembic" --version >/dev/null

log "[8/9] Restarting and stabilizing application services..."
run_root systemctl restart wb-backend
run_root systemctl restart wb-celery
run_root systemctl restart wb-celery-beat
run_root systemctl reload nginx

sleep "$STABILIZE_SECONDS"
check_services_stable
sleep "$STABILIZE_SECONDS"
check_services_stable

# Verify the worker is not merely 'active' during a restart loop.
(
  cd "$BACKEND_DIR"
  "$VENV_DIR/bin/celery" -A celery_app:celery_app inspect ping --timeout=5 >/tmp/wb-insight-celery-ping.txt
)
grep -q 'pong' /tmp/wb-insight-celery-ping.txt || fail "Celery worker did not answer inspect ping"

log "[9/9] Checking backend readiness..."
ready=false
for _ in $(seq 1 30); do
  if curl -fsS "$HEALTH_URL" >/tmp/wb-insight-ready.json 2>/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  run_root journalctl -u wb-backend -n 100 --no-pager || true
  fail "Readiness check failed: $HEALTH_URL"
fi
cat /tmp/wb-insight-ready.json
printf '\n'

cleanup_old_release_venvs

ok "WB Insight update completed successfully."
ok "Previous commit: $PREVIOUS_COMMIT"
ok "Current commit:  $NEW_COMMIT"
ok "Backend Python:  $($VENV_DIR/bin/python --version 2>&1)"
ok "Product version:  $(tr -d '\r\n' < "$PROJECT_DIR/VERSION")"
