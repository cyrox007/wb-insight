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
UPDATE_LOCK_FILE="${UPDATE_LOCK_FILE:-/tmp/wb-insight-update.lock}"
UPDATE_BACKUP_DIR="${UPDATE_BACKUP_DIR:-/var/backups/wb-insight/update}"
UPDATE_STATE_DIR="${UPDATE_STATE_DIR:-/var/tmp/wb-insight-update}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

PREVIOUS_COMMIT="${WB_UPDATE_PREVIOUS_COMMIT:-}"
TARGET_COMMIT="${WB_UPDATE_TARGET_COMMIT:-}"
CANDIDATE_DIR=""
CANDIDATE_BACKEND=""
CANDIDATE_FRONTEND=""
NEW_VENV=""
PREVIOUS_VENV_KIND=""
PREVIOUS_VENV_TARGET=""
PREVIOUS_VENV_PATH=""
FRONTEND_STATE_FILE=""
ROLLBACK_DB_BACKUP=""
ACTIVATION_STARTED=false
DB_MUTATION_STARTED=false
REPO_SWITCHED=false
VENV_SWITCHED=false
FRONTEND_SWITCHED=false
SUCCESS=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { printf '%b\n' "${YELLOW}$*${NC}"; }
ok() { printf '%b\n' "${GREEN}$*${NC}"; }
error() { printf '%b\n' "${RED}$*${NC}" >&2; }
fail() {
  error "$*"
  return 1
}

run_root() {
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Не найдена обязательная команда: $1"
}

acquire_update_lock_if_needed() {
  if [[ "${WB_UPDATE_LOCK_HELD:-0}" == "1" ]]; then
    return 0
  fi
  require_cmd flock
  exec 8>"$UPDATE_LOCK_FILE"
  if ! flock -n 8; then
    fail "Другое обновление WB Insight уже выполняется: $UPDATE_LOCK_FILE"
  fi
  export WB_UPDATE_LOCK_HELD=1
}

check_python() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    fail "WB Insight требует Python 3.12 и пакет python3.12-venv."
  }
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(
        f"Требуется Python 3.12, обнаружен {sys.version.split()[0]}"
    )
print(f"python={sys.version.split()[0]}")
PY
}

