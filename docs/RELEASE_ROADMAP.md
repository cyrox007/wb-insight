# WB Insight — дорожная карта до стабильного релиза

Дата фиксации: 16 сентября 2026 года.

Цель: первый публичный стабильный релиз **WB Insight Web v1 / `1.0.0` для продавцов Wildberries**.

В scope `1.0.0`: регистрация и сессия, роли/admin, тарифы/demo/limits, подключение WB-кабинетов, автоматическая синхронизация, KPI/финансы/остатки/цены/реклама/unit-экономика, COGS, ручные расходы, план выручки, Сбер acquiring, production deployment, monitoring, backup/restore, versioned legal consent и безопасный account lifecycle.

Не блокируют `1.0.0`: Ozon, AI-аналитик, native mobile и WB OAuth 2.0 onboarding после Catalog readiness.

## Текущее состояние

- `main`: **`0.9.0-alpha.11`**;
- P34 слит PR #53, merge `2b0ce4522adda642f6af8fa78b30e5440a7469be`;
- P36 systemd deployment hotfix слит PR #55, merge `d4c8a20d6ecc75ab9cd8449bd55f6b2ce4242d9c`, без изменения product version;
- dependency audits, release integrity, data-accuracy tooling и evidence manifest v2 являются постоянными release gates;
- основной WB Web v1 feature/code baseline собран и feature scope заморожен;
- P31 закрыл account lifecycle baseline, P32 — registration/demo и disposable beta-smoke, P33 — fail-closed production configuration, P34 — beta evidence-contract closure;
- P35 активен как hardening data-accuracy completeness: обязательные policy-метрики нельзя пропустить/понизить, tolerance override требует документированную причину;
- P36 добавил безопасный systemd updater с Python 3.12 preflight, fresh venv, Alembic, `npm ci`, restart/readiness и отдельным CI workflow;
- следующий stage — `0.9.0-beta.1` только после фактического production-like acceptance;
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

## Этап C — P31 / `0.9.0-alpha.8` — закрыт

Результат:

- password recovery через одноразовый email token, в БД хранится только digest;
- raw reset secret передаётся через URL fragment и не попадает в HTTP request URI;
- anti-enumeration response и rollback недоставленного SMTP token;
- production recovery fail-closed требует HTTPS и SMTP STARTTLS с проверкой сертификата;
- durable `session_version` и немедленный отзыв ранее выданных JWT;
- paid cancel-at-period-end + undo без обрыва оплаченного периода;
- demo не участвует в paid cancellation semantics;
- self-service soft deactivation, retention metadata, отзыв sessions/credentials/reset links;
- admin reactivation и revoke-sessions с отдельной защитой `super_admin` targets;
- append-only lifecycle events;
- allowlisted support access/payment/refund records с actor/reference;
- late-Sber-payment safeguard для inactive account и serialization payment/deactivation через user row lock;
- recovery/security UI, migration и regression tests;
- `/account/*` входит в production same-origin gateway smoke;
- clean Alembic upgrade и metadata check подтверждены CI.

P31 не вводит автоматический hard purge и не подменяет утверждение legal retention/refund policy.

## Этап C2 — P32 / `0.9.0-alpha.9` — закрыт

**PR:** #49  
**Merge:** `7206df554e6f98c2533160385d9ad7d27c704268`.

Причина появления этапа — release-smoke ревизия после P31 обнаружила два реальных code-side blocker:

- demo subscription искала несовместимый uppercase `DEMO`, хотя канонический tariff code — lowercase `demo`;
- `insert_user()` скрывал DB flush exception и мог оставлять request transaction в failed-state перед автоматическим commit.

P32 закрыл:

- единый lowercase `demo` contract;
- явный rollback registration `IntegrityError` и ошибки назначения базовой роли;
- атомарный user/role/legal-consent/demo registration flow;
- privacy-safe authenticated read-only consent evidence endpoint;
- встроенный disposable registration smoke по умолчанию: registration → demo → exact legal evidence → refresh → soft-deactivation → inactive login rejection;
- best-effort cleanup временного аккаунта даже при частичном падении smoke;
- regression tests transaction/demo/consent API contracts.

