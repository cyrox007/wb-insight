# WB Insight — дорожная карта до стабильного релиза

Дата фиксации: 15 сентября 2026 года.

Цель: первый публичный стабильный релиз **WB Insight Web v1 / `1.0.0` для продавцов Wildberries**.

В scope `1.0.0`: регистрация и сессия, роли/admin, тарифы/demo/limits, подключение WB-кабинетов, автоматическая синхронизация, KPI/финансы/остатки/цены/реклама/unit-экономика, COGS, ручные расходы, план выручки, Сбер acquiring, production deployment, monitoring, backup/restore, versioned legal consent и безопасный account lifecycle.

Не блокируют `1.0.0`: Ozon, AI-аналитик, native mobile и WB OAuth 2.0 onboarding после Catalog readiness.

## Текущее состояние

- `main`: **`0.9.0-alpha.7`**, P30 слит PR #46, merge `77f1ec19cbe565cdbaca2a65a2c4cd7d5199ff5f`;
- dependency audits, release integrity, data-accuracy tooling и evidence manifest являются постоянными release gates;
- основной WB Web v1 feature baseline собран;
- P31 готовит **`0.9.0-alpha.8`** — account lifecycle code baseline;
- переход стадии определяется доказанными gates, а не номером P-задачи.

## Этап A — P29 / `0.9.0-alpha.6` — закрыт

Результат: frontend/backend dependency security gates, исправленный dependency graph и канонический `docs/`-портал.

## Этап B — P30 / `0.9.0-alpha.7` — закрыт

Результат:

- versioned metric/tolerance policy;
- deterministic data-accuracy runner на `Decimal`;
- JSON + Markdown acceptance reports;
- SHA-256 input/policy binding;
- positive/negative CI fixtures;
- release-evidence manifest для beta/RC/stable;
- CI contract успешного и намеренно провального acceptance;
- backend security и Alembic запускаются при каждом изменении `VERSION`.

P30 сделал процесс приёмки доказуемым, но не заменил фактическую production-like приёмку.

## Этап C — P31 / `0.9.0-alpha.8`: account lifecycle

Цель: убрать оставшиеся code-side сценарии, которые иначе требовали бы ручного вмешательства в production DB.

В P31 входят:

- password recovery через одноразовый email token, в БД хранится только digest;
- anti-enumeration response и rollback недоставленного SMTP token;
- durable `session_version` и немедленный отзыв ранее выданных JWT;
- paid cancel-at-period-end + undo без обрыва оплаченного периода;
- demo не участвует в paid cancellation semantics;
- self-service soft deactivation, retention metadata, отзыв sessions/credentials/reset links;
- admin reactivation и revoke-sessions;
- append-only lifecycle events;
- allowlisted support access/payment/refund records с actor/reference;
- late-Sber-payment safeguard для inactive account;
- recovery/security UI, migration и regression tests.

P31 не вводит автоматический hard purge и не подменяет утверждение legal retention/refund policy.

Выход этапа: `main = 0.9.0-alpha.8`, если exact P31 head проходит полный CI и PR merge.

## Этап D — production-like validation → `0.9.0-beta.1`

Цель: доказать работу продукта как единой системы.

Обязательно:

- feature freeze WB Web v1;
- отдельный production-like HTTPS environment из репозитория;
- миграции на чистой БД и upgrade копии существующей БД;
- deploy/rollback smoke без destructive downgrade;
- core `ops/release_smoke.py`;
- disposable registration + demo subscription + legal consent evidence;
- login/refresh-cookie restore/logout;
- account lifecycle smoke, включая password reset через реальный SMTP/provider;
- основные desktop/mobile сценарии и empty/loading/error states;
- отсутствие secrets/JWT/WB credentials в frontend bundle, git и logs;
- real-seller data-accuracy acceptance;
- полный beta evidence manifest для exact candidate commit.

### Data-accuracy gate

Минимум на одном реальном WB seller account и нескольких фиксированных периодах сверяются:

- заказы, продажи, возвраты;
- выручка;
- комиссии WB;
- логистика и хранение;
- реклама;
- себестоимость;
- ручные расходы;
- налоги;
- прибыль;
- выплаты/reconciliation;
- остатки и цены;
- unit-economy ratios.