check_node() {
  node - <<'NODE'
const [major, minor] = process.versions.node.split('.').map(Number)
const ok = (major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major > 22
if (!ok) {
  console.error(`Требуется Node ^20.19.0 или >=22.12.0, обнаружен ${process.versions.node}`)
  process.exit(1)
}
console.log(`node=${process.versions.node}`)
NODE
}

check_unit_exists() {
  systemctl cat "$1" >/dev/null 2>&1 || fail "Не найден systemd unit: $1"
}

check_services_stable() {
  local service
  for service in wb-backend wb-celery wb-celery-beat; do
    if ! systemctl is-active --quiet "$service"; then
      run_root systemctl status "$service" --no-pager -l || true
      run_root journalctl -u "$service" -n 100 --no-pager || true
      error "Сервис не работает после переключения: $service"
      return 1
    fi
  done
}

install_celery_dropins() {
  local source_root="$1"
  local worker_src="$source_root/ops/systemd/wb-celery.service.d/10-wb-insight.conf"
  local beat_src="$source_root/ops/systemd/wb-celery-beat.service.d/10-wb-insight.conf"

  [[ -f "$worker_src" ]] || fail "Не найден основной drop-in Celery worker: $worker_src"
  [[ -f "$beat_src" ]] || fail "Не найден основной drop-in Celery beat: $beat_src"

  run_root install -d -m 0755 \
    "$SYSTEMD_DIR/wb-celery.service.d" \
    "$SYSTEMD_DIR/wb-celery-beat.service.d"
  run_root install -m 0644 \
    "$worker_src" \
    "$SYSTEMD_DIR/wb-celery.service.d/10-wb-insight.conf"
  run_root install -m 0644 \
    "$beat_src" \
    "$SYSTEMD_DIR/wb-celery-beat.service.d/10-wb-insight.conf"
  run_root systemctl daemon-reload
}

cleanup_old_release_venvs() {
  [[ "$RELEASE_KEEP" =~ ^[0-9]+$ ]] || return 0
  (( RELEASE_KEEP > 0 )) || return 0

  mapfile -t releases < <(
    find "$BACKEND_DIR" -maxdepth 1 -mindepth 1 -type d \
      -name 'venv.release.*' -printf '%T@ %p\n' 2>/dev/null |
      sort -nr |
      awk '{print $2}'
  )
  local index
  for ((index=RELEASE_KEEP; index<${#releases[@]}; index++)); do
    rm -rf -- "${releases[$index]}"
  done
}

resolve_update_context() {
  [[ -d "$PROJECT_DIR/.git" ]] || fail "Каталог не является Git-репозиторием: $PROJECT_DIR"
  if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]]; then
    fail "Рабочее дерево содержит изменения. Сначала сохраните или отмените их."
  fi

  local current_branch
  current_branch="$(git -C "$PROJECT_DIR" branch --show-current)"
  [[ "$current_branch" == "$TARGET_BRANCH" ]] || {
    fail "Ожидалась ветка '$TARGET_BRANCH', активна '$current_branch'"
  }

  if [[ -z "$PREVIOUS_COMMIT" || -z "$TARGET_COMMIT" ]]; then
    PREVIOUS_COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
    git -C "$PROJECT_DIR" fetch --prune origin "$TARGET_BRANCH"
    TARGET_COMMIT="$(git -C "$PROJECT_DIR" rev-parse "origin/$TARGET_BRANCH")"
  fi

  [[ "$(git -C "$PROJECT_DIR" rev-parse HEAD)" == "$PREVIOUS_COMMIT" ]] || {
    fail "Рабочий HEAD изменился после начала обновления"
  }
  git -C "$PROJECT_DIR" cat-file -e "$TARGET_COMMIT^{commit}"
  if ! git -C "$PROJECT_DIR" merge-base --is-ancestor "$PREVIOUS_COMMIT" "$TARGET_COMMIT"; then
    fail "Целевой commit не является fast-forward продолжением текущей версии"
  fi
}

prepare_candidate_snapshot() {
  CANDIDATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wb-insight-candidate.XXXXXX")"
  CANDIDATE_BACKEND="$CANDIDATE_DIR/backend"
  CANDIDATE_FRONTEND="$CANDIDATE_DIR/frontend"

  git -C "$PROJECT_DIR" archive "$TARGET_COMMIT" | tar -x -C "$CANDIDATE_DIR"

  if [[ -f "$BACKEND_DIR/.env" && ! -e "$CANDIDATE_BACKEND/.env" ]]; then
    ln -s "$BACKEND_DIR/.env" "$CANDIDATE_BACKEND/.env"
  fi

  [[ -f "$CANDIDATE_BACKEND/requirements.txt" ]] || {
    fail "В кандидате отсутствует backend/requirements.txt"
  }
  [[ -f "$CANDIDATE_FRONTEND/package-lock.json" ]] || {
    fail "В кандидате отсутствует frontend/package-lock.json"
  }
  [[ -f "$CANDIDATE_DIR/ops/postgres_backup.sh" ]] || {
    fail "В кандидате отсутствует скрипт резервного копирования БД"
  }
  [[ -f "$CANDIDATE_DIR/ops/postgres_restore.sh" ]] || {
    fail "В кандидате отсутствует скрипт восстановления БД"
  }

  bash -n "$CANDIDATE_DIR/update.sh"
  bash -n "$CANDIDATE_DIR/ops/update_systemd.sh"
  bash -n "$CANDIDATE_DIR/ops/publish_frontend.sh"
}

build_candidate_runtime() {
  log "[1/6] Подготовка Python-среды кандидата..."
  NEW_VENV="$BACKEND_DIR/venv.release.$STAMP"
  [[ ! -e "$NEW_VENV" ]] || fail "Release-venv уже существует: $NEW_VENV"

  "$PYTHON_BIN" -m venv "$NEW_VENV"
  "$NEW_VENV/bin/python" -m pip install --upgrade pip setuptools wheel
  "$NEW_VENV/bin/python" -m pip install --requirement "$CANDIDATE_BACKEND/requirements.txt"

  (
    cd "$CANDIDATE_BACKEND"
    PYTHONPATH=. "$NEW_VENV/bin/python" - <<'PY'
import fastapi
import numpy
import pandas
import models
from celery_app import celery_app

print(
    f"numpy={numpy.__version__} pandas={pandas.__version__} "
    f"fastapi={fastapi.__version__}"
)
print(f"celery_app={celery_app.main}")
PY
    "$NEW_VENV/bin/python" -m celery -A celery_app:celery_app report >/dev/null
    "$NEW_VENV/bin/python" -m alembic --version >/dev/null
  )

  log "[2/6] Сборка клиентской части кандидата..."
  (
    cd "$CANDIDATE_FRONTEND"
    npm ci
    VITE_API_BASE_URL=/api npm run build
  )
  [[ -f "$CANDIDATE_FRONTEND/dist/index.html" ]] || {
    fail "Клиентская сборка кандидата не создала dist/index.html"
  }

  run_root nginx -t >/dev/null
  ok "Кандидат полностью собран до изменения runtime и БД."
}

load_database_environment() {
  local env_file="$BACKEND_DIR/.env"
  local exports
  exports="$(
    "$NEW_VENV/bin/python" - "$env_file" <<'PY'
import os
import shlex
import sys
from pathlib import Path

from dotenv import dotenv_values

path = Path(sys.argv[1])
values = dotenv_values(path) if path.is_file() else {}
names = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "BACKUP_ENCRYPTION_PASSPHRASE_FILE",
    "BACKUP_RETENTION_DAYS",
)
for name in names:
    value = os.environ.get(name)
    if value is None:
        value = values.get(name)
    if value is not None:
        print(f"export {name}={shlex.quote(str(value))}")
PY
  )"
  eval "$exports"

  local required
  for required in \
    DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD BACKUP_ENCRYPTION_PASSPHRASE_FILE
  do
    [[ -n "${!required:-}" ]] || fail "Для rollback не задано значение $required"
  done
  [[ -r "$BACKUP_ENCRYPTION_PASSPHRASE_FILE" ]] || {
    fail "Файл ключевой фразы резервной копии недоступен для чтения"
  }
}

