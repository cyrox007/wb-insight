# WB Insight — Release Readiness

Дата ревизии: 16 сентября 2026 года.

## Текущий статус

- `main`: **`0.9.0-alpha.8`** после P31 / PR #47, merge `6cb34aa9b4633e20d1810b6a5edd690056cde986`.
- P32 candidate: **`0.9.0-alpha.9`** на `codex/p32-registration-beta-smoke` — исправляет найденные перед beta дефекты регистрации/demo и встраивает disposable registration evidence в core smoke.
- P30 закрепил воспроизводимую data-accuracy acceptance и release-evidence baseline.
- P31 закрыл production-safe code baseline жизненного цикла аккаунта с полным green CI exact-head кандидата.
- P32 не расширяет feature scope WB Web v1: это release-hardening текущего frozen baseline.
- `0.9.0-beta.1` назначается только после merge P32 с green CI и фактического production-like, SMTP recovery и real-seller acceptance с evidence manifest.

## Code-side status

### Закрыто в main

- auth/session/RBAC baseline;
- account-scoped durable WB sync;
- orders/sales/returns;
- advertising/funnel;
- products/stocks/prices;
- paid storage;
- finance/reconciliation;
- historical COGS/manual expenses/revenue plan;
- Overview/Unit Economy/Finance/Inventory/Prices/Ads UI;
- marketplace adapter foundation;
- WB credential policy/live validation;
- Sber acquiring code baseline;
- production Docker/Compose baseline;
- monitoring/alerts code baseline;
- encrypted backup/restore + CI drill;
- versioned legal-consent technical baseline;
- browser access token in-memory + refresh restore;
- release smoke runner;
- frontend production/full dependency audit gate;
- backend `pip-audit` gate без известных vulnerabilities на P31 merge candidate;
- versioned data-accuracy comparator и release-evidence manifest tooling;
- password reset/recovery через email с anti-enumeration response;
- hashed one-time reset tokens; raw secret передаётся через URL fragment, а не HTTP query;
- production recovery requires HTTPS и SMTP STARTTLS с проверкой сертификата;
- durable `session_version` для немедленного отзыва access/refresh JWT;
- paid subscription cancel-at-period-end и undo без обрыва оплаченного периода;
- demo исключён из paid cancellation semantics;
- self-service soft deactivation с retention metadata;
- деактивация отзывает sessions, marketplace credentials и reset links;
- Sber paid callback/account deactivation race сериализован блокировкой строки пользователя;
- admin lifecycle mutations над `super_admin` ограничены `super_admin`;
- append-only account lifecycle audit trail;
- allowlisted support access/payment/refund events без ручного редактирования production DB;
- `/account/*` закреплён в production same-origin gateway smoke;
- Alembic `c8e5f1a2b934` проходит clean upgrade и metadata check;
- полная структурированная документация проекта.

P31 намеренно не реализует автоматический hard purge и не придумывает юридический срок retention/refund rules. Эти решения требуют утверждённой policy.

### P32 candidate до merge

- канонический demo tariff code выровнен на lowercase `demo` во всём registration flow;
- `insert_user()` больше не скрывает DB flush failures от transaction owner;
- registration явно rollback-ит `IntegrityError` и ошибку назначения базовой роли;
- добавлен authenticated read-only `/legal/consents/me` без IP/User-Agent evidence hashes;
- `ops/release_smoke.py` по умолчанию выполняет disposable registration → demo → exact consent evidence → refresh → self-deactivation → inactive-login rejection;
- добавлены regression tests на transaction/demo/consent privacy contracts;
- candidate version синхронизирован как `0.9.0-alpha.9`.

P32 должен пройти обычные Backend security, Frontend build, Database migrations и Release integrity на exact PR head. До merge эти пункты не считаются закрытыми в `main`.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- merge P32 / `0.9.0-alpha.9` с полным green CI exact-head;
- feature freeze WB Web v1 на текущем code baseline;
- production-like HTTPS deployment из репозитория;
- миграций на чистой БД и upgrade существующей БД;
- deploy/rollback smoke;
- фактического core `ops/release_smoke.py` без `--skip-disposable-registration`;
- disposable registration + demo subscription + exact persisted legal evidence;
- login/refresh-cookie restore/logout и lifecycle smoke;
- реального password-recovery smoke через настроенный SMTP/provider;
- основных desktop/mobile UX сценариев;
- проверки отсутствия secrets в frontend bundle/git/logs;
- приёмочной сверки аналитики минимум на одном реальном WB seller account;
- фиксированных acceptance-периодов и versioned tolerance policy;
- отсутствия необъяснённых существенных денежных расхождений;
- полного `beta` manifest от `ops/release_evidence.py` для exact candidate commit.

Подробности data-accuracy: `DATA_ACCURACY_ACCEPTANCE.md`. Формат evidence: `RELEASE_EVIDENCE.md`.

## Внешние blockers до RC

### Wildberries

Нужны фактические production partner/service credentials, разрешённые лимиты и реальный seller smoke. Проверяется полный sync всех заявленных доменов без необъяснённых auth/rate-limit ошибок.

### Сбер

Нужны merchant onboarding, sandbox/production credentials, HTTPS callback/return/fail URLs и реальные smoke-сценарии success/decline/cancel/retry/duplicate callback с back-office reconciliation. Для refund требуется утверждённая процедура и фактическая проверка у провайдера.

### Production infrastructure

Нужны фактические domain/DNS/TLS, secret management, production PostgreSQL/Redis topology и подтверждённый deploy/rollback.

### Operations

Нужно реально подключить uptime monitor, alert destination, centralized logs/error triage и проверить alert delivery на production-like трафике.

### Backup/restore

Нужно включить регулярный schedule, off-host storage и выполнить production-like restore drill с измеренными RPO/RTO.

### Legal

Текущие встроенные документы остаются draft. Перед RC должны быть утверждены и опубликованы non-draft версии: terms/offer, privacy, personal-data consent, marketplace credential policy, refund/cancellation policy, retention/deletion policy и реквизиты оператора.

### Account lifecycle — внешняя активация после P31

После code baseline P31 остаются доказательства среды:

- реальный SMTP/provider и recovery-delivery smoke;
- утверждённый retention срок и hard-delete procedure;
- утверждённая refund/cancellation policy;
- проверенная Sber refund/reconciliation procedure;
- production-like lifecycle smoke и evidence.

## Gate до `1.0.0-rc.1`

Все beta-gates плюс:

- реальный WB seller credential + full sync;
- реальный Sber payment/refund smoke;
- production deployment/TLS;
- monitoring/alerts/logging active;
- off-host backup + restore evidence;
- non-draft legal documents;
- account lifecycle проверен в production-like окружении;
- полный release smoke;
- полный `rc` evidence manifest для exact commit.

## Gate до `1.0.0`

Stable выпускается из проверенного RC, если:

- нет release-blocking дефектов;
- нет необработанных Critical/High security issues;
- нет необъяснённых финансовых/аналитических расхождений;
- backup актуален и rollback plan проверен;
- legal published;
- CHANGELOG/release notes финальны;
- полный `stable` evidence manifest сохранён;
- exact stable commit получает `VERSION=1.0.0` и tag `v1.0.0`.

Полная последовательность и ownership задач: [`RELEASE_ROADMAP.md`](RELEASE_ROADMAP.md). Smoke contract: [`RELEASE_SMOKE.md`](RELEASE_SMOKE.md).
