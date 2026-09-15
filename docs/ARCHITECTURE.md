# WB Insight — архитектура

## Общая схема

WB Insight разделён на browser frontend, FastAPI backend, PostgreSQL, Redis и фоновые Celery процессы.

```text
Browser
  |
  | HTTPS / same-origin
  v
nginx frontend gateway
  |-------------------- static Vue bundle
  |
  +--> FastAPI backend
          |
          +--> PostgreSQL
          +--> Redis
          +--> Wildberries APIs
          +--> Sber acquiring (when enabled)

Celery Beat --> Redis/Celery --> Celery Worker --> PostgreSQL / WB APIs
```

## Frontend

Стек: Vue 3 + Pinia + Vue Router + Axios + Vite.

Frontend отвечает за:

- навигацию и UI state;
- фильтры периода/кабинета;
- ввод данных продавца;
- визуализацию backend metrics;
- browser session orchestration.

Frontend **не является source of truth для бизнес-формул и прав доступа**.

Access JWT хранится только в памяти. Refresh session живёт в HttpOnly cookie. После reload frontend выполняет cookie-based refresh и получает новый access token + безопасный user snapshot.

## Backend

Стек: Python 3.12 + FastAPI + SQLAlchemy 2 async + PostgreSQL.

Backend отвечает за:

- auth/session/RBAC;
- legal consent validation;
- marketplace credentials;
- тарифные ограничения;
- синхронизацию и canonical facts;
- бизнес-расчёты и semantic metrics;
- billing;
- admin/control panel;
- health/operations endpoints.

## База данных

PostgreSQL — основное durable storage.

Ключевые типы данных:

- users/roles;
- subscriptions/tariffs/payments/payment events;
- marketplace credentials;
- sync jobs/checkpoints/states;
- WB operational facts;
- advertising/funnel/storage/finance facts;
- product/price/inventory facts;
- historical COGS;
- manual seller expenses;
- revenue plans;
- legal consent evidence.

Schema evolution выполняется только Alembic migrations.

## Redis

Redis используется для:

- Celery broker/coordination;
- rate-limit coordination;
- краткоживущей operations telemetry;
- dedupe operational alerts.

Redis не является каноническим хранилищем финансовых/аналитических фактов.

## Celery

### Worker

Выполняет длительные и периодические задачи: sync, retry/recovery, operations monitor и другие фоновые процессы.

### Beat

Планирует periodic jobs. В стандартной topology разрешён один Beat instance.

## Marketplace abstraction

Оркестрация отделена от конкретного marketplace через `MarketplaceAdapter`/registry approach. Wildberries — первая реализация. Ozon находится за пределами `1.0.0`.

Каждая синхронизация account-scoped: данные всегда привязаны к конкретному marketplace credential/account и не должны смешиваться между кабинетами пользователя.

## Durable sync

Sync jobs используют:

- persistent job state;
- lease processing;
- bounded retries;
- checkpoints;
- crash recovery;
- `FOR UPDATE SKIP LOCKED` для безопасного конкурентного claim.

Transport layer централизует rate limits, retry/backoff и typed external API errors.

## Поток WB данных

1. Пользователь добавляет допустимый seller credential.
2. Backend декодирует metadata JWT, проверяет тип/expiry/permissions/read-only/service binding.
3. Выполняется live validation WB.
4. Secret сохраняется только в encrypted form.
5. Scheduler создаёт account-scoped sync work.
6. Worker получает данные официальных WB APIs.
7. Payload нормализуется в canonical facts.
8. Semantic/business layer агрегирует факты для dashboards.
9. Frontend получает только необходимые response models.

## Финансовый слой

Раздел Finance/Reconciliation опирается на финансовые факты WB и отделяется от operational orders/sales. Это важно: заказ, выкуп, реализация и выплата — разные бизнес-события и не должны смешиваться одной датой или одним источником.

COGS хранится с effective date, поэтому изменение закупочной цены не переписывает историю. Manual expenses также входят в прибыль согласно своему периоду/account/SKU.

## Billing

Payment attempt создаётся backend-ом. Redirect/callback не является доказательством оплаты. Backend повторно получает status у Сбера и активирует subscription только после подтверждённого deposited state. Idempotency и связь payment/subscription защищают от повторной активации.

## Legal consent

Текущие версии legal documents задаются backend registry. При критичных действиях frontend передаёт точную принятую версию, а backend проверяет code/version/SHA-256 и записывает append-only evidence. UI checkbox сам по себе не является enforcement.

## Production topology

`compose.production.yml` содержит:

- PostgreSQL;
- Redis;
- one-shot migration container;
- backend API;
- Celery worker;
- Celery Beat;
- frontend/nginx.

Для зрелого production PostgreSQL/Redis могут быть заменены managed services без изменения логической архитектуры.

## Observability

- `/health/live` — process liveness;
- `/health/ready` — DB/Redis readiness;
- super-admin operations snapshot;
- HTTP/5xx minute-bucket telemetry;
- stale/failed sync checks;
- credential/service-secret expiry checks;
- deduplicated operational alert webhook.

## Архитектурные инварианты

- бизнес-формулы находятся server-side;
- tenant/account scope проверяется backend-ом;
- marketplace secret не возвращается frontend-у;
- access JWT не сохраняется persistent browser storage;
- payment activation только после server-side provider verification;
- schema меняется только миграциями;
- historical inputs не переписывают прошлые периоды;
- внешняя ошибка не должна автоматически означать invalid credential;
- release stage повышается только после evidence, а не после количества commits.
