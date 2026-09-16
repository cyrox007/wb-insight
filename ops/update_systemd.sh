#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/projects/wb}"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:9000/health/ready}"
TARGET_BRANCH="${TARGET_BRANCH:-main}"
VENV_DIR="$BACKEND_DIR/venv"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PREVIOUS_COMMIT=""
NEW_VENV=""

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
  printf '%s\n' "Services were not intentionally restarted unless the script reached the restart step." >&2
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

log "[preflight] Checking host and repository..."
require_cmd git
require_cmd node
require_cmd npm
require_cmd curl
require_cmd systemctl
check_python
check_node
[[ -d "$PROJECT_DIR/.git" ]] || fail "Not a Git repository: $PROJECT_DIR"
[[ -f "$BACKEND_DIR/requirements.txt" ]] || fail "Missing backend/requirements.txt"
[[ -f "$FRONTEND_DIR/package-lock.json" ]] || fail "Missing frontend/package-lock.json"

if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]]; then
  fail "Working tree is not clean. Commit/stash local changes before deployment."
fi

CURRENT_BRANCH="$(git -C "$PROJECT_DIR" branch --show-current)"
[[ "$CURRENT_BRANCH" == "$TARGET_BRANCH" ]] || fail "Expected branch '$TARGET_BRANCH', got '$CURRENT_BRANCH'."
PREVIOUS_COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
log "Current commit: $PREVIOUS_COMMIT"

log "[1/8] Fetching and fast-forwarding $TARGET_BRANCH..."
git -C "$PROJECT_DIR" fetch --prune origin "$TARGET_BRANCH"
git -C "$PROJECT_DIR" merge --ff-only "origin/$TARGET_BRANCH"
NEW_COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
log "Target commit:  $NEW_COMMIT"

log "[2/8] Building a fresh Python 3.12 virtual environment..."
NEW_VENV="$BACKEND_DIR/venv.next.$STAMP"
"$PYTHON_BIN" -m venv "$NEW_VENV"
"$NEW_VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$NEW_VENV/bin/python" -m pip install --requirement "$BACKEND_DIR/requirements.txt"
"$NEW_VENV/bin/python" - <<'PY'
import numpy, pandas, fastapi
print(f"numpy={numpy.__version__} pandas={pandas.__version__} fastapi={fastapi.__version__}")
PY

log "[3/8] Applying database migrations with the new environment..."
(
  cd "$BACKEND_DIR"
  "$NEW_VENV/bin/alembic" upgrade head
)

log "[4/8] Installing frontend dependencies from lockfile..."
(
  cd "$FRONTEND_DIR"
  npm ci
)

log "[5/8] Building frontend..."
(
  cd "$FRONTEND_DIR"
  npm run build
)

log "[6/8] Activating the new virtual environment..."
if [[ -d "$VENV_DIR" ]]; then
  mv "$VENV_DIR" "$BACKEND_DIR/venv.previous.$STAMP"
fi
mv "$NEW_VENV" "$VENV_DIR"
NEW_VENV=""

log "[7/8] Restarting application services..."
run_root systemctl restart wb-backend
run_root systemctl restart wb-celery
run_root systemctl restart wb-celery-beat
run_root systemctl reload nginx

for service in wb-backend wb-celery wb-celery-beat; do
  if ! systemctl is-active --quiet "$service"; then
    run_root systemctl status "$service" --no-pager -l || true
    run_root journalctl -u "$service" -n 100 --no-pager || true
    fail "Service failed after update: $service"
  fi
done

log "[8/8] Checking readiness..."
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

ok "WB Insight update completed successfully."
ok "Previous commit: $PREVIOUS_COMMIT"
ok "Current commit:  $NEW_COMMIT"
ok "Backend Python:  $($VENV_DIR/bin/python --version 2>&1)"
ok "Product version:  $(tr -d '\r\n' < "$PROJECT_DIR/VERSION")"
