#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_BRANCH="${TARGET_BRANCH:-main}"

fail() {
  printf 'Update bootstrap failed: %s\n' "$*" >&2
  exit 1
}

bootstrap_latest_updater() {
  command -v git >/dev/null 2>&1 || fail "git is required"
  [[ -d "$PROJECT_DIR/.git" ]] || fail "Not a Git repository: $PROJECT_DIR"

  if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]]; then
    fail "Working tree is not clean. Commit/stash local changes before deployment."
  fi

  local current_branch before after
  current_branch="$(git -C "$PROJECT_DIR" branch --show-current)"
  [[ "$current_branch" == "$TARGET_BRANCH" ]] || fail "Expected branch '$TARGET_BRANCH', got '$current_branch'."

  before="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
  git -C "$PROJECT_DIR" fetch --prune origin "$TARGET_BRANCH"
  git -C "$PROJECT_DIR" merge --ff-only "origin/$TARGET_BRANCH"
  after="$(git -C "$PROJECT_DIR" rev-parse HEAD)"

  if [[ "$before" != "$after" && "${WB_UPDATE_REEXEC:-0}" != "1" ]]; then
    printf 'Updater refreshed %s -> %s; restarting with the new version...\n' "$before" "$after"
    exec env WB_UPDATE_REEXEC=1 TARGET_BRANCH="$TARGET_BRANCH" "$PROJECT_DIR/update.sh" "$@"
  fi
}

if [[ "${1:-}" != "--preflight-only" ]]; then
  bootstrap_latest_updater "$@"
fi

"$PROJECT_DIR/ops/update_systemd.sh" "$@"

if [[ "${1:-}" == "--preflight-only" ]]; then
  exit 0
fi

bash "$PROJECT_DIR/ops/publish_frontend.sh"
