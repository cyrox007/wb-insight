#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ $# -ne 1 ]]; then
  echo "Usage: RESTORE_CONFIRM=YES $0 <backup.dump.enc>" >&2
  exit 2
fi
if [[ "${RESTORE_CONFIRM:-}" != "YES" ]]; then
  echo "Refusing destructive restore: set RESTORE_CONFIRM=YES" >&2
  exit 2
fi

backup="$1"
checksum="${backup}.sha256"

: "${DB_HOST:?DB_HOST is required}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE_FILE:?BACKUP_ENCRYPTION_PASSPHRASE_FILE is required}"

[[ -r "$backup" ]] || { echo "Backup is not readable: $backup" >&2; exit 1; }
[[ -r "$checksum" ]] || { echo "Checksum is not readable: $checksum" >&2; exit 1; }
[[ -r "$BACKUP_ENCRYPTION_PASSPHRASE_FILE" ]] || {
  echo "Backup encryption passphrase file is not readable" >&2
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

echo "Restore completed and alembic_version is readable."