prepare_backup_directory() {
  local uid gid
  uid="$(id -u)"
  gid="$(id -g)"
  run_root install -d -m 0700 -o "$uid" -g "$gid" "$UPDATE_BACKUP_DIR"
  mkdir -p "$UPDATE_STATE_DIR"
}

stop_application_writers() {
  ACTIVATION_STARTED=true
  log "[3/6] Остановка API и фоновых обработчиков для согласованного переключения..."
  run_root systemctl stop wb-backend wb-celery wb-celery-beat
}

create_database_rollback_point() {
  local backup_output
  log "Создание зашифрованной точки восстановления PostgreSQL..."
  backup_output="$(
    BACKUP_DIR="$UPDATE_BACKUP_DIR" \
      bash "$CANDIDATE_DIR/ops/postgres_backup.sh"
  )"
  ROLLBACK_DB_BACKUP="$(
    printf '%s\n' "$backup_output" |
      sed -n 's/^backup=//p' |
      tail -n 1
  )"
  [[ -n "$ROLLBACK_DB_BACKUP" && -r "$ROLLBACK_DB_BACKUP" ]] || {
    fail "Не удалось определить созданную резервную копию БД"
  }
  [[ -r "${ROLLBACK_DB_BACKUP}.sha256" ]] || {
    fail "Для резервной копии БД отсутствует контрольная сумма"
  }
  ok "Точка восстановления БД создана: $ROLLBACK_DB_BACKUP"
}

