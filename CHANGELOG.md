# История изменений WB Insight

Здесь фиксируются значимые продуктовые вехи проекта. Версии, предшествующие введению формальной release-policy 15 сентября 2026 года, реконструированы по полной истории `main` и слитым pull request. Они описывают фактический уровень зрелости продукта и не означают, что в тот момент существовал Git tag с таким номером.

Подробная история с объяснением каждого перехода находится в `docs/VERSION_HISTORY.md`, правила дальнейшего версионирования — в `docs/VERSIONING.md`.

## [0.9.0-alpha.5] — 2026-09-15

P28 — browser-session hardening и формализация release smoke.

- access JWT больше не сохраняется в `localStorage` или `sessionStorage` и живёт только в памяти frontend-приложения;
- после перезагрузки страницы authenticated session восстанавливается исключительно через HttpOnly refresh-cookie;
- `/auth/refresh` возвращает минимальный безопасный user snapshot вместе с новым access JWT;
- login и refresh используют единый session identity contract;
- добавлена очистка legacy `access_token`/`user`, оставшихся от сборок до P28;
- Axios использует единый in-memory token store и один concurrent refresh promise, исключая гонку нескольких refresh-запросов;
- frontend CI запрещает повторное появление persistent storage для access JWT/user identity;
- исправлен production API fallback: production frontend использует same-origin backend gateway, а не `localhost:9000`;
- nginx gateway дополнен маршрутами `/billing` и `/legal`, которые ранее могли ошибочно попадать в SPA fallback;
- release-integrity CI теперь поднимает реальный frontend container и mock backend и проверяет маршрутизацию `/auth`, `/dashboard`, `/billing`, `/legal`, `/control-panel` и `/health`;
- добавлены backend regression tests восстановления session по refresh-cookie;
- добавлен `ops/release_smoke.py` для production-like health/legal/login/profile/refresh/dashboard/logout smoke и опциональных WB/Sber фаз;
- добавлен `docs/RELEASE_SMOKE.md` с полным WB Web v1 smoke contract и требованиями к release evidence.

## [0.9.0-alpha.4] — 2026-09-15

P27 — versioned legal documents и доказуемая фиксация согласий.

- добавлен backend registry юридических документов с кодом, версией и SHA-256 текста;
- добавлены публичные API requirements и просмотра конкретного документа;
- создана immutable таблица `legal_consents` для точной версии принятого документа;
- evidence содержит контекст, ссылку на бизнес-объект и UTC timestamp;
- IP и User-Agent не сохраняются открытым текстом — фиксируются только HMAC;
- регистрация backend-ом требует актуальные версии `terms` и `privacy`, а для юрлиц также `personal_data`;
- платёж нельзя создать без актуальных `privacy`, `offer` и `refund_policy`;
- WB credential нельзя сохранить без `privacy` и `credential_policy`;
- frontend получает legal requirements с backend и отправляет точные `version + sha256`;
- добавлены публичные `/legal/:code`, совместимые `/terms` и `/privacy`, а также reusable consent checklist;
- production env дополнен отдельным `LEGAL_EVIDENCE_HMAC_KEY`;
- добавлена техническая документация `docs/LEGAL_CONSENT.md` и тесты version/hash enforcement;
- юридические тексты намеренно остаются `draft`: их утверждение владельцем сервиса/юристом остаётся обязательным внешним условием до RC.

## [0.9.0-alpha.3] — 2026-09-15

P26 — эксплуатационный hardening: monitoring, alerts, backup/restore и проверяемые operational assets.

- добавлен super-admin operational snapshot без seller secrets и PII;
- контролируются failed sync jobs, истёкшие processing leases и stale sync states;
- добавлены предупреждения по истекающим marketplace credentials;
- добавлен контроль срока ротации `WB_SERVICE_SECRET` без раскрытия секрета;
- реализованы Redis minute-bucket counters для HTTP 5xx rate;
- добавлен периодический Celery operations monitor;
- добавлен deduplicated alert webhook для агрегированных operational signals;
- добавлены зашифрованные PostgreSQL backup с SHA-256 и retention;
- destructive restore требует явного подтверждения;
- добавлен isolated restore drill во временную БД;
- release-integrity CI выполняет реальный encrypted backup/restore roundtrip;
- добавлен operations runbook и зафиксированы стартовые RPO/RTO targets;
- исправлен production refresh-cookie contract: единая Secure/SameSite/Domain policy, `Path=/`, удалён legacy `GET /auth/refresh`;
- расширена подробная история версий проекта.

## [0.9.0-alpha.2] — 2026-09-15

P25 — управление версиями и базовый production deployment.

