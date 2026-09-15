# WB Insight — подробная история версий

Дата ревизии: 15 сентября 2026 года.

Этот документ фиксирует продуктовую историю WB Insight по фактически слитым изменениям в `main` и отдельно обозначает текущую release-кандидат ветку, если она ещё не слита.

До введения формальной release-policy 15 сентября 2026 года номера версий ниже являются **ретроспективно реконструированными milestones**. Они описывают фактический уровень зрелости продукта после соответствующих merge и не означают, что на тот момент существовал Git tag. Канонические правила дальнейшего версионирования находятся в `docs/VERSIONING.md`, краткие release notes — в `CHANGELOG.md`.

## Как читать историю

Мы разделяем три уровня:

- **Git history** — отдельные технические commits и merge;
- **product version history** — законченные уровни зрелости продукта;
- **release stage** — `alpha`, `beta`, `rc`, `stable`, меняющаяся только после выполнения release gates.

Один продуктовый milestone может объединять несколько PR. Номер версии не является номером коммита.

---

## 0.1.0-alpha.1 — реконструкция проекта

**Период:** 30 марта 2026 года  
**Mainline:** PR #1  
**Стадия:** ранний прототип.

Что появилось:

- восстановлен первый рабочий codebase;
- сформирована исходная структура backend/frontend;
- подготовлена база для последующей интеграции Wildberries.

PR #2 и #3 были закрыты без merge и в mainline-историю не входят.

**Почему 0.1:** первый воспроизводимый baseline, но ещё не продуктовый MVP.

---

## 0.2.0-alpha.1 — первая Unit Economy

**Период:** 5 мая 2026 года  
**Mainline:** PR #4–#7.

Что изменилось:

- появились первые расчёты по WB reports;
- начал формироваться контур unit-экономики;
- несколько итераций уточнили расчёты и связку с отчётами WB.

**Почему 0.2:** проект перешёл от skeleton к первой самостоятельной полезной аналитической функции.

---

## 0.3.0-alpha.1 — ранняя синхронизация и реклама

**Период:** 6 мая 2026 года  
**Mainline:** PR #8–#12.  
**Не входит:** PR #13 — закрыт без merge.

Что изменилось:

- исправлена работа sync при проблемном WB credential;
- появилась первая синхронизация рекламной статистики;
- добавлялся и дорабатывался backend/frontend рекламного раздела;
- исправлялись ошибки импорта advertising data.

**Почему 0.3:** появился второй самостоятельный аналитический контур и регулярная интеграция с внешним WB API.

---

## 0.4.0-alpha.1 — консолидация БД и требований

**Период:** 7 мая 2026 года  
**Mainline:** PR #14.

Что изменилось:

- уточнены требования к БД;
- зафиксированы дополнительные требования к persistence/data structure;
- подготовлен переход к системному production-аудиту.

**Почему 0.4:** архитектурная точка перед большой переработкой P0–P24, а не публичный релиз.

---

## 0.5.0-alpha.1 — production safety и durable sync foundation

**Период:** 14 сентября 2026 года  
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
- normalized ingestion текущих WB payloads.

### P4 / PR #19 — Durable Resumable Jobs

- atomic claim через `FOR UPDATE SKIP LOCKED`;
- processing leases и crash recovery;
- bounded retry budget;
- durable page checkpoints;
- restart продолжает sync с подтверждённой страницы.

**Почему 0.5:** проект впервые получил production-oriented security и устойчивый ingestion core, но пользовательский scope ещё был неполным.

---

## 0.6.0-alpha.1 — operational WB facts

**Период:** 14 сентября 2026 года  
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

**Почему 0.6:** система получила канонический operational/marketing fact layer вместо ранних отчётных assumptions.

---

## 0.7.0-alpha.1 — semantic layer и бизнес-вводы

**Период:** 15 сентября 2026 года  
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

**Почему 0.7:** появился единый semantic/business layer поверх marketplace facts — основа замены исходной аналитической таблицы.

---

## 0.8.0-alpha.1 — feature-complete WB analytics alpha

**Период:** 15 сентября 2026 года  
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

**Почему 0.8:** пользовательский WB analytics scope уже близок к первому полному продукту, но production access, billing и release infrastructure ещё не закрыты.

---

## 0.9.0-alpha.1 — release-hardening baseline

**Период:** 15 сентября 2026 года  
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
- duplicate callback/refresh не создаёт вторую subscription;
- sandbox/production separation.

**Почему 0.9.0-alpha.1:** функциональный WB scope сформирован, но ещё отсутствовали deployment/monitoring/backup/legal/session/release-smoke слои.

---

## 0.9.0-alpha.2 — version governance и production deployment baseline

**Период:** 15 сентября 2026 года  
**Mainline:** P25, PR #40  
**Merge commit:** `8cad1f098ae63c813ed36aad2c462d196484153a`.

Что изменилось:

- root `VERSION` стал source of truth;
- frontend/FastAPI version приведены к одной схеме;
- runtime version доступна через health endpoints;
- формализованы SemVer и stage gates;
- добавлены production Docker images;
- same-origin nginx gateway;
- Compose topology: PostgreSQL, Redis, migration, API, worker, beat, frontend;
- production env contract без секретов;
- deployment/upgrade/rollback runbook;
- release-integrity CI проверяет version consistency, images и Compose.

**Почему всё ещё alpha:** deployment воспроизводим из repo, но operations, legal и финальный browser-session/release-smoke hardening ещё не закрыты.

---

## 0.9.0-alpha.3 — operations hardening

