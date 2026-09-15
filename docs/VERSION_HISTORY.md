# WB Insight — подробная история версий

Дата ревизии истории: 2026-09-15.

Этот документ фиксирует продуктовую историю WB Insight по фактически слитым изменениям в `main` и отдельно обозначает текущий release candidate ветки, если он ещё не слит.

Важно: версии до введения формальной release-policy 15 сентября 2026 года являются **ретроспективно реконструированными milestones**. Они описывают фактический уровень зрелости продукта после соответствующих merge и не утверждают, что в тот момент существовал Git tag. Канонические правила дальнейшего версионирования описаны в `docs/VERSIONING.md`, краткие release notes — в `CHANGELOG.md`.

## Как читать историю

Мы разделяем:

- **Git history** — отдельные технические commit и merge;
- **product version history** — законченные уровни зрелости продукта;
- **release stage** — alpha, beta, rc или stable, которая меняется только при выполнении заранее определённых gates.

Один продуктовый milestone может объединять несколько PR. Номер версии не является номером коммита.

---

## 0.1.0-alpha.1 — реконструкция проекта

**Период:** 2026-03-30  
**Mainline:** PR #1.  
**Статус:** ранний прототип.

### Что появилось

- восстановлен первый рабочий codebase;
- сформирована исходная структура backend/frontend;
- подготовлена база для последующей интеграции Wildberries.

PR #2 и #3 были закрыты без merge и в mainline-историю не входят.

### Почему 0.1

Первый воспроизводимый baseline, но ещё не продуктовый MVP.

---

## 0.2.0-alpha.1 — первая Unit Economy

**Период:** 2026-05-05  
**Mainline:** PR #4–#7.

### Что изменилось

- появились первые расчёты по WB reports;
- начал формироваться контур unit-экономики;
- несколько итераций уточнили расчёты и связку с отчётами WB.

### Почему 0.2

Проект перешёл от skeleton к первой самостоятельной полезной аналитической функции.

---

## 0.3.0-alpha.1 — ранняя синхронизация и реклама

**Период:** 2026-05-06  
**Mainline:** PR #8–#12.  
**Не входит:** PR #13 — закрыт без merge.

### Что изменилось

- исправлена работа sync при проблемном WB credential;
- появилась первая синхронизация рекламной статистики;
- добавлялся и дорабатывался backend/frontend рекламного раздела;
- исправлялись ошибки импорта advertising data.

### Почему 0.3

Появился второй самостоятельный аналитический контур и регулярная внешняя WB API integration.

---

## 0.4.0-alpha.1 — консолидация БД и требований

**Период:** 2026-05-07  
**Mainline:** PR #14.

### Что изменилось

- уточнены требования к БД;
- зафиксированы дополнительные требования к persistence/data structure;
- подготовлен переход к системному production-аудиту.

### Почему 0.4

Архитектурная точка перед большой переработкой P0–P24, а не публичный релиз.

---

## 0.5.0-alpha.1 — production safety и durable sync foundation

**Период:** 2026-09-14  
**Mainline:** P0–P4, PR #15–#19.

### P0 / PR #15 — Production Safety

- строгая модель access/refresh JWT;
- server-side refresh/logout;
- server-side RBAC control panel;
- защита super-admin invariants;
- marketplace credentials перестали возвращаться на frontend;
- тарифные лимиты WB-кабинетов проверяются backend-ом;
- fake billing ограничен development;
- audit logging без request body/секретов;
- CI baseline backend/frontend/PostgreSQL migrations.

### P1 / PR #16 — Account-scoped Sync

- `SyncJob` и `UserSyncState` привязаны к конкретному marketplace credential;
- scheduler/worker не смешивают кабинеты одного пользователя;
- ownership, marketplace, validity и tariff allowance проверяются перед sync;
- Alembic проверяется на чистом PostgreSQL.

### P2 / PR #17 — WB Transport Hardening

- Redis-coordinated rate limiting;
- bounded retries и `Retry-After`;
- typed auth/rate/API errors;
- credential не деактивируется из-за любого 4xx;
- deterministic cleanup HTTP/Redis resources.

### P3 / PR #18 — WB API Contracts

