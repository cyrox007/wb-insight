# WB Insight — подробная история версий

Дата ревизии истории: 2026-09-15.

Этот документ фиксирует продуктовую историю WB Insight по фактически слитым изменениям в `main`.

Важно: до введения формальной release-policy версии ниже являются **ретроспективно реконструированными milestones**. Они описывают уровень зрелости продукта после соответствующих merge, но не утверждают, что в тот момент существовал Git tag с таким номером. Канонические правила дальнейшего версионирования описаны в `docs/VERSIONING.md`, краткие release notes — в `CHANGELOG.md`.

## Как читать историю

Мы разделяем две истории:

- **Git history** — каждый технический commit/merge;
- **product version history** — законченные уровни зрелости продукта.

Один продуктовый milestone может объединять несколько PR, если только вместе они дают осмысленное состояние продукта. Это позволяет не превращать номер версии в номер коммита и сохраняет смысл переходов `alpha -> beta -> rc -> stable`.

---

## 0.1.0-alpha.1 — реконструкция проекта

**Период:** 2026-03-30  
**Mainline:** PR #1  
**Статус:** ранний прототип / техническая реконструкция.

### Что появилось

- восстановлен первый рабочий кодовый baseline репозитория;
- сформирована исходная структура backend/frontend;
- подготовлена база для последующей синхронизации Wildberries.

### Что не вошло

PR #2 и #3 были закрыты без merge и поэтому не являются частью истории `main`.

### Почему версия 0.1

Это первый воспроизводимый mainline baseline, но ещё не продуктовый MVP.

---

## 0.2.0-alpha.1 — первая Unit Economy

**Период:** 2026-05-05  
**Mainline:** PR #4–#7.

### Что изменилось

- появились первые расчёты на основе WB reports;
- начал формироваться экран/контур unit-экономики;
- несколько итераций подряд уточняли расчётную модель и связку с отчётами WB.

### Ограничения этапа

- модель данных и API-контракты ещё не были приведены к production semantics;
- account isolation, durable sync, финальная безопасность и release-инфраструктура ещё отсутствовали.

### Почему версия 0.2

Проект перешёл от восстановленного skeleton к первой полезной аналитической функции.

---

## 0.3.0-alpha.1 — ранняя синхронизация и реклама

**Период:** 2026-05-06  
**Mainline:** PR #8–#12.  
**Не входит:** PR #13 — закрыт без merge.

### Что изменилось

- исправлена работа синхронизации при проблемном WB credential;
- добавлена первая синхронизация рекламной статистики;
- добавлялся и дорабатывался backend/frontend рекламного раздела;
- исправлялись ошибки импорта рекламных данных.

### Почему версия 0.3

Появился второй самостоятельный аналитический контур — реклама — и началась регулярная интеграция с внешним WB API.

---

## 0.4.0-alpha.1 — консолидация БД и требований

**Период:** 2026-05-07  
**Mainline:** PR #14.

### Что изменилось

- уточнены требования к БД;
- зафиксированы дополнительные notes по функционалу и структуре данных;
- подготовлен переход от раннего прототипа к системной переработке persistence/API слоя.

### Почему версия 0.4

Это не большой пользовательский релиз, а важная архитектурная точка перед production-аудитом и последующим P0–P24 hardening.

---

## 0.5.0-alpha.1 — production-safety и durable sync foundation

**Период:** 2026-09-14  
**Mainline:** P0–P4, PR #15–#19.

### P0 / PR #15 — production safety

- строгая модель access/refresh JWT;
- server-side refresh/logout;
- production fail-closed для security secrets;
- server-side RBAC control panel;
- защита ролей и super-admin invariants;
- marketplace credentials перестали возвращаться на frontend;
- тарифные лимиты WB-кабинетов начали проверяться backend-ом;
- fake billing ограничен dev-режимом;
- audit trail без request body/секретов;
- появился CI baseline backend/frontend/PostgreSQL migrations.

### P1 / PR #16 — account-scoped sync

- `SyncJob` и `UserSyncState` получили размерность конкретного marketplace credential;
- worker и scheduler перестали смешивать кабинеты одного пользователя;
- ownership, marketplace, credential validity и тариф проверяются перед sync;
- clean PostgreSQL + Alembic check стали частью CI.

### P2 / PR #17 — WB transport hardening

- Redis-coordinated rate limiting;
- bounded retries;
- `Retry-After` и shared cooldown;
- typed WB auth/rate/API errors;
- credential не деактивируется из-за любого 4xx;
- закрытие HTTP/Redis resources стало детерминированным.

### P3 / PR #18 — актуальные WB contracts

- обновлены Finance/Stocks/Content API contracts;
- добавлена безопасная pagination/cursor semantics;
- исправлены account-scoped canonical identities;
- ingestion начал писать normalized current API data вместо raw response assumptions.

### P4 / PR #19 — durable/resumable jobs

- atomic claim через `FOR UPDATE SKIP LOCKED`;
- processing lease и crash recovery;
- bounded retry budget;
- durable page checkpoints;
- restart продолжает sync с последней подтверждённой страницы.

### Почему версия 0.5

