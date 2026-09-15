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

P25 добавляет:

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

### 4. Health, monitoring и alerts — P26

Уже есть:

- `GET /health/live` — liveness + deployed version;
- `GET /health/ready` — readiness PostgreSQL + Redis + deployed version.

До релиза нужны:

- error tracking;
- централизованные production logs;
- alert на 5xx/error rate;
- alert на failed/dead sync jobs;
- alert на длительное отсутствие успешной синхронизации кабинета;
- alert на срок действия `WB_SERVICE_SECRET` и seller tokens;
- uptime check `/health/ready`.

### 5. Backup / restore — P26 OPS BLOCKER

Нужно определить и проверить:

- ежедневный backup PostgreSQL;
- retention policy;
- шифрование backup;
- отдельное хранение backup;
- documented restore procedure;
- минимум один успешный restore drill до публичного запуска;
- RPO/RTO для первой версии.

### 6. Legal / privacy / consent — P27 PRODUCT + EXTERNAL BLOCKER

Перед продажами нужны утверждённые тексты и страницы:

- оферта/условия использования;
- политика конфиденциальности;
- согласие на обработку персональных данных;
- политика обработки/хранения marketplace credentials;
- реквизиты оператора сервиса;
- правила возвратов/отмены подписки;
- фиксация версии согласия и timestamp.

### 7. Browser session hardening + release smoke — P28

Frontend пока хранит access JWT в `localStorage`. Refresh token уже HttpOnly cookie. Целевое состояние до публичного релиза: короткоживущий access token в memory с восстановлением через HttpOnly refresh cookie.

Также нужен полный release smoke suite.

## Release stages

### Alpha — текущая стадия

`0.9.0-alpha.N` используется, пока закрываются P25–P28, environment validation и внешние WB/Sber blockers.

### Beta

`0.9.0-beta.1` допускается только после feature freeze WB Web v1, закрытия code-side P0 blockers и успешного production-like end-to-end smoke. Beta не назначается автоматически по количеству коммитов.

### Release Candidate

`1.0.0-rc.1` допускается только после настройки реальных WB/Sber credentials, production deployment/TLS, monitoring, backup/restore drill, legal/consent flow и полного release smoke.

### Stable

`1.0.0` — публичный стабильный WB Web v1.

## End-to-end release smoke suite

Нужен автоматизируемый или документированный smoke:

1. регистрация;
2. demo subscription;
3. подключение WB кабинета;
4. полный sync;
5. открытие всех dashboard sections;
6. ввод себестоимости и расходов;
7. создание плана;
8. создание реального платежа;
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
- [ ] error monitoring и critical alerts работают;
- [ ] backup и restore drill подтверждены;
- [ ] legal documents опубликованы и consent фиксируется;
- [ ] browser access-token hardening завершён;
- [ ] smoke suite пройдена на production-like environment;
- [ ] секреты/токены не присутствуют в git, frontend bundle или логах.

## Очерёдность закрытия

1. P22 — WB credential contract — **done**.
2. P23 — release readiness / health / documentation — **done**.
3. P24 — Sber acquiring code integration — **done; merchant onboarding остаётся внешним blocker**.
4. P25 — versioning + production container/deployment baseline — **done после green CI**.
5. P26 — monitoring, sync/token expiry alerts, backup/restore runbook.
6. P27 — legal routes + consent persistence.
7. P28 — browser access-token hardening + release smoke.
8. `0.9.0-beta.1` после feature freeze и production-like validation.
9. `1.0.0-rc.1` после закрытия external/ops blockers.
10. `1.0.0` — public stable WB Web v1.
11. Ozon adapter/products/orders/finance.
12. WB OAuth 2.0 onboarding after Catalog readiness.
