#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_BRANCH="${TARGET_BRANCH:-main}"
UPDATE_LOCK_FILE="${UPDATE_LOCK_FILE:-/tmp/wb-insight-update.lock}"
BOOTSTRAP_FILE=""

fail() {
  printf 'Ошибка запуска обновления: %s\n' "$*" >&2
  return 1
}

cleanup() {
  if [[ -n "$BOOTSTRAP_FILE" && -f "$BOOTSTRAP_FILE" ]]; then
    rm -f -- "$BOOTSTRAP_FILE" || true
  fi
}
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "не найдена обязательная команда: $1"
}

acquire_update_lock() {
  require_cmd flock
  exec 9>"$UPDATE_LOCK_FILE"
  if ! flock -n 9; then
    fail "другое обновление WB Insight уже выполняется: $UPDATE_LOCK_FILE"
  fi
  export WB_UPDATE_LOCK_HELD=1
}

resolve_target() {
  require_cmd git
  require_cmd mktemp
  [[ -d "$PROJECT_DIR/.git" ]] || fail "каталог не является Git-репозиторием: $PROJECT_DIR"

  if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]]; then
    fail "рабочее дерево содержит изменения. Сначала сохраните или отмените их."
  fi

  local current_branch previous_commit target_commit
  current_branch="$(git -C "$PROJECT_DIR" branch --show-current)"
  [[ "$current_branch" == "$TARGET_BRANCH" ]] || {
    fail "ожидалась ветка '$TARGET_BRANCH', активна '$current_branch'"
  }

  previous_commit="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
  git -C "$PROJECT_DIR" fetch --prune origin "$TARGET_BRANCH"
  target_commit="$(git -C "$PROJECT_DIR" rev-parse "origin/$TARGET_BRANCH")"

  if ! git -C "$PROJECT_DIR" merge-base --is-ancestor "$previous_commit" "$target_commit"; then
    fail "origin/$TARGET_BRANCH не является fast-forward продолжением текущего commit"
  fi

  export WB_UPDATE_PREVIOUS_COMMIT="$previous_commit"
  export WB_UPDATE_TARGET_COMMIT="$target_commit"

  if [[ "$previous_commit" == "$target_commit" ]]; then
    exec env \
      PROJECT_DIR="$PROJECT_DIR" \
      TARGET_BRANCH="$TARGET_BRANCH" \
      WB_UPDATE_LOCK_HELD=1 \
      WB_UPDATE_PREVIOUS_COMMIT="$previous_commit" \
      WB_UPDATE_TARGET_COMMIT="$target_commit" \
      "$PROJECT_DIR/ops/update_systemd.sh" "$@"
  fi

  BOOTSTRAP_FILE="$(mktemp "${TMPDIR:-/tmp}/wb-insight-updater.XXXXXX.sh")"
  git -C "$PROJECT_DIR" show "$target_commit:ops/update_systemd.sh" >"$BOOTSTRAP_FILE"
  chmod 0700 "$BOOTSTRAP_FILE"

  printf 'Обновлятор подготовлен из целевого commit %s без переключения рабочего дерева.\n' "$target_commit"
  exec env \
    PROJECT_DIR="$PROJECT_DIR" \
    TARGET_BRANCH="$TARGET_BRANCH" \
    WB_UPDATE_LOCK_HELD=1 \
    WB_UPDATE_PREVIOUS_COMMIT="$previous_commit" \
    WB_UPDATE_TARGET_COMMIT="$target_commit" \
    WB_UPDATE_BOOTSTRAP_FILE="$BOOTSTRAP_FILE" \
    "$BOOTSTRAP_FILE" "$@"
}

acquire_update_lock
resolve_target "$@"
