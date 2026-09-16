#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/projects/wb}"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BUILD_DIR="$FRONTEND_DIR/dist"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-127.0.0.1:9001}"
FRONTEND_DEPLOY_DIR="${FRONTEND_DEPLOY_DIR:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEPLOY_DIR=""
PREVIOUS_DIR=""
SWAPPED=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { printf '%b\n' "${YELLOW}$*${NC}"; }
ok() { printf '%b\n' "${GREEN}$*${NC}"; }
fail() { printf '%b\n' "${RED}$*${NC}" >&2; exit 1; }

run_root() {
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

rollback_frontend() {
  local rc=$?
  if [[ "$SWAPPED" == true && -n "$DEPLOY_DIR" && -n "$PREVIOUS_DIR" && -e "$PREVIOUS_DIR" ]]; then
    printf '%b\n' "${RED}Frontend publish failed; restoring previous nginx document root...${NC}" >&2
    run_root rm -rf -- "$DEPLOY_DIR" || true
    run_root mv -- "$PREVIOUS_DIR" "$DEPLOY_DIR" || true
    run_root nginx -t >/dev/null 2>&1 || true
    run_root systemctl reload nginx >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap rollback_frontend ERR

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

detect_frontend_root() {
  if [[ -n "$FRONTEND_DEPLOY_DIR" ]]; then
    printf '%s\n' "$FRONTEND_DEPLOY_DIR"
    return 0
  fi

  local nginx_dump
  nginx_dump="$(mktemp)"
  if ! run_root nginx -T >"$nginx_dump" 2>&1; then
    rm -f "$nginx_dump"
    fail "Unable to read nginx configuration. Set FRONTEND_DEPLOY_DIR explicitly."
  fi

  local detected
  detected="$($PYTHON_BIN - "$BACKEND_UPSTREAM" "$nginx_dump" <<'PY'
import re
import sys

upstream = sys.argv[1]
path = sys.argv[2]
with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
    lines = fh.readlines()

server_blocks = []
in_server = False
depth = 0
buffer = []

for raw in lines:
    line = raw.split('#', 1)[0]
    if not in_server:
        if re.search(r'\bserver\s*\{', line):
            in_server = True
            buffer = [line]
            depth = line.count('{') - line.count('}')
            if depth <= 0:
                server_blocks.append('\n'.join(buffer))
                in_server = False
                buffer = []
        continue

    buffer.append(line)
    depth += line.count('{') - line.count('}')
    if depth <= 0:
        server_blocks.append('\n'.join(buffer))
        in_server = False
        buffer = []

proxy_re = re.compile(r'proxy_pass\s+https?://' + re.escape(upstream) + r'/?\s*;')
roots = []
for block in server_blocks:
    if not proxy_re.search(block):
        continue
    roots.extend(re.findall(r'(?m)^\s*root\s+([^;]+)\s*;', block))

unique = []
for value in roots:
    value = value.strip().strip('"').strip("'")
    if value not in unique:
        unique.append(value)

if len(unique) != 1:
    raise SystemExit(
        f"Expected exactly one nginx root for upstream {upstream}, found {unique or 'none'}"
    )

root = unique[0]
if '$' in root or not root.startswith('/'):
    raise SystemExit(f"Unsupported nginx root expression: {root}")
print(root)
PY
)" || {
    rm -f "$nginx_dump"
    fail "Could not determine WB Insight nginx document root. Set FRONTEND_DEPLOY_DIR explicitly."
  }
  rm -f "$nginx_dump"
  printf '%s\n' "$detected"
}

require_cmd nginx
require_cmd systemctl
require_cmd "$PYTHON_BIN"
require_cmd cmp
require_cmd realpath

[[ -f "$BUILD_DIR/index.html" ]] || fail "Frontend build missing: $BUILD_DIR/index.html"

DEPLOY_DIR="$(detect_frontend_root)"
[[ -n "$DEPLOY_DIR" ]] || fail "Frontend deploy directory is empty"

BUILD_REAL="$(realpath -m "$BUILD_DIR")"
DEPLOY_REAL="$(realpath -m "$DEPLOY_DIR")"

if [[ "$BUILD_REAL" == "$DEPLOY_REAL" ]]; then
  log "Nginx already serves frontend/dist directly: $DEPLOY_DIR"
  run_root nginx -t >/dev/null
  run_root systemctl reload nginx
  ok "Frontend publish verified."
  exit 0
fi

PARENT_DIR="$(dirname "$DEPLOY_DIR")"
BASE_NAME="$(basename "$DEPLOY_DIR")"
STAGING_DIR="$PARENT_DIR/.${BASE_NAME}.wb-next-$STAMP"
PREVIOUS_DIR="$PARENT_DIR/.${BASE_NAME}.wb-prev-$STAMP"

log "Publishing frontend build to nginx root: $DEPLOY_DIR"
run_root install -d -m 0755 "$PARENT_DIR"
run_root rm -rf -- "$STAGING_DIR"
run_root cp -a -- "$BUILD_DIR" "$STAGING_DIR"

if [[ -e "$DEPLOY_DIR" || -L "$DEPLOY_DIR" ]]; then
  run_root mv -- "$DEPLOY_DIR" "$PREVIOUS_DIR"
fi
run_root mv -- "$STAGING_DIR" "$DEPLOY_DIR"
SWAPPED=true

run_root nginx -t >/dev/null
run_root systemctl reload nginx
run_root cmp -s "$BUILD_DIR/index.html" "$DEPLOY_DIR/index.html"

SWAPPED=false
ok "Frontend published to $DEPLOY_DIR"
if [[ -e "$PREVIOUS_DIR" || -L "$PREVIOUS_DIR" ]]; then
  ok "Previous frontend kept at $PREVIOUS_DIR"
fi
