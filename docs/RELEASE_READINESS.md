# WB Insight — Release Readiness

Дата ревизии: 2026-09-15.

Текущая release-линия: **`0.9.0-alpha.N`**. Правила переходов: `docs/VERSIONING.md`.

## Целевой первый релиз

Первый публичный стабильный релиз фиксируем как **WB Insight Web v1 / `1.0.0` для продавцов Wildberries**:

- регистрация и безопасная сессия;
- подключение одного или нескольких WB-кабинетов в рамках тарифа;
- автоматическая синхронизация официального WB API;
- обзор KPI, финансы, остатки, цены, реклама, unit-экономика;
- себестоимость, ручные расходы и план выручки;
- тарифы и реальная оплата;
- production deployment, мониторинг и восстановление.

Ozon, AI-аналитик и мобильные приложения не являются блокерами WB Web v1. Они идут следующими релизными этапами.

## P0 — блокеры публичного релиза

### 1. Wildberries partner credentials — EXTERNAL BLOCKER

Статус кода: **готово после P22**.

Для production нужны собственные:

- `WB_SERVICE_ID`;
- `WB_SERVICE_SECRET`;
- лимиты API, настроенные WB для сервиса;
- минимум один реальный seller account для pre-release smoke test.

Production backend намеренно fail-closed без них.

Подробности: `docs/WB_ACCESS_TOKEN_REQUIREMENTS.md`.

### 2. Реальный acquiring — EXTERNAL/SMOKE BLOCKER

Статус кода: **реализовано в P24**.

Sber acquiring flow включает server-to-server регистрацию, server-side status verification, idempotency, callback-as-trigger semantics и активацию подписки только после подтверждённого deposited state.

До release всё ещё нужны внешние действия:

- договор/merchant account Сбер internet acquiring;
- sandbox/test credentials;
- production credentials и production gateway URL;
- HTTPS return/fail/callback URLs;
- sandbox smoke: success / decline / cancel / retry / duplicate callback;
- минимальный production payment smoke и сверка в merchant back office.

Подробности: `docs/SBER_ACQUIRING.md`.

### 3. Production deployment — CODE BASELINE READY IN P25 / OPS VALIDATION REMAINS

P25 добавил:

- production Docker image backend;
- production multi-stage frontend/nginx image;
- отдельные API / Celery worker / Celery beat процессы;
- one-shot `alembic upgrade head` как release step;
- PostgreSQL/Redis container baseline с health checks;
- same-origin API gateway;
- `.env.production.example` без реальных секретов;
- release-integrity CI с Docker builds и Compose validation;
- deploy/upgrade/rollback runbook.

До RC остаются environment-specific действия:

- выбрать production host/cluster;
- настроить DNS и TLS termination;
- заменить bundled PostgreSQL/Redis managed services при необходимости;
- проверить deploy/rollback на production-like environment.

Подробности: `docs/PRODUCTION_DEPLOYMENT.md`.

### 4. Health, monitoring и alerts — CODE BASELINE READY IN P26 / OPS ACTIVATION REMAINS

P26 добавил:

- `GET /health/live` — liveness + deployed version;
- `GET /health/ready` — readiness PostgreSQL + Redis + deployed version;
- super-admin `GET /control-panel/operations/health`;
- aggregated checks failed sync jobs, expired processing leases и stale sync states;
- alerts по expired/expiring marketplace credentials;
- отдельный 30-day rotation warning для `WB_SERVICE_SECRET`;
- Redis minute-bucket HTTP/5xx telemetry без path/body/PII;
- периодический Celery operations monitor;
- deduplicated HTTPS webhook для агрегированных operational alerts.

До RC остаются environment-specific действия:

- подключить реальный alert destination и проверить доставку;
- подключить внешний uptime monitor к `/health/ready`;
- направить structured application logs в централизованное хранилище;
- определить/подключить provider для error tracking, если он используется в production;
- проверить alert thresholds на production-like traffic.

Подробности: `docs/OPERATIONS.md`.

### 5. Backup / restore — CODE BASELINE READY IN P26 / REAL DRILL REMAINS

P26 добавил:

- encrypted `pg_dump` backup;
- AES-256-CBC + PBKDF2;
- SHA-256 integrity checksum;
- retention policy;
- удаление plaintext dump после шифрования;
- destructive restore guard `RESTORE_CONFIRM=YES`;
- isolated restore drill в отдельную временную БД;
- проверку `alembic_version` и public tables;
- CI roundtrip: создать backup -> расшифровать/восстановить -> проверить БД;
- стартовые targets: RPO <=24h, RTO <=4h, retention >=14 дней.

До RC нужны реальные эксплуатационные доказательства:

- включить ежедневный backup schedule;
- настроить off-host/object storage для encrypted artifacts;
- выполнить restore drill на реальном production-like backup;
- замерить фактические RPO/RTO;
- задокументировать результат drill.

Подробности: `docs/OPERATIONS.md`.

### 6. Legal / privacy / consent — CODE BASELINE READY IN P27 / LEGAL APPROVAL REMAINS

P27 закрывает технический контур:

- backend является source of truth для текущей версии каждого обязательного документа;
- публичные `/legal/requirements/{context}` и `/legal/documents/{code}`;
- immutable `legal_consents` с user/document/version/SHA-256/context/timestamp;
- IP и User-Agent сохраняются только как HMAC evidence, без исходного значения;
- backend отклоняет отсутствующую, устаревшую или несовпадающую по SHA-256 версию согласия;
- регистрация требует `terms + privacy`, для юрлица дополнительно `personal_data`;
- платный payment attempt требует `privacy + offer + refund_policy`;
- подключение marketplace credential требует `privacy + credential_policy`;
- frontend получает версии документов с backend непосредственно перед действием.