Приоритет источников: официальный WB source для соответствующего домена, seller inputs для управленческих данных и исходная spreadsheet-модель как coverage/business reference. Spreadsheet не заменяет официальный источник, если прежняя формула была исправлена semantic layer.

Нельзя назначать beta при необъяснённом существенном денежном расхождении. Contract: `DATA_ACCURACY_ACCEPTANCE.md`.

## Этап E — внешние и эксплуатационные blockers до RC

### Wildberries

Нужны реальные `WB_SERVICE_ID`, `WB_SERVICE_SECRET`, service limits и seller account. Проверяется Base/Service flow, permissions/read-only, signing, полный sync orders/sales/products/stocks/prices/ads/funnel/paid-storage/finance и отсутствие необъяснённых 401/403/429.

### Сбер acquiring

Нужны merchant onboarding и sandbox/production credentials. Проверяются success, decline, cancel, retry, duplicate callback, server-side confirmation, одна subscription на payment, refund/reconciliation procedure и merchant back-office reconciliation.

### Production infrastructure

Нужны host/cluster, domain/DNS/TLS, secret management, PostgreSQL/Redis persistence, один Celery Beat, migration procedure и deploy/rollback drill.

### Monitoring и incident readiness

Нужно фактически подключить uptime `/health/ready`, alert destination, centralized logs/error triage и проверить доставку alert.

### Backup/restore

Нужно включить ежедневный encrypted backup, off-host/object storage, retention и выполнить restore drill с измеренными RPO/RTO.

### Legal

Draft-тексты заменяются утверждёнными versioned documents: terms/offer, privacy, personal-data consent, credential policy, refund/cancellation policy, retention/deletion policy и реквизиты оператора. Нужен immutable archive опубликованных версий и production `LEGAL_EVIDENCE_HMAC_KEY`.

### Lifecycle activation

P31 закрывает code baseline, но до RC нужны реальный SMTP recovery smoke, утверждённые retention/refund procedures и production-like evidence этих сценариев.

## Этап F — `1.0.0-rc.1`

RC допускается только после этапов D–E и полного `rc` evidence manifest.

Полный RC smoke включает registration/legal/demo, login/refresh/logout/recovery, account deactivation/support flow, реальный WB credential + full sync, все основные dashboards, COGS/expenses/plan, реальный Sber payment + paid activation/refund reconciliation, idempotency, monitoring, off-host backup, restore drill и deploy/rollback evidence.

## Этап G — `1.0.0` Stable

Stable выпускается из проверенного RC, а не из новой функциональной ветки.

Перед `v1.0.0`:

- нет необработанных Critical/High security issues;
- нет необъяснённых финансовых/аналитических расхождений;
- нет release-blocking RC дефектов;
- backup актуален, rollback проверен;
- legal documents non-draft;
- CHANGELOG/release notes финальны;
- полный `stable` evidence manifest сохранён;
- exact stable commit получает `VERSION=1.0.0` и immutable tag `v1.0.0`.

## Ownership

Внутри репозитория закрываем lifecycle code, acceptance tooling, smoke bugfixes, CI gates и versioning.

Внешние действия владельца/инфраструктуры: WB partner credentials/limits, Сбер merchant credentials/refund procedure, production hosting/domain/TLS, legal approval/requisites/retention, SMTP provider, alert/logging/object-storage providers.

Внешний blocker не останавливает безопасную code-side разработку, но без фактического закрытия нельзя выдавать beta/RC/stable в обход соответствующего gate.

## Каноническая последовательность

`0.9.0-alpha.7` -> `0.9.0-alpha.8` (P31 account lifecycle) -> `0.9.0-beta.1` (реальная production-like + SMTP + data accuracy) -> `1.0.0-rc.1` -> `1.0.0`.

Связанные документы: `RELEASE_SMOKE.md`, `DATA_ACCURACY_ACCEPTANCE.md`, `RELEASE_EVIDENCE.md`, `ACCOUNT_LIFECYCLE.md`, `VERSIONING.md`, `RELEASE_READINESS.md`.
