# WB Insight — Release Readiness

Дата ревизии: 15 сентября 2026 года.

## Текущий статус

- `main`: **`0.9.0-alpha.7`** после P30 / PR #46, merge `77f1ec19cbe565cdbaca2a65a2c4cd7d5199ff5f`.
- P30 закрепил воспроизводимую data-accuracy acceptance и release-evidence baseline.
- P31 готовит **`0.9.0-alpha.8`**: production-safe code baseline жизненного цикла аккаунта.
- Основной WB Web v1 feature baseline собран и находится в feature-freeze направлении.
- `0.9.0-beta.1` назначается только после фактического production-like, SMTP recovery и real-seller acceptance, а не после merge code/tooling.

## Code-side status

### Закрыто в main до P31

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
- backend `pip-audit` gate без известных vulnerabilities на P29 merge head;
- versioned data-accuracy comparator и release-evidence manifest tooling;
- полная структурированная документация проекта.

### P31 candidate — `0.9.0-alpha.8`

P31 закрывает code-side account lifecycle:

- password reset/recovery через email с anti-enumeration response;
- криптографически случайный reset secret, в БД — только digest;
- SMTP failure rollback недоставленного token;
- durable `session_version`, делающий password reset/revoke/deactivation немедленно действующими для access и refresh JWT;
- paid subscription cancel-at-period-end и undo без обрыва оплаченного периода;
- demo исключён из paid cancellation semantics;
- self-service soft deactivation с retention metadata;
- деактивация отзывает sessions, marketplace credentials и reset links;
- admin reactivation без автоматического восстановления старых WB credentials;
- append-only account lifecycle audit trail;
- allowlisted support access/payment/refund events без ручного редактирования production DB;
- late Sber success для inactive account сохраняется как финансовый факт, но не создаёт subscription;
- recovery/security frontend UI и regression tests;
- Alembic migration `c8e5f1a2b934`.

P31 намеренно не реализует автоматический hard purge и не придумывает юридический срок retention/refund rules. Эти решения требуют утверждённой policy.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- merge P31 с green release-candidate CI;
- feature freeze WB Web v1;
- production-like HTTPS deployment из репозитория;
- миграций на чистой БД и upgrade существующей БД;
- deploy/rollback smoke;
- core `ops/release_smoke.py`;
- disposable registration + demo subscription + legal evidence;
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
