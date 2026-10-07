#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ $# -ne 1 ]]; then
  echo "Использование: RESTORE_CONFIRM=YES $0 <backup.dump.enc>" >&2
  exit 2
fi
if [[ "${RESTORE_CONFIRM:-}" != "YES" ]]; then
  echo "Разрушающее восстановление отменено: задайте RESTORE_CONFIRM=YES" >&2
  exit 2
fi

backup="$1"
checksum="${backup}.sha256"

: "${DB_HOST:?Не задан DB_HOST}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?Не задан DB_NAME}"
: "${DB_USER:?Не задан DB_USER}"
: "${DB_PASSWORD:?Не задан DB_PASSWORD}"
: "${BACKUP_ENCRYPTION_PASSPHRASE_FILE:?Не задан BACKUP_ENCRYPTION_PASSPHRASE_FILE}"

[[ -r "$backup" ]] || {
  echo "Резервная копия недоступна для чтения: $backup" >&2
  exit 1
}
[[ -r "$checksum" ]] || {
  echo "Контрольная сумма недоступна для чтения: $checksum" >&2
  exit 1
}
[[ -r "$BACKUP_ENCRYPTION_PASSPHRASE_FILE" ]] || {
  echo "Файл ключевой фразы шифрования резервной копии недоступен для чтения" >&2
  exit 1
}

(
  cd "$(dirname "$backup")"
  sha256sum --check "$(basename "$checksum")"
)

tmp="$(mktemp --suffix=.dump)"
cleanup() {
  rm -f "$tmp"
}
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" \
  -in "$backup" \
  -out "$tmp"

export PGPASSWORD="$DB_PASSWORD"
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  "$tmp"

psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --set=ON_ERROR_STOP=1 \
  --tuples-only \
  --command='SELECT version_num FROM alembic_version;'

echo "Восстановление завершено, alembic_version доступна для чтения."
