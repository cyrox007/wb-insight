# WB Insight — Release Readiness

Дата ревизии: 15 сентября 2026 года.

## Текущий статус

- `main`: **`0.9.0-alpha.5`** после P28.
- P29 готовит **`0.9.0-alpha.6`**: dependency/security hardening + полная ревизия документации.
- Основной WB Web v1 feature baseline собран.
- Следующий release stage — `0.9.0-beta.1`, но только после production-like и data-accuracy acceptance.

## Code-side status

### Закрыто

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
- frontend dependency audit gate;
- backend dependency audit gate — P29 candidate.

### До merge P29

- backend `pip-audit` должен пройти на последнем head;
- frontend production/full dependency audit должен быть green;
- временный lockfile regeneration workflow должен оставаться disabled/read-only и быть удалён housekeeping-изменением, когда доступно;
- вся version/documentation metadata должна быть синхронизирована;
- четыре основных CI-контура должны быть green на одном exact head.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- feature freeze WB Web v1;
- green `0.9.0-alpha.6` code baseline;
- production-like HTTPS deployment из репозитория;
- миграций на чистой и upgrade существующей DB;
- deploy/rollback smoke;
- core `ops/release_smoke.py`;
- disposable registration + demo + legal evidence;
- browser session restore/logout smoke;
- основных desktop/mobile UX сценариев;
- проверки отсутствия secrets в frontend/git/logs;
- приёмочной сверки аналитики с реальными WB отчётами/исходной spreadsheet-моделью;
- отсутствия необъяснённых существенных денежных расхождений.

## Внешние blockers до RC

### Wildberries

Нужны фактические production partner/service credentials, разрешённые лимиты и реальный seller smoke. Проверяется полный sync всех заявленных доменов без необъяснённых auth/rate-limit ошибок.

### Сбер

Нужны merchant onboarding, sandbox/production credentials, HTTPS callback/return/fail URLs и реальные smoke-сценарии success/decline/cancel/retry/duplicate callback с back-office reconciliation.

### Production infrastructure

Нужны фактические domain/DNS/TLS, secret management, production PostgreSQL/Redis topology и подтверждённый deploy/rollback.

### Operations

Нужно реально подключить uptime monitor, alert destination, centralized logs/error triage и проверить alert delivery на production-like трафике.

### Backup/restore

Нужно включить регулярный schedule, off-host storage и выполнить production-like restore drill с измеренными RPO/RTO.

### Legal

Текущие встроенные документы остаются draft. Перед RC должны быть утверждены и опубликованы non-draft версии: terms/offer, privacy, personal-data consent, marketplace credential policy, refund/cancellation policy и реквизиты оператора.

### Account lifecycle

До RC нужен production-safe сценарий восстановления доступа, отмены подписки, обработки возврата/ошибочного платежа, деактивации/удаления аккаунта и audit trail административных действий. Допускается support-mediated flow, если он документирован и не требует прямой правки DB.

## Gate до `1.0.0-rc.1`

Все beta-gates плюс:

- реальный WB seller credential + full sync;
- реальный Sber smoke;
- production deployment/TLS;
- monitoring/alerts/logging active;
- off-host backup + restore evidence;
- non-draft legal documents;
- account lifecycle закрыт;
- полный release smoke;
- сохранён release evidence для exact commit.

## Gate до `1.0.0`

Stable выпускается из проверенного RC, если:

- нет release-blocking дефектов;
- нет необработанных Critical/High security issues;
- нет необъяснённых финансовых/аналитических расхождений;
- backup актуален и rollback plan проверен;
- legal published;
- CHANGELOG/release notes финальны;
- release evidence сохранён;
- exact stable commit получает `VERSION=1.0.0` и tag `v1.0.0`.

Полная последовательность и ownership задач: [`RELEASE_ROADMAP.md`](RELEASE_ROADMAP.md). Smoke contract: [`RELEASE_SMOKE.md`](RELEASE_SMOKE.md).
