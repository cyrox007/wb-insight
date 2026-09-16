# WB Insight — production deployment

Текущий `main` находится на release-line **`0.9.0-alpha.11`**. Канонический production baseline проекта — container deployment через Docker Compose; существующие Ubuntu/systemd-инсталляции поддерживаются отдельным runbook [`SYSTEMD_DEPLOYMENT.md`](SYSTEMD_DEPLOYMENT.md).

## Topology

`compose.production.yml` содержит:

- PostgreSQL 16;
- Redis 7 с AOF;
- one-shot `alembic upgrade head`;
- FastAPI backend;
- Celery worker;
- один Celery Beat scheduler;
- Vue build, обслуживаемый nginx;
- same-origin nginx proxy для backend routes.

На зрелом production PostgreSQL/Redis можно заменить managed services, сохранив application environment contract.

## Подготовка host/environment

1. Подготовить Linux host/cluster с Docker Engine + Compose v2 либо эквивалентную container platform.
2. Настроить production PostgreSQL/Redis и persistent storage.
3. Подготовить domain/DNS.
4. Настроить TLS termination перед frontend/nginx.
5. Создать production secret store/environment по `.env.production.example`.
6. Открыть наружу только HTTPS frontend endpoint; БД, Redis и backend должны оставаться приватными.
7. Подключить monitoring/logging/backup infrastructure.

## Конфигурация

```bash
cp .env.production.example .env.production
# заменить placeholders через безопасный процесс управления секретами
```

Обязательные группы описаны в `CONFIGURATION.md`. Production работает fail-closed для критичной security/WB конфигурации.

## Первый deploy

```bash
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

`migrate` должен успешно завершиться до старта API/worker.

Проверка локального entrypoint:

```bash
docker compose --env-file .env.production -f compose.production.yml ps
curl -fsS http://127.0.0.1:${PUBLIC_HTTP_PORT:-8080}/health/live
curl -fsS http://127.0.0.1:${PUBLIC_HTTP_PORT:-8080}/health/ready
```

После этого те же health/smoke проверки выполняются через реальный публичный HTTPS hostname.

## HTTPS boundary

Bundled nginx слушает container HTTP port и не является финальным TLS terminator. Внешний reverse proxy/load balancer должен обеспечивать HTTPS.

Production значения включают:

- `SERVER_HTTP_PROTOCOL=https://`;
- реальный `SERVER_ADDR`;
- `COOKIE_SECURE=true`;
- точный HTTPS origin в `ALLOWED_ORIGINS`;
- реальные HTTPS Sber return/fail endpoints при включённом acquiring.

## Gateway routing

Frontend/nginx обслуживает SPA и проксирует backend routes same-origin. Release-integrity CI поднимает реальный container и проверяет как минимум `/auth`, `/dashboard`, `/billing`, `/legal`, `/control-panel` и `/health`.

## Upgrade

1. Зафиксировать текущий deployed version/commit.
2. Создать encrypted backup и убедиться в наличии off-host copy.
3. Checkout exact release tag/commit.
4. Проверить `VERSION`/release notes.
5. Build new images.
6. Выполнить migration release step.
7. Запустить application processes.
8. Проверить `/health/ready`.
9. Выполнить release smoke.
10. Сохранить release evidence и держать previous image доступным до окончания validation.

Для существующей systemd-инсталляции не используйте произвольный `git pull && pip install` скрипт: актуальный backend требует Python **3.12**, а frontend release install должен идти через lockfile. Используйте [`SYSTEMD_DEPLOYMENT.md`](SYSTEMD_DEPLOYMENT.md) и `ops/update_systemd.sh`.

## Rollback

Обычный rollback — возврат к предыдущему known-good application image/commit. Автоматический destructive Alembic downgrade не является стандартной стратегией.

Если migration не backward-compatible, restore point и процедура восстановления должны быть протестированы до deploy. См. `OPERATIONS.md`.

## Secrets

Не хранить production `.env`, DB password, JWT/encryption/legal evidence keys, WB service secret, bank merchant data или backup passphrase в git/image/frontend/logs.

При наличии platform secret manager предпочтительна runtime injection вместо постоянного `.env.production` на host.

## Celery

Worker масштабируется отдельно с учётом WB rate limits и DB capacity. Beat в базовой topology должен быть ровно один; несколько Beat без leader-election создают дублирующиеся periodic tasks.

## Production validation

Container/systemd deploy сам по себе не означает beta/RC readiness. Обязательны:

- production-like core smoke;
- deploy/rollback drill;
- data-accuracy acceptance;
- external WB/Sber validation;
- operational monitoring;
- off-host backup/restore drill;
- legal/account-lifecycle gates согласно `RELEASE_ROADMAP.md`.
