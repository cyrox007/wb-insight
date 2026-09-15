# WB Insight — Release Readiness

Дата ревизии: 15 сентября 2026 года.

## Текущий статус

- `main`: **`0.9.0-alpha.6`** после P29 / PR #44.
- P29 dependency/security hardening закрыт; frontend и backend dependency audits входят в постоянный CI.
- P30 готовит **`0.9.0-alpha.7`**: воспроизводимую data-accuracy acceptance и release-evidence baseline.
- Основной WB Web v1 feature baseline собран и находится в feature-freeze направлении.
- `0.9.0-beta.1` назначается только после фактического production-like и real-seller acceptance, а не после merge tooling.

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
- frontend production/full dependency audit gate;
- backend `pip-audit` gate без известных vulnerabilities на P29 merge head;
- полная структурированная документация проекта.

### P30 candidate

P30 добавляет code-side доказуемость acceptance-процесса:

- versioned policy метрик/tolerances;
- deterministic data-accuracy comparator;
- машинные JSON/Markdown acceptance reports;
- positive/negative CI contracts;
- release-evidence manifest с exact commit/version/environment и hashes artifacts;
- обязательные evidence kinds для beta/RC/stable;
- запуск backend security и Alembic при каждом изменении `VERSION`.

Эти инструменты считаются готовыми только после green CI и merge P30. Они не заменяют реальные staging/WB/Sber/ops evidence.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- merge P30 с green release-candidate CI;
- feature freeze WB Web v1;
- production-like HTTPS deployment из репозитория;
- миграций на чистой БД и upgrade существующей БД;
- deploy/rollback smoke;
- core `ops/release_smoke.py`;
- disposable registration + demo subscription + legal evidence;
- browser session restore/logout smoke;
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