apply_candidate_migrations() {
  log "[4/6] Применение миграций из полностью собранного кандидата..."
  DB_MUTATION_STARTED=true
  (
    cd "$CANDIDATE_BACKEND"
    "$NEW_VENV/bin/python" -m alembic upgrade head
  )
}

switch_repository() {
  log "Переключение рабочего дерева на целевой commit..."
  git -C "$PROJECT_DIR" reset --hard "$TARGET_COMMIT"
  REPO_SWITCHED=true
}

switch_release_venv() {
  PREVIOUS_VENV_PATH="$BACKEND_DIR/venv.previous.$STAMP"

  if [[ -L "$VENV_DIR" ]]; then
    PREVIOUS_VENV_KIND="symlink"
    PREVIOUS_VENV_TARGET="$(readlink -f "$VENV_DIR")"
    [[ -n "$PREVIOUS_VENV_TARGET" ]] || fail "Не удалось определить текущий release-venv"
    rm "$VENV_DIR"
  elif [[ -d "$VENV_DIR" ]]; then
    PREVIOUS_VENV_KIND="directory"
    mv "$VENV_DIR" "$PREVIOUS_VENV_PATH"
  elif [[ -e "$VENV_DIR" ]]; then
    fail "backend/venv должен быть каталогом или symlink"
  else
    PREVIOUS_VENV_KIND="missing"
  fi

  ln -s "$NEW_VENV" "$VENV_DIR"
  VENV_SWITCHED=true

  (
    cd "$BACKEND_DIR"
    "$VENV_DIR/bin/python" --version
    PYTHONPATH=. "$VENV_DIR/bin/python" -c \
      'from celery_app import celery_app; print(f"celery_app={celery_app.main}")'
    "$VENV_DIR/bin/python" -m celery -A celery_app:celery_app report >/dev/null
    "$VENV_DIR/bin/python" -m alembic --version >/dev/null
  )
}

start_candidate_services() {
  install_celery_dropins "$PROJECT_DIR"
  run_root systemctl enable wb-backend wb-celery wb-celery-beat >/dev/null
  run_root systemctl restart wb-backend wb-celery wb-celery-beat
}

wait_backend_ready() {
  local ready=false
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS "$HEALTH_URL" >/tmp/wb-insight-ready.json 2>/dev/null; then
      ready=true
      break
    fi
    sleep 1
  done

  if [[ "$ready" != true ]]; then
    run_root journalctl -u wb-backend -n 100 --no-pager || true
    fail "Проверка готовности backend не пройдена: $HEALTH_URL"
  fi
}

publish_candidate_frontend() {
  FRONTEND_STATE_FILE="$(mktemp "${TMPDIR:-/tmp}/wb-insight-frontend-state.XXXXXX")"
  FRONTEND_BUILD_DIR="$CANDIDATE_FRONTEND/dist" \
    FRONTEND_PUBLISH_STATE_FILE="$FRONTEND_STATE_FILE" \
    bash "$PROJECT_DIR/ops/publish_frontend.sh"

  local PUBLISH_SWITCHED="false"
  source "$FRONTEND_STATE_FILE"
  FRONTEND_SWITCHED="$PUBLISH_SWITCHED"
}

postcheck_candidate() {
  log "[6/6] Проверка согласованности активной версии..."
  sleep "$STABILIZE_SECONDS"
  check_services_stable
  sleep "$STABILIZE_SECONDS"
  check_services_stable

  (
    cd "$BACKEND_DIR"
    "$VENV_DIR/bin/python" -m celery -A celery_app:celery_app \
      inspect ping --timeout=5 >/tmp/wb-insight-celery-ping.txt
  )
  grep -q 'pong' /tmp/wb-insight-celery-ping.txt || {
    fail "Celery worker не ответил на inspect ping"
  }

  run_root nginx -t >/dev/null
  wait_backend_ready
  [[ "$(git -C "$PROJECT_DIR" rev-parse HEAD)" == "$TARGET_COMMIT" ]] || {
    fail "После итоговой проверки активен неожиданный Git commit"
  }
}

