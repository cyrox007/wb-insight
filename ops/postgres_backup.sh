#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

: "${DB_HOST:?Не задан DB_HOST}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?Не задан DB_NAME}"
: "${DB_USER:?Не задан DB_USER}"
: "${DB_PASSWORD:?Не задан DB_PASSWORD}"
: "${BACKUP_ENCRYPTION_PASSPHRASE_FILE:?Не задан BACKUP_ENCRYPTION_PASSPHRASE_FILE}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

if [[ ! -r "$BACKUP_ENCRYPTION_PASSPHRASE_FILE" ]]; then
  echo "Файл ключевой фразы шифрования резервной копии недоступен для чтения" >&2
  exit 1
fi
if ! [[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]] || (( BACKUP_RETENTION_DAYS < 1 )); then
  echo "BACKUP_RETENTION_DAYS должен быть положительным целым числом" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
base="wb-insight_${DB_NAME}_${timestamp}"
plain="${BACKUP_DIR}/${base}.dump"
encrypted="${plain}.enc"
checksum="${encrypted}.sha256"

cleanup() {
  rm -f "$plain"
}
trap cleanup EXIT

export PGPASSWORD="$DB_PASSWORD"
pg_dump \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-privileges \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --file="$plain" \
  "$DB_NAME"

openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
  -pass "file:${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" \
  -in "$plain" \
  -out "$encrypted"

(
  cd "$BACKUP_DIR"
  sha256sum "$(basename "$encrypted")" >"$(basename "$checksum")"
)

find "$BACKUP_DIR" -type f \
  \( -name 'wb-insight_*.dump.enc' -o -name 'wb-insight_*.dump.enc.sha256' \) \
  -mtime "+${BACKUP_RETENTION_DAYS}" -delete

printf 'backup=%s\nchecksum=%s\n' "$encrypted" "$checksum"
