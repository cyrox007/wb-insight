# WB Insight — Operations Runbook

Версия документа: P26 / `0.9.0-alpha.3` candidate.

Этот runbook описывает минимальный эксплуатационный контур WB Web v1: operational monitoring, alerting, PostgreSQL backup и restore drill. Он дополняет `docs/PRODUCTION_DEPLOYMENT.md` и не заменяет provider-specific runbook инфраструктуры, где будет размещён production.

## 1. Operational monitoring

### Публичные health endpoints

- `GET /health/live` — процесс приложения жив; внешние зависимости не проверяются.
- `GET /health/ready` — PostgreSQL и Redis доступны; при деградации возвращается HTTP 503.

Эти endpoints предназначены для load balancer / orchestrator / uptime monitoring.

### Super-admin operations snapshot

`GET /control-panel/operations/health`

Endpoint защищён `require_super_admin` и возвращает только агрегированные operational signals. Seller token values, payment credentials, user PII, request bodies и raw provider errors туда не включаются.

Проверяются:

- terminal failed sync jobs за заданное lookback-окно;
- processing jobs с истёкшим lease;
- sync states без успешной синхронизации дольше SLA;
- активные marketplace credentials, срок которых уже истёк;
- credentials, которые истекут в warning window;
- срок ротации `WB_SERVICE_SECRET` без вывода самого секрета;
- HTTP 5xx rate за короткое окно.

Общий статус:

- `ok` — критических и warning сигналов нет;
- `warning` — есть предупреждение, например credential/service secret скоро истечёт;
- `degraded` — есть critical/error condition.

### HTTP telemetry

При `OPS_HTTP_METRICS_ENABLED=true` middleware пишет в Redis только minute-bucket counters:

- общее число HTTP responses;
- число HTTP 5xx.

Path, query string, body, user ID, marketplace account и token не сохраняются в этих counters.

Если Redis telemetry недоступна, обработка пользовательского request не падает: metrics path fail-open.

### Scheduled alert check

Celery Beat запускает `tasks.processors.operations_monitor.run` с интервалом `OPS_ALERT_CHECK_INTERVAL_SECONDS`.

При `warning/degraded`:

1. snapshot пишется как structured warning в operations log;
2. при настроенном `OPS_ALERT_WEBHOOK_URL` отправляется агрегированный JSON webhook;
3. одинаковые alerts дедуплицируются в Redis на `OPS_ALERT_REPEAT_SECONDS`.

Webhook обязан использовать HTTPS и принадлежать доверенной monitoring-системе. В webhook не передаются raw exception bodies и secrets.

### Рекомендуемые production thresholds для первого релиза

- stale sync: `OPS_SYNC_STALE_MINUTES=180`;
- failed-job lookback: `60` минут;
- seller credential warning: `14` дней;
- WB service-secret rotation warning: `30` дней;
- 5xx window: `5` минут;
- critical 5xx rate: `>=5%` при минимум `20` requests;
- operations check: каждые `15` минут;
- повтор одинакового alert: не чаще одного раза в час.

Эти значения являются стартовыми operational defaults. После появления production traffic их нужно пересмотреть по фактической частоте sync и нагрузке.

## 2. WB service secret rotation

`WB_SERVICE_SECRET` является production credential сервиса и никогда не должен попадать в git, frontend bundle, logs или monitoring payload.

Для контроля ротации задаётся только дата/время истечения или внутреннего rotation deadline:

```text
OPS_WB_SERVICE_SECRET_EXPIRES_AT=2026-12-01T00:00:00+03:00
OPS_WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS=30
```

Требуется timezone-aware ISO-8601 значение.

Поведение monitoring:

- service secret не настроен — `not_applicable` вне production; production backend и так fail-closed;
- secret есть, deadline не указан — warning;
- deadline некорректен — critical;
- до deadline <= `OPS_WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS` — warning;
- deadline прошёл — critical.

После rotation дата должна быть обновлена одновременно с secret management record.

## 3. PostgreSQL backup policy

### Базовая политика WB Web v1

До RC принимаем следующие operational targets:

- backup frequency: минимум один полный backup каждые 24 часа;
- retention: минимум 14 дней;
- RPO target: <=24 часа;
- RTO target: <=4 часа;
- минимум одна копия должна находиться вне production host;
- backup должен быть зашифрован до отправки во внешнее хранилище;
- restore drill обязателен до `1.0.0-rc.1` и повторяется после существенных изменений схемы/backup process.

RPO/RTO становятся подтверждёнными только после реального restore drill с замером времени. До этого это цели, а не гарантии.

### Backup script

`ops/postgres_backup.sh`

Требует PostgreSQL client tools и OpenSSL.

Обязательные environment variables:

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
BACKUP_ENCRYPTION_PASSPHRASE_FILE
```

Опционально:

```text
BACKUP_DIR=/var/backups/wb-insight
BACKUP_RETENTION_DAYS=14
```

Скрипт:

1. создаёт `pg_dump --format=custom`;
2. шифрует dump через AES-256-CBC + PBKDF2;
3. удаляет plaintext dump;
4. создаёт SHA-256 checksum для encrypted artifact;
5. удаляет backup artifacts старше retention policy.

Passphrase хранится в отдельном secret file и не должна находиться в backup directory, git или `.env.production`.

### Off-host copy

Скрипт намеренно не привязан к конкретному cloud/provider storage. После успешного backup encrypted `.dump.enc` и соответствующий `.sha256` должны быть отправлены в отдельное object/off-host storage средствами выбранной production infrastructure.

Успешный локальный backup без off-host copy не закрывает release requirement.

## 4. Restore

### Destructive restore

`ops/postgres_restore.sh <backup.dump.enc>`

По умолчанию скрипт отказывается работать. Для destructive restore требуется явное:

```text
RESTORE_CONFIRM=YES
```

Перед restore:

- проверяется SHA-256;
- artifact расшифровывается во временный файл с `umask 077`;
- plaintext удаляется через trap;
- после restore проверяется доступность `alembic_version`.

Production restore выполняется только после остановки write traffic/API/worker/beat и создания дополнительного pre-restore snapshot, если это возможно.

## 5. Restore drill

`ops/postgres_restore_drill.sh <backup.dump.enc>`

Drill не затрагивает production database:

1. проверяет checksum;
2. расшифровывает artifact;
3. создаёт отдельную временную БД;
4. выполняет `pg_restore`;
5. читает `alembic_version`;
6. проверяет наличие public tables;
7. удаляет drill database.

Успешный drill должен быть зафиксирован в release evidence минимум с:

- временем запуска/окончания;
- именем/датой backup artifact;
- восстановленной Alembic revision;
- количеством восстановленных public tables;
- фактическим restore duration;
- результатом `success/failure`.

Сам факт существования скрипта не считается выполненным restore drill.

## 6. Incident triage

При `degraded` сначала определить класс проблемы:

**Database/Redis readiness** — проверить managed service/containers, network/DNS, credentials, storage capacity. Не перезапускать бесконечно API, если downstream остаётся недоступен.

**Failed/stale sync** — проверить operations snapshot, затем Celery logs и конкретный provider category/HTTP class. Не деактивировать seller credential по произвольному 403/feature-level error: текущий sync engine уже разделяет auth/permission/feature errors.

**Expired processing lease** — worker recovery должен вернуть job в retry либо terminal failed по retry budget. Массовые expired leases — сигнал worker starvation/crashes.

**Credential expiry** — связаться с владельцем кабинета до фактического истечения. Seller credential values не передавать в support tickets/logs.

**WB service secret rotation** — подготовить новый secret, обновить secret store/env и rotation deadline, выполнить controlled restart и smoke всех WB categories.

**5xx spike** — сопоставить окно с application logs, readiness, DB/Redis и deployment events. HTTP telemetry сама не хранит request content.

## 7. Что блокирует RC

P26 закрывает кодовый baseline monitoring/backup, но для перехода в RC всё ещё нужны реальные эксплуатационные доказательства:

- monitoring webhook/alert destination настроен и проверен;
- uptime monitor проверяет `/health/ready` извне;
- ежедневный backup schedule реально включён;
- encrypted backups копируются off-host;
- выполнен успешный restore drill;
- RPO/RTO подтверждены фактическим drill;
- зафиксирован реальный WB service secret rotation deadline.

Эти пункты отслеживаются в `docs/RELEASE_READINESS.md`.