- актуализированы Finance, Stocks и Content contracts;
- безопасная pagination/cursor semantics;
- account-scoped canonical identities;
- normalized ingestion current WB payloads.

### P4 / PR #19 — Durable Resumable Jobs

- atomic claim через `FOR UPDATE SKIP LOCKED`;
- processing leases и crash recovery;
- bounded retry budget;
- durable page checkpoints;
- restart продолжает sync с подтверждённой страницы.

### Почему 0.5

Проект впервые получил production-oriented security и устойчивый ingestion core, но пользовательский scope ещё был неполным.

---

## 0.6.0-alpha.1 — operational WB facts

**Период:** 2026-09-14  
**Mainline:** P5–P7, PR #20–#22.

### P5 / PR #20 — Orders и Sales/Returns

- account-scoped orders и sales/returns facts;
- canonical identities;
- retention-aware initial sync;
- cursor по `lastChangeDate`;
- stale replay protection.

### P6 / PR #21 — Advertising

- актуальный Promotion API;
- campaign discovery и `fullstats v3`;
- batching и rolling refresh;
- account-scoped advertising facts;
- permission errors отделены от invalid credential.

### P7 / PR #22 — Sales Funnel

- daily product funnel facts;
- views, carts, orders, buyouts и conversions;
- rolling 7-day refresh;
- batching `nmIds`;
- typed feature-unavailable behavior.

### Почему 0.6

Система получила канонический operational/marketing fact layer вместо ранних отчётных assumptions.

---

## 0.7.0-alpha.1 — semantic layer и бизнес-вводы

**Период:** 2026-09-15  
**Mainline:** P8–P13, PR #23–#28.

### P8 / PR #23 — Unified Semantic Metrics

- единые определения метрик между аналитическими разделами;
- operational orders отделены от finance realization;
- advertising attribution отделена от общего количества заказов;
- исправлены comparison periods, Moscow-day boundaries и sync status semantics.

### P9 / PR #24 — Multi-account Dashboard

- единый `DashboardAccountScope`;
- безопасный selected/all account scope;
- SQL-level scoping основных разделов;
- общий frontend account selector.

### P10 / PR #25 — Unit Economy correctness

- исправлены runtime/alias mismatches;
- aggregate ratios считаются из числителей/знаменателей;
- фактические advertising расходы включены в unit economics;
- API contract синхронизирован с frontend.

### P11 / PR #26 — Monthly Revenue Plans

- persistent monthly targets;
- target по кабинету и месяцу;
- реальная длина календарного месяца;
- раздельные required revenue/day и orders/day;
- удалены выдуманные fallback targets.

### P12 / PR #27 — Paid Storage

- официальный task/status/download flow;
- chunks не более 8 дней;
- persisted task/checkpoint;
- rolling refresh.

### P13 / PR #28 — Historical COGS и Seller Expenses

- date-effective COGS history;
- manual expenses по account/SKU;
- новая закупочная цена не искажает историю;
- Main и Unit Economy используют одинаковую temporal semantics.

### Почему 0.7

Появился единый semantic/business layer поверх marketplace facts — основа замены исходной аналитической таблицы.

---

## 0.8.0-alpha.1 — feature-complete WB analytics alpha

**Период:** 2026-09-15  
**Mainline:** P14–P18, PR #29–#33.

### P14 / PR #29 — Dashboard UX Foundation

- единый спокойный UI аналитики;
- Overview, Unit Economy и Ads перестроены вокруг реальных данных;
- удалены demo/hardcoded KPI;
- исправлены period/filter semantics.

### P15 / PR #30 — Seller Inputs / Settings

- рабочий профиль продавца;
- workspace WB-кабинетов;
- ввод COGS с effective dates и CSV path;
- ручные расходы;
- единый settings design system.

### P16 / PR #31 — Inventory Risk / Replenishment

- спрос по 30 завершённым дням;
- stock cover;
- критический остаток;
- recommendation quantity;
- отдельный inventory dashboard.

### P17 / PR #32 — Price Monitoring

- durable current-price sync;
- история только фактических изменений;
- size-aware identity;
- price dashboard.

### P18 / PR #33 — Finance Reconciliation

- canonical finance summaries;
- current balance snapshot;
- reconciliation summary/detail;
- tolerance 2 копейки;
- durable finance sync.

