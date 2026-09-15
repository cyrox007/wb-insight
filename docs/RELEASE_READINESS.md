# WB Insight — Release Readiness

Дата ревизии: 2026-09-15.

## Целевой первый релиз

Первый публичный релиз фиксируем как **WB Insight Web v1 для продавцов Wildberries**:

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

Получить реквизиты можно до публикации в Каталоге через `business-solutions@rwb.ru`. Production backend намеренно fail-closed без них.

Подробности: `docs/WB_ACCESS_TOKEN_REQUIREMENTS.md`.

### 2. Реальный acquiring — CODE + EXTERNAL BLOCKER

Статус: **не готово**.

Сейчас production billing намеренно отвечает `BILLING_NOT_CONFIGURED`. Fake provider разрешён только в development.

Для релиза нужно:

- договор/merchant credentials Сбер acquiring;
- sandbox/test credentials;
- production credentials;
- server-to-server создание платежа;
- redirect/payment URL;
- server-side проверка статуса платежа;
- подписанный/проверенный callback или webhook;
- idempotency обработки callback;
- активация/смена подписки только после подтверждённого `SUCCEEDED`;
- корректная обработка failed/cancelled/expired;
- журнал provider events без хранения чувствительных платёжных данных.

### 3. Production deployment — CODE/OPS BLOCKER

Статус: **не готово**.

В репозитории нет воспроизводимого production deployment. Нужны:

- контейнер backend;
- контейнер frontend/static build;
- PostgreSQL и Redis как managed services либо документированная эксплуатационная схема;
- отдельные Celery worker и scheduler/beat процессы;
- reverse proxy/TLS termination;
- автоматический `alembic upgrade head` как контролируемый release step;
- environment/secret injection без `.env` в образе;
- rollback runbook.

### 4. Health, monitoring и alerts — IN PROGRESS

P23 добавляет:

- `GET /health/live` — liveness без внешних зависимостей;
- `GET /health/ready` — readiness PostgreSQL + Redis.

До релиза ещё нужны:

- error tracking (например Sentry или аналог);
- централизованные production logs;
- alert на 5xx/error rate;
- alert на failed/dead sync jobs;
- alert на длительное отсутствие успешной синхронизации кабинета;
- alert на срок действия `WB_SERVICE_SECRET` и seller tokens;
- uptime check `/health/ready`.

### 5. Backup / restore — OPS BLOCKER

Статус: **не готово**.

Нужно определить и проверить:

- ежедневный backup PostgreSQL;
- retention policy;
- шифрование backup;
- отдельное хранение backup;
- documented restore procedure;
- минимум один успешный restore drill до публичного запуска;
- RPO/RTO для первой версии.

### 6. Legal / privacy / consent — PRODUCT + EXTERNAL BLOCKER

Статус: **не готово**.

В публичном frontend сейчас нет отдельных legal routes. Перед продажами нужны утверждённые владельцем/юристом тексты и страницы:

- оферта/условия использования;
- политика конфиденциальности;
- согласие на обработку персональных данных;
- политика обработки/хранения marketplace credentials;
- реквизиты оператора сервиса;
- правила возвратов/отмены подписки;
- согласие с документами при регистрации и/или оплате с версией документа и timestamp.

### 7. Production documentation — CODE BLOCKER

Статус: **не готово**.

`README.md` и `SETUP.md` содержат устаревшие утверждения и старую ручную схему БД. До релиза:

- README должен описывать только реально существующий функционал;
- убрать утверждения, что AI/mobile уже реализованы;
- обновить WB access-token contract;
- `SETUP.md` должен использовать Alembic как единственный source of truth схемы;
- описать обязательные production env vars и startup order;
- описать worker/scheduler и smoke checks.

## P1 — важно сразу после базового release hardening

### Access token в browser storage

Frontend сейчас хранит access JWT в `localStorage`. Refresh token уже защищён HttpOnly cookie, но access token остаётся доступен JavaScript при XSS.

Целевое состояние: короткоживущий access token только в memory, восстановление сессии через HttpOnly refresh cookie при загрузке приложения. Это нужно закрыть до широкого масштабирования; желательно до публичного релиза.

### End-to-end release smoke suite

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

После публикации в Каталоге OAuth 2.0 стоит сделать основным onboarding flow. Он уменьшит количество ручных действий продавца и риск ошибок при выборе категорий.

### AI / mobile

AI-аналитик, прогнозы и native mobile apps не должны фигурировать как доступные функции, пока соответствующие production features не реализованы и не покрыты release checks.

## Release Definition of Done

Публичный WB Web v1 можно выпускать, когда одновременно выполнено:

- [ ] `main` green: backend tests, frontend build, Alembic check;
- [ ] получены и установлены WB partner credentials;
- [ ] Base/Service token smoke проходит на реальном seller account;
- [ ] все sync entities проходят end-to-end без необъяснённых 401/403;
- [ ] подключён реальный Sber acquiring;
- [ ] payment success подтверждается только server-side;
- [ ] production deployment воспроизводим из репозитория;
- [ ] HTTPS и production CORS настроены;
- [ ] `/health/live` и `/health/ready` используются инфраструктурой;
- [ ] error monitoring и critical alerts работают;
- [ ] backup и restore drill подтверждены;
- [ ] legal documents опубликованы и consent фиксируется;
- [ ] README/SETUP соответствуют фактическому продукту;
- [ ] smoke suite пройдена на production-like environment;
- [ ] секреты/токены не присутствуют в git, frontend bundle или логах.

## Очерёдность закрытия

1. P22 — WB credential contract — **done**.
2. P23 — release readiness / health / documentation — **in progress**.
3. P24 — Sber acquiring production integration.
4. P25 — production container/deployment baseline.
5. P26 — monitoring, sync/token expiry alerts, backup runbook.
6. P27 — legal routes + consent persistence.
7. P28 — browser access-token hardening + release smoke.
8. WB Web v1 release candidate.
9. Ozon adapter/products/orders/finance.
10. WB OAuth 2.0 onboarding after Catalog readiness.