Это точка, где проект впервые получил production-oriented security и устойчивый ingestion core. Пользовательский набор функций ещё был неполным, поэтому стадия осталась alpha.

---

## 0.6.0-alpha.1 — operational WB facts

**Период:** 2026-09-14  
**Mainline:** P5–P7, PR #20–#22.

### P5 / PR #20 — Orders и Sales/Returns

- account-scoped operational orders;
- sales/returns facts;
- canonical `(token_id, srid)` и `(token_id, sale_id)` identities;
- retention-aware initial sync;
- cursor based on `lastChangeDate`;
- stale replay protection.

### P6 / PR #21 — Advertising

- актуальный Promotion API;
- campaign discovery и `fullstats v3`;
- campaign batching;
- rolling refresh attribution data;
- account-scoped ad facts;
- permission error отделён от invalid credential.

### P7 / PR #22 — Sales Funnel

- daily product funnel facts;
- views/carts/orders/buyouts/conversions;
- rolling 7-day refresh;
- batch по `nmIds`;
- typed feature-unavailable behavior.

### Почему версия 0.6

Система перестала быть только Finance/Unit Economy prototype и получила канонический operational/marketing fact layer.

---

## 0.7.0-alpha.1 — semantic layer и бизнес-вводы

**Период:** 2026-09-15  
**Mainline:** P8–P13, PR #23–#28.

### P8 / PR #23 — Semantic Metrics

- единые определения метрик между Main/Ads;
- operational orders отделены от Finance realization;
- advertising attribution отделена от общего заказа;
- исправлены предыдущие периоды и Moscow-day boundaries;
- sync-state semantics перестали давать ложный вечный `syncing`.

### P9 / PR #24 — Multi-account Dashboard

- единый `DashboardAccountScope`;
- режим всех тарифно разрешённых кабинетов;
- безопасный выбор одного кабинета;
- SQL-level scope для основных аналитических разделов;
- общий frontend selector кабинета.

### P10 / PR #25 — Unit Economy correctness

- устранены obsolete aliases и runtime mismatches;
- ratios считаются из агрегированных числителей/знаменателей;
- фактические рекламные расходы входят в Unit Economy;
- API output синхронизирован с frontend contract.

### P11 / PR #26 — Revenue Plans

- persistent monthly revenue target;
- target отдельно по кабинету/месяцу;
- реальная длина календарного месяца;
- разделены required revenue/day и required orders/day;
- удалены выдуманные fallback-планы.

### P12 / PR #27 — Paid Storage

- официальный WB task/status/download flow;
- <=8-day chunks;
- persisted task ID/checkpoint;
- rolling refresh с заменой завершённого диапазона.

### P13 / PR #28 — COGS history и seller expenses

- date-effective себестоимость;
- account/SKU manual expenses;
- история не искажается при новой закупочной цене;
- Main и Unit Economy используют одинаковую temporal COGS semantics.

### Почему версия 0.7

Проект получил единый semantic/business layer поверх сырых marketplace facts и начал заменять ручные листы исходной аналитической таблицы.

---

## 0.8.0-alpha.1 — feature-complete WB analytics alpha

**Период:** 2026-09-15  
**Mainline:** P14–P18, PR #29–#33.

### P14 / PR #29 — UI/UX foundation

- единый спокойный интерфейс аналитики;
- Overview перестроен вокруг результата/отклонения/причин;
- удалены demo/hardcoded KPI;
- исправлена передача периода;
- Unit Economy и Ads приведены к рабочей информационной архитектуре.

### P15 / PR #30 — Seller Settings

- реальный профиль продавца;
- workspace подключённых WB-кабинетов;
- UI ввода себестоимости;
- CSV secondary path;
- CRUD ручных расходов;
- налоговая ставка и timezone валидируются backend-ом.

### P16 / PR #31 — Inventory/Replenishment

- спрос за 30 завершённых дней;
- stock cover;
- порог критичности 14 дней;
- целевой запас 30 дней;
- рекомендация поставки без отрицательных значений;
- позиции без спроса отделены от нормального stock coverage.

### P17 / PR #32 — Price Monitoring

- read-only current price snapshot;
- история только реальных изменений;
- size-aware identity;
- price dashboard.

### P18 / PR #33 — Finance Reconciliation

- canonical finance report summary;
- current WB balance;
- summary/detail reconciliation;
- tolerance 2 копейки;
- `bankPaymentSum` сохраняется как канонический итог WB, а не восстанавливается собственной формулой.

### Почему версия 0.8

К этому моменту пользовательский WB analytics scope уже близок к полному первому продукту: обзор, Unit Economy, реклама, финансы, остатки, цены, планы, COGS и расходы. Но production access, billing и эксплуатационный контур ещё не готовы.

---

## 0.9.0-alpha.1 — release-hardening baseline

**Период:** 2026-09-15  
**Mainline:** P19–P24, PR #34–#39.  
**Main commit после P24:** `ff0d278c32f0a770dc0cdbc0cf0ab9d98c2377ca`.

### P19 / PR #34 — WB credential compliance