Это hardening существующего feature scope, а не новая продуктовая функциональность. Exact P32 head прошёл Backend security, Frontend build, Database migrations и Release integrity перед merge.

## Этап C3 — P33 / `0.9.0-alpha.10` — закрыт

**PR:** #51  
**Merge:** `9dacaee426937c7466ac22cedd878e11b53cc472`.

Причина появления этапа — финальный pre-beta audit выявил, что production runtime мог формально стартовать с template/weak values из `.env.production.example`.

P33 закрыл:

- единый fail-closed production preflight на общем `settings` import path для API/Alembic/Celery;
- запрет `DEBUG=true`, HTTP public endpoints, reserved example hosts и `replace-with-*` placeholders;
- minimum/weak-secret validation для production DB/JWT/legal-evidence/WB/Sber credentials;
- реальную Fernet validation для `API_TOKEN_ENCRYPTION_KEY`;
- отдельный обязательный production `LEGAL_EVIDENCE_HMAC_KEY`;
- conditional fail-closed Sber gateway/merchant validation;
- conditional fail-closed SMTP/reset URL/sender/STARTTLS validation;
- намеренно неготовый к production запуску `.env.production.example`;
- CI contract: template обязан упасть, CI-only безопасные overrides обязаны импортировать полный FastAPI app;
- regression tests production/Sber/lifecycle validation.

Первый CI P33 поймал regression порядка recovery validation и ошибку Sber test fixture; оба дефекта исправлены до merge. Финальный exact head прошёл Backend security, Frontend build, Database migrations и Release integrity.

## Этап C4 — P34 / `0.9.0-alpha.11` — закрыт

**PR:** #53  
**Merge:** `2b0ce4522adda642f6af8fa78b30e5440a7469be`.

Причина появления этапа — после P33 обнаружено несоответствие между фактическим beta readiness и `ops/release_evidence.py`: старый runner мог выдать `status=complete` для beta только по `ci + core_smoke + data_accuracy`, хотя дорожная карта уже требовала deployment/rollback, SMTP/account lifecycle, desktop/mobile UX и secrets review.

P34 закрыл:

- обязательный beta evidence set: `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`;
- наследование полного beta-набора стадией RC и RC-набора стадией stable;
- stage/version binding: beta только для `*-beta.N`, RC для `*-rc.N`, stable без prerelease suffix;
- полный 40-символьный Git SHA вместо произвольной строки;
- запрет пустых и неизвестных artifacts;
- machine-readable validation `data_accuracy.status=pass`, schema/version/hash/count invariants;
- manifest schema v2;
- positive/negative CI self-tests контракта;
- синхронизацию `RELEASE_EVIDENCE.md`, `RELEASE_READINESS.md`, `VERSIONING.md` и этой дорожной карты.

Финальный exact head `0d0d3d6c7c9f17f569f816bd79d9577b7fc226e6` прошёл Backend security, Frontend build, Database migrations и Release integrity. P34 является governance/release-hardening этапом, а не доказательством внешней acceptance.

## Этап C5 — P36: systemd deployment hotfix — закрыт

**PR:** #55  
**Merge:** `d4c8a20d6ecc75ab9cd8449bd55f6b2ce4242d9c`.

P36 появился из реального production-like обновления Ubuntu/systemd: существующий `backend/venv` был создан на Python 3.10, а актуальный dependency graph требует Python 3.12.

P36 добавил:

- `ops/update_systemd.sh` с preflight Python/Node/runtime requirements;
- требование clean working tree и fast-forward-only update;
- fresh Python 3.12 venv до переключения symlink/path;
- установку requirements и Alembic новым environment;
- frontend `npm ci` + build;
- restart backend/Celery/Beat и nginx reload;
- bounded `/health/ready` с journal diagnostics;
- сохранение предыдущего venv для диагностики;
- `--preflight-only` и отдельный GitHub Actions workflow;
- `docs/SYSTEMD_DEPLOYMENT.md` и обновлённые installation/production/troubleshooting docs.