До RC остаётся обязательный внешний legal review:

- утвердить окончательное Пользовательское соглашение/оферту;
- утвердить Политику конфиденциальности и согласие на обработку персональных данных;
- утвердить правила обработки marketplace credentials;
- заполнить реквизиты оператора/продавца услуги;
- утвердить правила отмены подписки и возвратов;
- заменить `1.0-draft.1` на утверждённые версии без изменения уже принятой версии «на месте»;
- настроить отдельный `LEGAL_EVIDENCE_HMAC_KEY` в production;
- сохранить неизменяемый архив выпущенных юридических текстов.

Пока встроенные документы имеют статус `draft`, продукт **не может** перейти в `1.0.0-rc.N`.

Подробности: `docs/LEGAL_CONSENT.md`.

### 7. Browser session hardening + release smoke — P28

Frontend пока хранит access JWT в `localStorage`. Refresh token уже HttpOnly cookie. Целевое состояние до публичного релиза: короткоживущий access token в memory с восстановлением через HttpOnly refresh cookie.

Также нужен полный release smoke suite.

## Release stages

### Alpha — текущая стадия

`0.9.0-alpha.N` используется, пока закрываются P27–P28, environment validation и внешние WB/Sber/legal blockers.

### Beta

`0.9.0-beta.1` допускается только после feature freeze WB Web v1, закрытия code-side P0 blockers и успешного production-like end-to-end smoke. Beta не назначается автоматически по количеству коммитов.

### Release Candidate

`1.0.0-rc.1` допускается только после настройки реальных WB/Sber credentials, production deployment/TLS, monitoring, backup/restore drill, утверждения legal documents/consent flow и полного release smoke.

### Stable

`1.0.0` — публичный стабильный WB Web v1.

## End-to-end release smoke suite

Нужен автоматизируемый или документированный smoke:

1. регистрация с фиксацией актуальных legal consent;
2. demo subscription;
3. подключение WB кабинета с credential consent;
4. полный sync;
5. открытие всех dashboard sections;
6. ввод себестоимости и расходов;
7. создание плана;
8. создание реального платежа с billing consent;
9. callback/status confirmation;
10. активация платного тарифа;
11. logout/login/refresh session;
12. удаление WB кабинета.

## Не блокирует WB Web v1

### Ozon

Marketplace adapter foundation уже создана. Ozon подключается после стабилизации WB v1: `Client-Id + Api-Key`, затем products/orders/finance через общий adapter layer.

### Wildberries OAuth 2.0

После публикации в Каталоге OAuth 2.0 стоит сделать основным onboarding flow.

### AI / mobile

AI-аналитик, прогнозы и native mobile apps не должны фигурировать как доступные функции, пока соответствующие production features не реализованы и не покрыты release checks.

## Release Definition of Done

Публичный WB Web v1 можно выпускать, когда одновременно выполнено:

- [ ] release commit green: backend tests, frontend build, Alembic check, release-integrity;
- [ ] получены и установлены WB partner credentials;
- [ ] Base/Service token smoke проходит на реальном seller account;
- [ ] все sync entities проходят end-to-end без необъяснённых 401/403;
- [ ] получены production merchant credentials Сбера;
- [ ] Sber sandbox + production smoke подтверждены;
- [x] payment success в коде подтверждается только server-side;
- [x] production deployment baseline воспроизводим из репозитория;
- [ ] production-like deploy/rollback проверен;
- [ ] HTTPS и production CORS настроены;
- [ ] `/health/live` и `/health/ready` используются инфраструктурой;
- [x] operational monitoring/alerting code baseline реализован;
- [ ] внешний alerting/uptime/logging реально подключён и проверен;
- [x] encrypted backup/restore code baseline и CI roundtrip реализованы;
- [ ] production-like restore drill и off-host backup подтверждены;
- [x] versioned legal/consent code baseline реализован;
- [ ] юридические тексты утверждены и опубликованы как non-draft версии;
- [ ] отдельный `LEGAL_EVIDENCE_HMAC_KEY` настроен в production;
- [ ] browser access-token hardening завершён;
- [ ] smoke suite пройдена на production-like environment;
- [ ] секреты/токены не присутствуют в git, frontend bundle или логах.

## Очерёдность закрытия

1. P22 — WB credential contract — **done**.
2. P23 — release readiness / health / documentation — **done**.
3. P24 — Sber acquiring code integration — **done; merchant onboarding остаётся внешним blocker**.
4. P25 — versioning + production container/deployment baseline — **done**.
5. P26 — monitoring, alerts, backup/restore baseline — **done; `0.9.0-alpha.3`**.
6. P27 — legal routes + versioned consent persistence — **candidate `0.9.0-alpha.4`; legal approval остаётся внешним blocker**.
7. P28 — browser access-token hardening + release smoke.
8. `0.9.0-beta.1` после feature freeze и production-like validation.
9. `1.0.0-rc.1` после закрытия external/ops/legal blockers.
10. `1.0.0` — public stable WB Web v1.
11. Ozon adapter/products/orders/finance.
12. WB OAuth 2.0 onboarding after Catalog readiness.