**Период:** 15 сентября 2026 года  
**Mainline:** P26, PR #41  
**Merge commit:** `76ee8651298fff99b8bf6a11921dcbfbf0916c46`.

Что изменилось:

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
- закрыт production refresh-cookie regression: единая Secure/SameSite/Domain policy, `Path=/`, legacy GET refresh удалён.

**Почему всё ещё alpha:** operations code baseline готов, но legal/consent и persistent browser access-token ещё оставались code-side blockers; реальные external/ops gates также не закрыты.

---

## 0.9.0-alpha.4 — versioned legal documents и consent evidence

**Период:** 15 сентября 2026 года  
**Mainline:** P27, PR #42  
**Merge commit:** `591b3919eb80403a7e4225382d996dca63b8c039`.

Что изменилось:

- backend registry обязательных юридических документов;
- каждый документ имеет стабильный `code`, `version` и SHA-256;
- публичные `/legal/requirements/{context}` и `/legal/documents/{code}`;
- immutable `legal_consents` с user/document/version/hash/context/timestamp;
- IP/User-Agent сохраняются только как HMAC evidence;
- backend отвергает отсутствующее согласие, устаревшую версию и несовпадающий hash;
- регистрация физлица/самозанятого требует `terms + privacy`;
- регистрация юрлица дополнительно требует `personal_data`;
- платный payment attempt требует `privacy + offer + refund_policy`;
- marketplace credential требует `privacy + credential_policy`;
- billing consent связывается с `payment_id`, credential consent — с credential ID;
- idempotent повтор Sber payment attempt не дублирует consent evidence;
- frontend получает актуальные версии документов с backend;
- созданы публичные legal pages и reusable consent checklist;
- legacy token-add endpoint также закрыт consent enforcement;
- техническая архитектура описана в `docs/LEGAL_CONSENT.md`.

Что намеренно не считается готовым:

- встроенные тексты имеют `1.0-draft.1`;
- реквизиты оператора/продавца ещё должны быть заполнены;
- финальные privacy/data-processing/refund terms должны пройти legal review;
- перед RC нужны non-draft версии и архив утверждённых текстов.

**Почему всё ещё alpha:** P27 закрывает техническую доказуемость согласий, но не юридическое утверждение содержания; также оставался code-side P28 browser session/release smoke.

---

## 0.9.0-alpha.5 — browser-session hardening и release smoke

**Период:** 15 сентября 2026 года  
**Рабочая ветка:** `codex/p28-session-hardening-release-smoke`  
**Статус:** кандидат P28; становится mainline milestone только после green CI и merge.

Что реализовано в P28:

- access JWT больше не хранится в `localStorage`/`sessionStorage`;
- access JWT существует только в оперативной памяти frontend;
- pre-P28 persistent auth values очищаются при загрузке;
- browser session после reload восстанавливается только по HttpOnly refresh-cookie;
- `/auth/refresh` возвращает access JWT и минимальный safe user snapshot;
- login/refresh используют единый session identity contract;
- Pinia auth store стартует пустым и выполняет refresh bootstrap до mount приложения;
- Axios подставляет только in-memory access JWT;
- concurrent 401 используют один refresh promise, без refresh storm;
- CI запрещает persistent `access_token`/user storage;
- production frontend больше не использует `localhost:9000` как API fallback;
- nginx gateway маршрутизирует `/auth`, `/dashboard`, `/billing`, `/legal`, `/control-panel`, `/users`, `/health`;
- release-integrity CI проверяет routing на реально запущенном frontend container;
- backend regression tests проверяют cookie-only session restore и безопасный user payload;
- `ops/release_smoke.py` формализует production-like health/legal/auth/session/dashboard smoke;
- runner имеет опциональные WB credential и Sber payment-init phases без вывода секретов;
- `docs/RELEASE_SMOKE.md` фиксирует полный smoke contract и release evidence.

### Что P28 не может закрыть кодом

Даже после green merge остаются внешние/операционные gates:

- реальные `WB_SERVICE_ID` и `WB_SERVICE_SECRET`;
- реальный seller account и полный WB sync smoke;
- Sber merchant onboarding/credentials и payment smoke;
- production host, DNS и TLS;
- реальный alert destination/uptime/logging;
- off-host backup и production-like restore drill;
- утверждённые non-draft legal documents;
- фактический production-like полный release smoke.

### Почему после P28 не назначаем beta автоматически

`0.9.0-beta.1` допускается только после **реального production-like прогона** и feature freeze. P28 закрывает последний запланированный code-side security/smoke baseline, но сам merge не является доказательством готовности внешних интеграций и среды.

---

## Следующие запланированные стадии

### 0.9.0-beta.1

Разрешена только после:

- merge P28 с полностью зелёным CI;
- feature freeze WB Web v1;
- отсутствия известных code-side P0 blocker;
- успешного production-like deployment;
- прохождения core release smoke;
- фиксации списка оставшихся только внешних/операционных blocker.

Beta означает заморозку функционального scope и переход к дефектам, UX-polish и production validation.

### 1.0.0-rc.1

Разрешена только после:

- реальных WB partner credentials и seller smoke;
- полного WB sync по всем release entities;
- Sber production merchant credentials и payment smoke;
- production deployment/TLS;
- реального alert destination/uptime/logging;
- off-host backup и production-like restore drill;
- юридических документов, утверждённых и опубликованных как non-draft;
- полного release smoke и сохранённого release evidence.

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

Переход `alpha -> beta -> rc -> stable` происходит только после выполнения соответствующих release gates.