fault_point() {
  local phase="$1"
  if [[ "${WB_UPDATE_ENABLE_FAULT_INJECTION:-0}" != "1" ]]; then
    return 0
  fi
  if [[ "${WB_UPDATE_FAIL_PHASE:-}" == "$phase" ]]; then
    fail "Тестовое прерывание обновления на фазе: $phase"
  fi
}

restore_frontend_from_state() {
  [[ "$FRONTEND_SWITCHED" == true && -r "$FRONTEND_STATE_FILE" ]] || return 0

  local DEPLOY_DIR=""
  local PREVIOUS_DIR=""
  local HAD_PREVIOUS="false"
  source "$FRONTEND_STATE_FILE"

  [[ -n "$DEPLOY_DIR" ]] || return 1
  run_root rm -rf -- "$DEPLOY_DIR"
  if [[ "$HAD_PREVIOUS" == "true" ]]; then
    [[ -n "$PREVIOUS_DIR" && -e "$PREVIOUS_DIR" ]] || return 1
    run_root mv -- "$PREVIOUS_DIR" "$DEPLOY_DIR"
  fi
  run_root nginx -t >/dev/null
  run_root systemctl reload nginx
}

restore_previous_venv() {
  [[ "$VENV_SWITCHED" == true ]] || return 0

  rm -f -- "$VENV_DIR"
  case "$PREVIOUS_VENV_KIND" in
    symlink)
      [[ -n "$PREVIOUS_VENV_TARGET" && -e "$PREVIOUS_VENV_TARGET" ]] || return 1
      ln -s "$PREVIOUS_VENV_TARGET" "$VENV_DIR"
      ;;
    directory)
      [[ -d "$PREVIOUS_VENV_PATH" ]] || return 1
      mv "$PREVIOUS_VENV_PATH" "$VENV_DIR"
      ;;
    missing)
      ;;
    *)
      return 1
      ;;
  esac
}

restore_database_if_needed() {
  [[ "$DB_MUTATION_STARTED" == true ]] || return 0
  [[ -n "$ROLLBACK_DB_BACKUP" && -r "$ROLLBACK_DB_BACKUP" ]] || return 1

  RESTORE_CONFIRM=YES \
    bash "$CANDIDATE_DIR/ops/postgres_restore.sh" "$ROLLBACK_DB_BACKUP"
}