### Почему 0.8

Пользовательский WB analytics scope уже близок к первому полному продукту, но production access, billing и release infrastructure ещё не закрыты.

---

## 0.9.0-alpha.1 — release-hardening baseline

**Период:** 2026-09-15  
**Mainline:** P19–P24, PR #34–#39.  
**Main commit после P24:** `ff0d278c32f0a770dc0cdbc0cf0ab9d98c2377ca`.

### P19 / PR #34 — WB Credential Compliance

- token type определяется по JWT `acc`;
- expiry берётся из реального `exp`;
- Personal/Test запрещены для cloud flow;
- Service token проверяется на service binding;
- официальный Bearer header.

### P20 / PR #35 — Marketplace Adapter Core

- общий `MarketplaceAdapter`;
- registry адаптеров;
- WB implementation скрыта за adapter contract;
- создан фундамент для будущего Ozon без дублирования scheduler/worker.

### P21 / PR #36 — Marketplace Credential Foundation

- `external_account_id`;
- nullable `expires_at`;
- seller identity отделена от encrypted secret;
- исправлены legacy credential regressions.

### P22 / PR #37 — WB Production Access-token Policy

- обязательные permissions: Контент, Аналитика, Цены и скидки, Статистика, Продвижение, Финансы;
- обязателен Read Only;
- Base/Service requests используют `X-Client-Secret`;
- production требует `WB_SERVICE_ID + WB_SERVICE_SECRET`;
- credential live-validates через WB `/ping` перед сохранением.

### P23 / PR #38 — Release Readiness baseline

- `/health/live`;
- `/health/ready` с PostgreSQL/Redis;
- README/SETUP приведены к фактическому продукту;
- создан Definition of Done;
- Ozon/AI/mobile выведены за scope WB Web v1.

### P24 / PR #39 — Sber Acquiring

- server-to-server registration/status verification;
- idempotency key;
- callback используется только как trigger;
- backend самостоятельно подтверждает deposited state;
- subscription связана с подтверждённым payment;
- duplicate callback/refresh не создаёт вторую подписку;
- sandbox/production separation.

### Почему 0.9.0-alpha.1

Функциональный WB scope сформирован, но ещё отсутствовали deployment/monitoring/backup/legal/session/release-smoke слои.

---

## 0.9.0-alpha.2 — version governance и production deployment baseline

**Период:** 2026-09-15  
**Mainline:** P25, PR #40.  
**Merge commit:** `8cad1f098ae63c813ed36aad2c462d196484153a`.

### Что изменилось

- root `VERSION` стал source of truth;
- frontend/FastAPI version приведены к одной схеме;
- runtime version доступна через health endpoints;
- формализованы SemVer и stage gates;
- добавлены production Docker images;
- same-origin nginx `/api` gateway;
- Compose topology: PostgreSQL, Redis, migration, API, worker, beat, frontend;
- production env contract без секретов;
- deployment/upgrade/rollback runbook;
- release-integrity CI проверяет version consistency, images и Compose.

### Почему всё ещё alpha

Deployment воспроизводим из repo, но operations, legal и финальный browser-session/release-smoke hardening ещё не закрыты.

---

## 0.9.0-alpha.3 — operations hardening

**Период:** 2026-09-15  
**Mainline:** P26, PR #41.  
**Merge commit:** `76ee8651298fff99b8bf6a11921dcbfbf0916c46`.

### Что изменилось

- super-admin operational snapshot;
- failed/stale sync и expired processing lease checks;
- marketplace credential expiry alerts;
- отдельный 30-day warning по ротации `WB_SERVICE_SECRET`;
- Redis minute-bucket HTTP/5xx telemetry;
- scheduled Celery operations monitor;
- deduplicated HTTPS alert webhook;
- encrypted PostgreSQL backup, checksum и retention;
- destructive restore guard;
- isolated restore drill;
- CI выполняет настоящий encrypted backup/restore roundtrip;
- зафиксированы RPO/RTO baseline и operations runbook;
- найден и закрыт production refresh-cookie regression: единая Secure/SameSite/Domain policy, `Path=/`, legacy GET refresh удалён.

### Почему всё ещё alpha