P36 не менял application behavior/schema и поэтому не повышал product version.

## Этап C6 — P35: обязательное data-accuracy coverage — активен

P35 закрывает ещё один найденный обход beta data-accuracy gate:

- каждая policy-required метрика должна присутствовать в каждом acceptance-периоде;
- отсутствующая обязательная метрика становится явным `missing` и блокирует run;
- input не может понизить policy-required метрику через `required:false`;
- изменение tolerance/mode относительно policy требует непустой `override_reason`;
- отчёт фиксирует required metric/observation counts и причины override;
- CI содержит full, failing, incomplete и invalid-override scenarios.

P35 не меняет runtime приложения и остаётся на `0.9.0-alpha.11` baseline.

## Этап D — production-like validation → `0.9.0-beta.1`

Цель: доказать работу продукта как единой системы.

Обязательно:

- feature freeze WB Web v1 на текущем `0.9.0-alpha.11` baseline;
- отсутствие известных необработанных code-side release blockers, включая закрытый P35;
- отдельный production-like HTTPS environment из репозитория с реальными non-placeholder secrets/hosts;
- для systemd deployment фактические процессы backend/Celery/Beat работают из Python 3.12 environment, а frontend build выполняется на поддерживаемой Node-линии (`^20.19` или `>=22.12`);
- clean working tree перед automated update; локальные helper-файлы вне Git не должны блокировать/подменять deployment procedure;
- миграции на чистой БД и upgrade копии существующей БД;
- deploy/rollback smoke без destructive downgrade;
- полный core `ops/release_smoke.py` без отключения disposable registration;
- disposable registration + demo subscription + exact legal consent evidence;
- login/refresh-cookie restore/logout;
- account lifecycle smoke, включая password reset через реальный SMTP/provider;
- основные desktop/mobile сценарии и empty/loading/error states;
- отсутствие secrets/JWT/WB credentials в frontend bundle, git и logs;
- real-seller data-accuracy acceptance со всеми policy-required метриками на каждом выбранном периоде;
- любой tolerance override документирован через `override_reason` и review evidence;
- полный beta evidence manifest v2 для exact `*-beta.N` candidate commit со всеми обязательными artifact kinds.

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

Нельзя назначать beta при `missing` обязательной метрике, необъяснённом существенном денежном расхождении или undocumented tolerance override. Contract: `DATA_ACCURACY_ACCEPTANCE.md`.

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

Внутри репозитория закрываем acceptance tooling, smoke bugfixes, CI gates, deployment tooling и versioning. P31 lifecycle, P32 registration/beta-smoke, P33 production-config, P34 evidence-contract и P36 systemd deployment hotfix закрыты; P35 data-accuracy completeness — текущая code-side задача.

Внешние действия владельца/инфраструктуры: WB partner credentials/limits, Сбер merchant credentials/refund procedure, production hosting/domain/TLS, legal approval/requisites/retention, SMTP provider, alert/logging/object-storage providers и фактическое production-like выполнение deployment/smoke.

Внешний blocker не останавливает безопасную code-side разработку, но без фактического закрытия нельзя выдавать beta/RC/stable в обход соответствующего gate.

## Каноническая последовательность

`0.9.0-alpha.11` (текущий main/hardening baseline) -> `0.9.0-beta.1` (реальная production-like + SMTP/lifecycle + UX/secrets review + полная data accuracy) -> `1.0.0-rc.1` -> `1.0.0`.

Связанные документы: `RELEASE_SMOKE.md`, `DATA_ACCURACY_ACCEPTANCE.md`, `RELEASE_EVIDENCE.md`, `ACCOUNT_LIFECYCLE.md`, `SYSTEMD_DEPLOYMENT.md`, `VERSIONING.md`, `RELEASE_READINESS.md`.