- корневой `VERSION` стал канонической версией продукта;
- версия backend/frontend приведена к единой схеме;
- задокументированы правила SemVer и переходов `alpha -> beta -> rc -> stable`;
- реконструирована история продуктовых версий;
- добавлены production Docker images backend/frontend;
- добавлена production Compose topology с отдельными migration/API/worker/beat/frontend процессами;
- добавлен same-origin `/api` gateway;
- добавлены deployment/upgrade/rollback runbook и release-integrity CI.

## [0.9.0-alpha.1] — 2026-09-15

Базовая стадия release-hardening после P19–P24.

### P19 — соответствие WB credential contract — PR #34

- тип WB-токена определяется по JWT claim `acc`, а не по вводу frontend;
- срок действия берётся из реального `exp`, а не вычисляется как условные 180 дней;
- Personal/Test tokens запрещены для cloud production flow;
- Service token связывается с настроенным service identity;
- WB authorization переведён на документированный Bearer format.

### P20 — Marketplace Adapter Core — PR #35

- введены общий контракт `MarketplaceAdapter` и registry;
- WB handlers вынесены за `WildberriesAdapter`;
- orchestration синхронизации стала marketplace-aware без дублирования worker infrastructure.

### P21 — Marketplace Credential Foundation — PR #36

- credentials получили `external_account_id`;
- `expires_at` стал nullable для ключей без фиксированного срока действия;
- seller identity хранится отдельно от encrypted secret;
- исправлены регрессии legacy credential endpoint.

### P22 — WB access-token policy и live validation — PR #37

- проверяются обязательные категории WB API и Read Only permission mask;
- production требует partner `WB_SERVICE_ID` и `WB_SERVICE_SECRET`;
- Base/Service seller requests используют `X-Client-Secret`;
- перед сохранением токен live-проверяется через WB;
- revoked/invalid credentials отклоняются fail-closed.

### P23 — Release Readiness baseline — PR #38

- добавлены liveness/readiness endpoints;
- readiness проверяет PostgreSQL и Redis;
- README/SETUP приведены к фактическому состоянию продукта;
- зафиксированы release blockers и Definition of Done.

### P24 — production flow Сбер acquiring — PR #39

- server-to-server регистрация и проверка статуса платежа;
- idempotent payment attempts;
- callback используется только как trigger, а не как доказательство оплаты;
- подписка активируется только после подтверждённого банком deposited state;
- добавлены payment event log, защита от двойной активации и разделение sandbox/production.

## [0.8.0-alpha.1] — 2026-09-15

Функционально полный alpha-контур WB-аналитики после P14–P18.

### P14 — Dashboard UX Foundation — PR #29

- создан единый спокойный дизайн системы аналитики;
- перестроены Overview / Unit Economy / Ads;
- удалены demo/hardcoded KPI;
- исправлена передача периода/фильтров и подписи метрик.

### P15 — Seller Inputs и Settings Workspace — PR #30

- реальное редактирование профиля продавца;
- workspace подключённых WB-кабинетов;
- ввод себестоимости с effective dates и CSV path;
- управление ручными расходами;
- settings UI приведён к основному design system.

### P16 — Inventory Risk и Replenishment Planning — PR #31

- модель спроса по 30 завершённым дням;
- расчёт stock cover;
- порог критического остатка и рекомендация поставки;
- отдельный stocks dashboard с account scope.

### P17 — Price Monitoring и History — PR #32

- durable sync цен WB;
- история только фактических изменений;
- size-aware current price model;
- price dashboard и фильтрация по кабинету.

### P18 — Finance Reports и Payout Reconciliation — PR #33

- canonical summaries финансовых отчётов WB;
- снимок текущего баланса;
- reconciliation summary/detail с tolerance;
- finance dashboard и durable finance sync.

## [0.7.0-alpha.1] — 2026-09-15

Созревание semantic/data model после P8–P13.

### P8 — Unified Semantic Metrics — PR #23

- общий semantic metrics layer;
- operational orders отделены от finance realization facts;
- advertising attribution отделена от общего количества заказов;
- исправлены comparison periods, границы московского дня и sync status semantics.

### P9 — Multi-account Dashboard Filter — PR #24

- единый `DashboardAccountScope`;
- безопасные режимы выбранного кабинета и всех разрешённых кабинетов;
- SQL-level scoping в Main, Charts, Ads и Unit Economy;
- frontend account selector сохраняется между аналитическими разделами.

### P10 — корректность Unit Economy — PR #25

- исправлены obsolete aliases/runtime mismatches;
- aggregate ratios пересчитываются из числителей/знаменателей;
- фактические рекламные расходы включены по SKU;
- API contract синхронизирован с frontend expectations.

