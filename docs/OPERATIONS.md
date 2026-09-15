# WB Insight — operations runbook

Документ описывает эксплуатационный baseline WB Web v1: health, monitoring, alerts, backup/restore и incident triage. Он дополняет `PRODUCTION_DEPLOYMENT.md`.

## Health

- `GET /health/live` — процесс приложения жив; внешние зависимости не проверяются.
- `GET /health/ready` — PostgreSQL и Redis готовы; при деградации возвращается non-ready status.

Внешний uptime monitor должен проверять `/health/ready` через production HTTPS endpoint.

## Super-admin operations health

`GET /control-panel/operations/health` возвращает агрегированные operational signals без seller secrets/PII.

Проверяются:

- recent failed sync jobs;
- processing jobs с истёкшим lease;
- stale sync states;
- expired/expiring marketplace connections;
- WB service-secret rotation deadline;
- HTTP request/5xx telemetry.

Общие состояния: `ok`, `warning`, `degraded`.

## HTTP telemetry

При `OPS_HTTP_METRICS_ENABLED=true` middleware хранит в Redis minute-bucket counters общего числа responses и HTTP 5xx. Path/query/body/user/account/secret в эти counters не записываются.

Telemetry fail-open: её отказ не должен ломать пользовательский request path.

## Operations monitor и alerts

Celery Beat периодически запускает operations monitor.

При проблеме:

1. создаётся structured warning;
2. при `OPS_ALERT_WEBHOOK_URL` отправляется агрегированный HTTPS webhook;
3. одинаковые alerts дедуплицируются на заданное окно.

Стартовые defaults:

- stale sync — 180 минут;
- failed-job lookback — 60 минут;
- seller credential warning — 14 дней;
- service-secret rotation warning — 30 дней;
- 5xx window — 5 минут;
- threshold — 5% при минимум 20 requests;
- monitor interval — 15 минут;
- повтор одинакового alert — не чаще раза в час.

Это начальные значения. До RC они должны быть проверены на production-like traffic.

## WB service-secret rotation

Для monitoring задаётся timezone-aware deadline `OPS_WB_SERVICE_SECRET_EXPIRES_AT`. Сам secret никогда не попадает в monitoring payload.

Поведение:

- secret без deadline — warning;
- некорректный deadline — critical/degraded;
- deadline внутри warning window — warning;
- deadline прошёл — critical/degraded.

После rotation одновременно обновляются secret store и metadata deadline.

## Backup policy

До RC используются цели:

- полный backup минимум раз в 24 часа;
- retention минимум 14 дней;
- RPO target <=24h;
- RTO target <=4h;
- минимум одна encrypted copy вне production host.

Это цели, пока production-like restore drill не подтвердит фактические значения.

### Создание backup

`ops/postgres_backup.sh`:

- выполняет custom-format `pg_dump`;
- шифрует artifact AES-256-CBC + PBKDF2;
- удаляет plaintext dump;
- создаёт SHA-256 checksum;
- применяет retention cleanup.

Нужны DB environment и `BACKUP_ENCRYPTION_PASSPHRASE_FILE`. Passphrase file хранится отдельно от repository и backup directory.

После успешного локального backup encrypted artifact + checksum должны копироваться off-host/object storage.

## Restore

`ops/postgres_restore.sh <backup.dump.enc>` является destructive operation и требует явного `RESTORE_CONFIRM=YES`.

Перед восстановлением проверяется checksum, temporary plaintext защищается `umask 077` и удаляется после завершения. После restore проверяется `alembic_version`.

Production restore выполняется при остановленном write traffic и по утверждённой incident procedure.

## Restore drill

`ops/postgres_restore_drill.sh <backup.dump.enc>` восстанавливает backup в отдельную временную DB и не затрагивает production database.

Release evidence должно содержать:

- время drill;
- идентификатор/дату backup artifact;
- восстановленную Alembic revision;
- факт наличия public tables;
- duration;
- success/failure.

## Incident triage

### PostgreSQL/Redis not ready
Проверить provider/container, network, credentials и storage capacity. Не маскировать downstream outage бесконечным restart API.

### Failed/stale sync
Проверить operations snapshot и worker logs, затем классифицировать auth/permission/rate-limit/network/provider error. Не отзывать marketplace connection из-за любого 4xx/5xx.

### Expired lease
Worker recovery должен вернуть job в retry либо terminal failed по retry budget. Массовые expired leases указывают на starvation/crash/слишком короткий lease.

### Credential expiry
Пользователь должен обновить подключение до срока истечения. Access data нельзя переносить в support ticket/log.

### 5xx spike
Сопоставить окно с deployment events, readiness, DB/Redis и structured application logs.

### Payment incident
Проверять server-side provider state, idempotency и связь payment/subscription. Клиентский screenshot не является доказательством статуса.

## RC operational gate

До `1.0.0-rc.1` требуется фактическое подтверждение:

- alert destination подключён и test signal доставлен;
- external uptime работает;
- centralized logs/error triage доступны;
- ежедневный backup schedule включён;
- encrypted backups уходят off-host;
- production-like restore drill успешен;
- фактические RPO/RTO зафиксированы;
- service-secret rotation deadline определён;
- deploy/rollback drill выполнен.

Статус gate ведётся в `RELEASE_READINESS.md`.