Operations code baseline готов, но legal/consent и persistent browser access-token ещё оставались code-side blockers. Реальные WB/Sber credentials, off-host backup, alert destination и production-like drills также остаются внешними/ops gates.

---

## 0.9.0-alpha.4 — versioned legal documents и consent evidence

**Период:** 2026-09-15  
**Рабочая ветка:** `codex/p27-legal-consent-foundation`.  
**Статус на момент этой записи:** кандидат P27; становится mainline milestone только после green CI и merge.

### Что реализовано в P27

- backend registry обязательных юридических документов;
- каждый документ имеет стабильный `code`, `version` и вычисляемый SHA-256;
- публичные `/legal/requirements/{context}` и `/legal/documents/{code}`;
- immutable `legal_consents` с `user_id`, кодом, точной версией, SHA-256, контекстом и UTC timestamp;
- IP/User-Agent не сохраняются открытым текстом, а фиксируются как HMAC evidence;
- отдельный production `LEGAL_EVIDENCE_HMAC_KEY` документирован;
- backend отвергает отсутствующее согласие, устаревшую версию и несовпадающий document hash;
- регистрация физлица/самозанятого требует `terms + privacy`;
- регистрация юрлица дополнительно требует `personal_data`;
- создание платного payment attempt требует `privacy + offer + refund_policy`;
- сохранение marketplace credential требует `privacy + credential_policy`;
- billing consent связывается с `payment_id`, credential consent — с credential ID;
- idempotent повтор Sber payment attempt не создаёт вторую пачку consent evidence;
- frontend получает актуальные document metadata с backend и отправляет точные `version + sha256`;
- созданы публичные legal pages и совместимые `/terms`/`/privacy` routes;
- добавлен reusable legal consent checklist;
- техническая архитектура описана в `docs/LEGAL_CONSENT.md`.

### Что намеренно не считается готовым

Встроенные тексты имеют версию `1.0-draft.1` и явно помечены как черновики. P27 доказывает **кто, когда и какую конкретную версию принял**, но не заменяет юридическую проверку содержания.

До RC требуется:

- утверждение текстов владельцем сервиса и юридическим специалистом;
- реквизиты оператора/продавца услуги;
- утверждённые правила возврата/отмены;
- утверждённая privacy/data processing модель;
- публикация новых non-draft версий без переписывания уже принятой версии;
- архив выпущенных текстов.

### Почему всё ещё alpha

После P27 остаётся code-side P28: access JWT должен уйти из persistent browser storage, а end-to-end release smoke должен стать формализованным и воспроизводимым. Кроме того, внешние production gates ещё не закрыты.

---

## Следующие запланированные версии

### 0.9.0-alpha.5 — P28 Browser Session Hardening / Release Smoke

Цель:

- access JWT только в памяти приложения;
- восстановление browser session через HttpOnly refresh cookie;
- отсутствие access token в `localStorage`/`sessionStorage`;
- формальный automated production-like release smoke.

### 0.9.0-beta.1

Допускается только после:

- feature freeze WB Web v1;
- закрытия всех code-side P0 blockers;
- green release commit;
- успешного production-like end-to-end smoke.

Beta не означает, что внешние WB/Sber/legal/operations условия уже обязательно закрыты, но продуктовый код и scope должны быть заморожены.

### 1.0.0-rc.1

Допускается только после закрытия внешних production blockers:

- реальные WB partner credentials и seller smoke;
- Sber production merchant credentials и payment smoke;
- production deployment/TLS;
- реальный alert destination/uptime/logging;
- off-host backup и production-like restore drill;
- юридические документы утверждены и опубликованы как non-draft;
- полный release smoke пройден.

### 1.0.0 — WB Insight Web v1 Stable

Первый публичный стабильный релиз для продавцов Wildberries. После stable breaking changes увеличивают MAJOR, backward-compatible feature releases — MINOR, исправления — PATCH.

---

## Что не должно менять release stage само по себе

Не повышаем стадию только из-за:

- количества commits;
- номера P-задачи;
- косметического merge;
- локально работающей функции без release validation;
- документации о будущем функционале.

Переход `alpha -> beta -> rc -> stable` происходит только после выполнения соответствующих gates.