write_rollback_proof() {
  local status="$1"
  local line="$2"
  local proof="$UPDATE_STATE_DIR/rollback-$STAMP.txt"
  mkdir -p "$UPDATE_STATE_DIR"
  {
    printf 'статус=%s\n' "$status"
    printf 'предыдущий_commit=%s\n' "$PREVIOUS_COMMIT"
    printf 'целевой_commit=%s\n' "$TARGET_COMMIT"
    printf 'строка_ошибки=%s\n' "$line"
    printf 'бд_изменялась=%s\n' "$DB_MUTATION_STARTED"
    printf 'время_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >"$proof"
  printf '%s\n' "$proof"
}

rollback_update() {
  local line="$1"
  local rollback_ok=true
  local proof

  [[ "$ACTIVATION_STARTED" == true ]] || return 0

  error "Начат автоматический rollback к предыдущей согласованной версии."
  run_root systemctl stop wb-backend wb-celery wb-celery-beat || rollback_ok=false

  if ! restore_database_if_needed; then
    error "Не удалось восстановить PostgreSQL. Сервисы останутся остановленными."
    rollback_ok=false
  fi

  if ! restore_frontend_from_state; then
    error "Не удалось восстановить предыдущий frontend."
    rollback_ok=false
  fi

  if [[ "$REPO_SWITCHED" == true ]]; then
    git -C "$PROJECT_DIR" reset --hard "$PREVIOUS_COMMIT" || rollback_ok=false
  fi

  if ! restore_previous_venv; then
    error "Не удалось восстановить предыдущую Python-среду."
    rollback_ok=false
  fi

  if [[ -d "$PROJECT_DIR/ops/systemd" ]]; then
    install_celery_dropins "$PROJECT_DIR" || rollback_ok=false
  fi

  proof="$(write_rollback_proof "$rollback_ok" "$line")"
  if [[ "$rollback_ok" == true ]]; then
    run_root systemctl restart wb-backend wb-celery wb-celery-beat || rollback_ok=false
    if [[ "$rollback_ok" == true ]]; then
      sleep "$STABILIZE_SECONDS"
      check_services_stable || rollback_ok=false
    fi
  fi

  if [[ "$rollback_ok" == true ]]; then
    error "Rollback завершён. Доказательство: $proof"
  else
    error "Rollback завершён не полностью. Сервисы оставлены в безопасном состоянии; требуется ручное вмешательство. Доказательство: $proof"
  fi
}

cleanup_workspace() {
  local rc=$?

  if [[ "$SUCCESS" != true && -n "$NEW_VENV" && -d "$NEW_VENV" ]]; then
    if [[ ! -L "$VENV_DIR" || "$(readlink -f "$VENV_DIR" 2>/dev/null || true)" != "$NEW_VENV" ]]; then
      rm -rf -- "$NEW_VENV" || true
    fi
  fi
  [[ -n "$CANDIDATE_DIR" ]] && rm -rf -- "$CANDIDATE_DIR" || true
  [[ -n "$FRONTEND_STATE_FILE" ]] && rm -f -- "$FRONTEND_STATE_FILE" || true
  [[ -n "${WB_UPDATE_BOOTSTRAP_FILE:-}" ]] && rm -f -- "$WB_UPDATE_BOOTSTRAP_FILE" || true

  return "$rc"
}

on_error() {
  local rc=$?
  local line="${BASH_LINENO[0]:-неизвестно}"
  trap - ERR
  set +e
  error "Обновление прервано на строке $line, код выхода $rc."
  error "Предыдущий commit: ${PREVIOUS_COMMIT:-не определён}"
  error "Целевой commit: ${TARGET_COMMIT:-не определён}"
  rollback_update "$line"
  exit "$rc"
}

trap on_error ERR
trap cleanup_workspace EXIT

acquire_update_lock_if_needed

log "[preflight] Проверка host, Git и systemd-контракта..."
require_cmd git
require_cmd tar
require_cmd mktemp
require_cmd node
require_cmd npm
require_cmd curl
require_cmd systemctl
require_cmd install
require_cmd nginx
require_cmd pg_dump
require_cmd pg_restore
require_cmd psql
require_cmd openssl
require_cmd sha256sum
check_python
check_node
for service in wb-backend wb-celery wb-celery-beat; do
  check_unit_exists "$service"
done
resolve_update_context
prepare_candidate_snapshot

if [[ "$MODE" == "--preflight-only" ]]; then
  ok "Preflight транзакционного systemd-updater пройден."
  exit 0
fi
[[ -z "$MODE" ]] || fail "Неизвестный аргумент: $MODE"

log "Предыдущий commit: $PREVIOUS_COMMIT"
log "Целевой commit:     $TARGET_COMMIT"

build_candidate_runtime
load_database_environment
prepare_backup_directory
fault_point "candidate"

stop_application_writers
create_database_rollback_point
fault_point "backup"

apply_candidate_migrations
fault_point "migrations"

log "[5/6] Атомарное переключение runtime..."
switch_repository
switch_release_venv
start_candidate_services
wait_backend_ready
fault_point "runtime"

publish_candidate_frontend
fault_point "frontend"

postcheck_candidate
SUCCESS=true
cleanup_old_release_venvs

ok "WB Insight успешно обновлён транзакционно."
ok "Предыдущий commit: $PREVIOUS_COMMIT"
ok "Текущий commit:     $TARGET_COMMIT"
ok "Backend Python:     $($VENV_DIR/bin/python --version 2>&1)"
ok "Версия продукта:    $(tr -d '\r\n' < "$PROJECT_DIR/VERSION")"