### P11 — Monthly Revenue Plans — PR #26

- persistent monthly revenue targets по WB-кабинету;
- корректная длина календарного месяца;
- отдельно считаются required revenue/day и orders/day;
- aggregation по всем кабинетам без выдуманных fallback targets.

### P12 — Durable Paid Storage Sync — PR #27

- официальный WB Paid Storage task/status/download flow;
- durable task checkpoints и chunks не более 8 дней;
- rolling refresh и idempotent replacement semantics.

### P13 — Historical COGS и Seller Expenses — PR #28

- date-effective история себестоимости;
- manual expenses на уровне account/SKU;
- Unit Economy и Main profit используют историческую COGS и scoped expenses;
- cost-price API корректно зарегистрирован в приложении.

## [0.6.0-alpha.1] — 2026-09-14

Фундамент операционных WB-данных после P5–P7.

### P5 — Orders и Sales Facts — PR #20

- account-scoped WB orders и sales/returns facts;
- canonical identities и stale-update protection;
- durable source cursors и retention-aware initial sync.

### P6 — Advertising Sync — PR #21

- актуальный Promotion API campaign discovery и `fullstats v3` ingestion;
- account-scoped рекламные facts и rolling refresh;
- campaign batching, typed permission errors и durable checkpoints.

### P7 — Daily Sales Funnel — PR #22

- product funnel facts по account/product/day;
- views, carts, orders, buyouts и conversion metrics;
- batching по 20 items, 7-day refresh и durable checkpointing;
- typed handling feature-unavailable responses.

## [0.5.0-alpha.1] — 2026-09-14

Production-safety и durable-sync foundation после P0–P4.

### P0 — Production Safety — PR #15

- строгая separation access/refresh JWT и безопасный refresh/logout flow;
- server-side RBAC control panel;
- защищённое управление пользователями/ролями;
- secrecy marketplace credentials и тарифные лимиты кабинетов;
- fail-closed billing defaults;
- audit logging и migration/test CI baseline.

### P1 — Account-scoped Sync — PR #16

- sync state/job identity привязана к точному marketplace credential;
- scheduler/worker проверяют ownership, validity и tariff allowance;
- миграции стали воспроизводимыми и проверяются на чистом PostgreSQL.

### P2 — WB Transport Hardening — PR #17

- Redis-coordinated rate limiting по endpoint/account;
- bounded retries, `Retry-After`, typed transport/auth/rate errors;
- credential деактивируется только при подтверждённой auth failure;
- deterministic cleanup ресурсов.

### P3 — WB API Contracts и Pagination — PR #18

- актуальные Finance, Stocks и Content contracts;
- безопасная pagination и cursor-stall protection;
- account-scoped finance/product/stock identities;
- нормализация текущих API payloads.

### P4 — Durable Resumable Jobs — PR #19

- atomic job claims с leases;
- crash recovery и bounded retries;
- committed page checkpoints для Finance/Stocks/Products;
- restart продолжает работу с последней сохранённой страницы.

## [0.4.0-alpha.1] — 2026-05-07

Веха консолидации БД и документации.

- слит PR #14 с обновлением требований/заметок по базе данных;
- ранние assumptions persistence были собраны перед сентябрьским production-аудитом.

## [0.3.0-alpha.1] — 2026-05-06

Ранняя синхронизация Wildberries и реклама.

- PR #8: исправлено поведение sync при недействительном marketplace token;
- PR #9: синхронизация рекламной статистики;
- PR #10 и #11: итерации advertising backend/frontend;
- PR #12: исправление advertising import.

PR #13 был закрыт без merge и не входит в mainline release history.

## [0.2.0-alpha.1] — 2026-05-05

Первая веха Unit Economy.

- PR #4–#7 последовательно добавляли и уточняли первые WB reports и unit-economy implementation.

## [0.1.0-alpha.1] — 2026-03-30

Базовая реконструкция репозитория.

- PR #1 сформировал первый reconstructed codebase в `main`;
- PR #2 и #3 были закрыты без merge и исключены из продуктовой истории версий.

## Почему проект остаётся в 0.x

Стабильный публичный контракт ещё не объявлен. Работы P0–P28 существенно изменяли authentication, data identities, WB API contracts, sync semantics, финансовую модель, billing, legal-consent model, browser session security и release infrastructure. Назвать одну из этих промежуточных стадий `1.0.0` означало бы преждевременно заявить стабильность.

Целевая последовательность WB Web v1:

`0.9.0-alpha.N` -> `0.9.0-beta.N` -> `1.0.0-rc.N` -> `1.0.0`.