- backend сам определяет token type из JWT `acc`;
- expiry берётся из реального `exp`;
- Personal/Test не допускаются в cloud production flow;
- Service token проверяется на service binding;
- официальный Bearer header.

### P20 / PR #35 — Marketplace Adapter Core

- общий `MarketplaceAdapter`;
- registry адаптеров;
- WB-specific handlers спрятаны за adapter contract;
- будущий Ozon сможет использовать тот же scheduler/worker.

### P21 / PR #36 — Marketplace Credential Foundation

- `external_account_id`;
- nullable `expires_at` для non-expiring provider keys;
- исправлена WB enum semantics;
- устранён legacy endpoint regression после предыдущего token API refactor.

### P22 / PR #37 — WB production token policy

- обязательные категории: Контент, Аналитика, Цены и скидки, Статистика, Продвижение, Финансы;
- обязателен Read Only;
- Base/Service requests подписываются `X-Client-Secret`;
- production требует `WB_SERVICE_ID + WB_SERVICE_SECRET`;
- credential live-validates against WB `/ping` перед сохранением.

### P23 / PR #38 — Release Readiness

- `/health/live`;
- `/health/ready` с PostgreSQL + Redis;
- README/SETUP приведены к фактическому продукту;
- создан release Definition of Done;
- Ozon/AI/mobile выведены за scope WB Web v1.

### P24 / PR #39 — Sber Acquiring

- server-to-server registration;
- idempotency key;
- provider `orderId/formUrl`;
- callback только триггер;
- backend самостоятельно подтверждает payment state;
- subscription привязана к подтверждённому payment;
- duplicate callback/refresh не создаёт вторую подписку;
- sandbox/prod separation.

### Почему версия 0.9.0-alpha.1

Функциональный WB scope уже сформирован, но продукт ещё нельзя честно назвать beta: отсутствовали воспроизводимый production deployment, monitoring, backup/restore, legal/consent и финальный session/release smoke hardening.

---

## 0.9.0-alpha.2 — version governance и production deployment baseline

**Период:** 2026-09-15  
**Mainline:** P25, PR #40.  
**Merge commit:** `8cad1f098ae63c813ed36aad2c462d196484153a`.

### Что изменилось

- введён root `VERSION` как source of truth;
- frontend и FastAPI перестали объявлять разные версии;
- runtime version доступна через health endpoints;
- зафиксированы SemVer и stage gates;
- появились production Docker images backend/frontend;
- same-origin nginx gateway;
- production Compose topology: PostgreSQL, Redis, migration job, API, worker, единственный beat, frontend;
- production env contract без реальных секретов;
- deployment/upgrade/rollback runbook;
- CI проверяет version consistency, Docker builds и Compose model.

### Почему всё ещё alpha

Production deployment теперь воспроизводим из репозитория, но monitoring/backup, legal consent, browser session hardening и внешние WB/Sber production smoke ещё не закрыты.

---

## 0.9.0-alpha.3 — P26 Operations hardening

**Статус:** в разработке на `codex/p26-operations-monitoring-backup`.

Планируемое содержание milestone:

- operational snapshot для super-admin;
- monitoring failed/stale sync jobs и processing leases;
- alerts по истекающим marketplace credentials;
- контроль срока ротации `WB_SERVICE_SECRET`;
- HTTP 5xx rate telemetry;
- scheduled Celery operations check;
- deduplicated alert webhook;
- encrypted PostgreSQL backup + checksum + retention;
- guarded restore;
- isolated restore drill;
- operational runbook и CI для release assets.

Версия станет канонической только после green CI и merge P26 в `main`.

---

## Следующие запланированные версии

### 0.9.0-alpha.4 — P27 Legal / Consent

Цель: публичные legal routes, versioned consent и фиксация согласия пользователя при необходимых действиях.

### 0.9.0-alpha.5 — P28 Session hardening / Release smoke

Цель: убрать browser access JWT из persistent storage, восстановление session через HttpOnly refresh и формальный end-to-end release smoke.

### 0.9.0-beta.1

Допускается только после закрытия code-side P0 blockers и успешного production-like end-to-end smoke. На beta feature scope WB Web v1 замораживается.

### 1.0.0-rc.1

Допускается только после закрытия внешних production blockers:

- реальные WB partner credentials и seller smoke;
- Sber production merchant credentials и payment smoke;
- monitoring/alerts включены;
- backup restore drill подтверждён;
- legal documents опубликованы;
- HTTPS/domain/secrets настроены;
- полный release smoke пройден.

### 1.0.0 — WB Insight Web v1 Stable

Первый публичный стабильный релиз для продавцов Wildberries. После него breaking changes требуют увеличения MAJOR, backward-compatible feature releases — MINOR, fixes — PATCH.

---

## Что не должно менять версию само по себе

Не повышаем стадию только из-за:

- большого количества commit;
- номера P-задачи;
- косметического merge;
- наличия локально работающей функции без release validation;
- документации о будущем функционале.

Версия меняется, когда изменилось **фактическое состояние продукта**, а переход стадии (`alpha -> beta -> rc -> stable`) — только когда выполнены соответствующие release gates.
