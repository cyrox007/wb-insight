#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$PROJECT_DIR/ops/update_systemd.sh" "$@"

if [[ "${1:-}" == "--preflight-only" ]]; then
  exit 0
fi

bash "$PROJECT_DIR/ops/publish_frontend.sh"
