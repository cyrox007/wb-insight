# WB Insight — дорожная карта до стабильного релиза

Дата фиксации: 15 сентября 2026 года.

Цель: первый публичный стабильный релиз **WB Insight Web v1 / `1.0.0` для продавцов Wildberries**.

В scope `1.0.0`: регистрация и сессия, роли/admin, тарифы/demo/limits, подключение WB-кабинетов, автоматическая синхронизация, KPI/финансы/остатки/цены/реклама/unit-экономика, COGS, ручные расходы, план выручки, Сбер acquiring, production deployment, monitoring, backup/restore и versioned legal consent.

Не блокируют `1.0.0`: Ozon, AI-аналитик, native mobile и WB OAuth 2.0 onboarding после Catalog readiness.

## Текущее состояние

- `main`: **`0.9.0-alpha.6`**, P29 слит PR #44;
- dependency audits frontend/backend являются постоянными CI gates;
- основной WB Web v1 feature baseline собран;
- P30 готовит **`0.9.0-alpha.7`** — acceptance tooling и release evidence;
- переход стадии определяется доказанными gates, а не номером P-задачи.

## Этап A — P29 / `0.9.0-alpha.6` — закрыт

Результат:

- production/full frontend dependency audits без известных High/Critical;
- backend `pip-audit` без известных vulnerabilities на merge head;
- уязвимая `python-jose -> ecdsa` цепочка удалена;
- документация полностью реструктурирована;
- Backend security, Frontend build, Database migrations и Release integrity зелёные на exact merge head.

## Этап B — P30 / `0.9.0-alpha.7`: acceptance tooling

Цель: сделать beta-приёмку воспроизводимой и привязанной к exact commit.

В P30 входят:

- versioned metric/tolerance policy;
- deterministic data-accuracy runner на `Decimal`;
- JSON + Markdown acceptance reports;
- SHA-256 input/policy binding;
- positive/negative CI fixtures;
- release-evidence manifest для beta/RC/stable;
- CI contract, который проверяет успешный и намеренно провальный acceptance;
- запуск backend security и Alembic при каждом изменении `VERSION`.

Выход этапа: `main = 0.9.0-alpha.7`, если P30 проходит полный release-candidate CI.

**Важно:** merge P30 не означает beta. Инструмент проверки не является доказательством фактического прохождения проверки.

## Этап C — production-like validation → `0.9.0-beta.1`

Цель: доказать работу продукта как единой системы.

Обязательно:

- feature freeze WB Web v1;
- отдельный production-like HTTPS environment из репозитория;
- миграции на чистой БД и upgrade копии существующей БД;
- deploy/rollback smoke без destructive downgrade;
- core `ops/release_smoke.py`;
- disposable registration + demo subscription + legal consent evidence;
- login/refresh-cookie restore/logout;
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

## Этап D — внешние и эксплуатационные blockers до RC

### Wildberries

Нужны реальные `WB_SERVICE_ID`, `WB_SERVICE_SECRET`, service limits и seller account. Проверяется Base/Service flow, permissions/read-only, signing, полный sync orders/sales/products/stocks/prices/ads/funnel/paid-storage/finance и отсутствие необъяснённых 401/403/429.

### Сбер acquiring

Нужны merchant onboarding и sandbox/production credentials. Проверяются success, decline, cancel, retry, duplicate callback, server-side confirmation, одна subscription на payment и merchant back-office reconciliation.

### Production infrastructure

Нужны host/cluster, domain/DNS/TLS, secret management, PostgreSQL/Redis persistence, один Celery Beat, migration procedure и deploy/rollback drill.

### Monitoring и incident readiness

Нужно фактически подключить uptime `/health/ready`, alert destination, centralized logs/error triage и проверить доставку alert.

### Backup/restore

Нужно включить ежедневный encrypted backup, off-host/object storage, retention и выполнить restore drill с измеренными RPO/RTO.

### Legal

Draft-тексты заменяются утверждёнными versioned documents: terms/offer, privacy, personal-data consent, credential policy, refund/cancellation policy и реквизиты оператора. Нужен immutable archive опубликованных версий и production `LEGAL_EVIDENCE_HMAC_KEY`.

## Этап E — account lifecycle

До RC закрываются:

- восстановление/сброс пароля через подтверждённый канал;
- отмена платной подписки и возврат согласно policy;
- деактивация/удаление аккаунта и retention;
- support/admin procedure для блокировки, ошибочного платежа и потерянного доступа;
- audit trail административных действий, влияющих на доступ/оплату.

Support-mediated flow допустим, если документирован и не требует прямой правки БД оператором.

## Этап F — `1.0.0-rc.1`

RC допускается только после этапов C–E и полного `rc` evidence manifest.

Полный RC smoke включает registration/legal/demo, login/refresh/logout, реальный WB credential + full sync, все основные dashboards, COGS/expenses/plan, реальный Sber payment + paid activation, idempotency, monitoring, off-host backup, restore drill и deploy/rollback evidence.

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

Внутри репозитория закрываем acceptance tooling, account-lifecycle code gaps, smoke bugfixes, CI gates и versioning.

Внешние действия владельца/инфраструктуры: WB partner credentials/limits, Сбер merchant credentials, production hosting/domain/TLS, legal approval/requisites, alert/logging/object-storage providers.

Внешний blocker не останавливает безопасную code-side разработку, но без фактического закрытия нельзя выдавать RC/stable.

## Каноническая последовательность

`0.9.0-alpha.6` -> `0.9.0-alpha.7` (P30 acceptance tooling) -> `0.9.0-beta.1` (реальная production-like + data accuracy) -> `1.0.0-rc.1` -> `1.0.0`.

Связанные документы: `RELEASE_SMOKE.md`, `DATA_ACCURACY_ACCEPTANCE.md`, `RELEASE_EVIDENCE.md`, `VERSIONING.md`, `RELEASE_READINESS.md`.
