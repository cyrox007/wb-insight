#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup.dump.enc>" >&2
  exit 2
fi

backup="$1"
checksum="${backup}.sha256"

: "${DB_HOST:?DB_HOST is required}"
: "${DB_PORT:=5432}"
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
drill_db="${RESTORE_DRILL_DB:-wb_insight_restore_drill_$(date -u +%Y%m%d%H%M%S)}"

export PGPASSWORD="$DB_PASSWORD"
cleanup() {
  rm -f "$tmp"
  dropdb \
    --if-exists \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    "$drill_db" >/dev/null 2>&1 || true
}
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" \
  -in "$backup" \
  -out "$tmp"

createdb \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  "$drill_db"

pg_restore \
  --no-owner \
  --no-privileges \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --dbname="$drill_db" \
  "$tmp"

alembic_revision="$(psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --dbname="$drill_db" \
  --set=ON_ERROR_STOP=1 \
  --tuples-only \
  --no-align \
  --command='SELECT version_num FROM alembic_version LIMIT 1;')"

table_count="$(psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --dbname="$drill_db" \
  --set=ON_ERROR_STOP=1 \
  --tuples-only \
  --no-align \
  --command="SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"

if [[ -z "$alembic_revision" || "$table_count" -lt 1 ]]; then
  echo "Restore drill failed validation" >&2
  exit 1
fi

printf 'restore_drill=success\ndatabase=%s\nalembic_revision=%s\npublic_tables=%s\n' \
  "$drill_db" "$alembic_revision" "$table_count"
