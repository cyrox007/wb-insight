# WB Insight — Release Readiness

Дата ревизии: 16 сентября 2026 года.

## Текущий статус

- `main`: **`0.9.0-alpha.10`** после P33 / PR #51, merge `9dacaee426937c7466ac22cedd878e11b53cc472`.
- P30 закрепил воспроизводимую data-accuracy acceptance и release-evidence baseline.
- P31 закрыл production-safe code baseline жизненного цикла аккаунта.
- P32 закрыл найденные перед beta дефекты registration/demo flow и встроил disposable registration evidence в core smoke.
- P33 закрыл найденный при pre-beta аудите production-config blocker и добавил fail-closed startup contract.
- Финальный P33 head `272dabc04f16290bca71bd1030ffe24b8a2186bd` прошёл Backend security, Frontend build, Database migrations и Release integrity.
- Основной WB Web v1 feature/code scope заморожен; следующий stage — `0.9.0-beta.1` только после фактического production-like, SMTP recovery и real-seller acceptance с evidence manifest.

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
- backend `pip-audit` gate без известных vulnerabilities на P33 final candidate;
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
- канонический demo tariff code выровнен на lowercase `demo`;
- registration DB failures и ошибка назначения базовой роли откатывают транзакцию безопасно;
- authenticated read-only `/legal/consents/me` не раскрывает IP/User-Agent evidence hashes;
- полный core smoke по умолчанию включает disposable registration → demo → exact legal evidence → refresh → self-deactivation → inactive-login rejection;
- production startup fail-closed отклоняет template/weak DB/JWT/WB/Sber credentials, malformed Fernet key, HTTP/example public endpoints и небезопасную recovery-конфигурацию;
- `LEGAL_EVIDENCE_HMAC_KEY` обязателен как отдельный production secret;
- `.env.production.example` намеренно не запускается как production без замены placeholders, и этот отрицательный contract проверяется CI;
- полная структурированная документация проекта.

P31 намеренно не реализует автоматический hard purge и не придумывает юридический срок retention/refund rules. Эти решения требуют утверждённой policy. P32/P33 не означают прохождение production-like acceptance: они делают соответствующие code-side проверки воспроизводимыми и fail-closed.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- отсутствия известных необработанных code-side release blockers на текущем `0.9.0-alpha.10` baseline;
- feature freeze WB Web v1;
- production-like HTTPS deployment из репозитория с реальными non-placeholder secrets/hosts;
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
