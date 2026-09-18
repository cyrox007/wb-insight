# WB Insight — Release Readiness

Дата ревизии: 16 сентября 2026 года.

## Текущий статус

- release baseline `main`: **`0.9.0-alpha.11`**; integration/candidate work собирается в `dev`.
- P31–P36 release-hardening baseline закрыт.
- P37 durable audit trail закрыт PR #74, merge `31434c26e98960c0f591bdcb969ba12d96af8263`.
- payment administration foundation закрыт PR #71, merge `e42c691eaa2f75d7149e78222ae605d039f2eabd`.
- P38/P39 verified email identity + durable/provider-neutral mail delivery закрыты PR #77, merge `5733ebd2b74a2947ce583dfa78734bdeb1335357`.
- основной WB Web v1 feature scope **заморожен**;
- текущий release stage — **P40 / issue #78: production-like beta acceptance и evidence closure**;
- `0.9.0-beta.1` разрешён только после фактического P40 acceptance на exact candidate commit.

## Code-side status: baseline закрыт; новая интеграция идёт через dev

- auth/session/RBAC, роли и Control Panel;
- account-scoped durable WB sync;
- orders/sales/returns, products/stocks/prices, advertising/funnel, paid storage;
- finance/reconciliation, historical COGS, manual expenses, revenue plan;
- Overview/Unit Economy/Finance/Inventory/Prices/Ads UI;
- marketplace credential policy/live validation;
- acquiring baseline + управляемые payment-provider test/live configs и payment journal;
- production Docker/Compose + hardened systemd updater;
- monitoring/alerts code baseline;
- encrypted backup/restore + CI drill;
- versioned legal-consent technical baseline;
- access JWT in-memory + HttpOnly refresh restore;
- password reset/recovery через durable transactional mail;
- digest-only reset/verification tokens, raw secrets только в URL fragment;
- durable `session_version`, paid cancel-at-period-end/undo, self-service soft deactivation;
- durable append-only P37 audit trail + Control Panel «Аудит»;
- P38 email verification: new account login/demo gated by ownership proof when enabled;
- безопасная смена email через `pending_email`, session/reset invalidation после подтверждения;
- provider-neutral mail registry, SMTP initial adapter;
- durable Celery mail outbox с retry/backoff/idempotency;
- campaign draft/preview/test/immediate/scheduled launch/cancel, segmentation, suppression и delivery history;
- campaign scheduling с row lock/due-time recheck и retry-safe materialization;
- mail failure-rate/stale-queue operational checks;
- Control Panel «Рассылки» с фильтрами/pagination/scheduling;
- versioned data-accuracy comparator и evidence manifest tooling;
- beta manifest v2 требует `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`;
- P40 live-WB/data provenance gate связывает passing `data_accuracy` с тем же live-validated seller account через secret-safe HMAC fingerprint, обязательный credential cleanup и SHA-256 binding защищённого input;
- production startup fail-closed для слабых/template secrets, unsafe endpoints и некорректных provider configs.

Все существующие пользователи при P38 schema upgrade сохраняют доступ: migration backfill-ит их verified-state. Новые registrations требуют подтверждения только после явного production включения verification вместе с рабочим mail transport.

## Production-like host

Исторические snapshots Python 3.10/Node 18 и локального helper updater больше не являются каноническим release state: deployment tooling после P36 неоднократно harden-илось. Для beta evidence не используется старый снимок хоста — состояние должно быть **заново зафиксировано на exact beta candidate commit**. До promotion таким commit является exact `dev` head; после green consolidated acceptance выполняется отдельный `dev -> main` release PR.

P40 deployment evidence обязан подтвердить:

1. clean working tree и штатный `./update.sh`;
2. активный immutable Python 3.12 release environment;
3. поддерживаемую Node-линию;
4. backend/Celery worker/Celery Beat/nginx после стабилизационных checks;
5. Alembic current/head и metadata consistency;
6. `/health/ready` на deployed version;
7. rollback procedure/evidence;
8. фактически опубликованный frontend bundle того же candidate commit.

## Promotion flow до `0.9.0-beta.1`

Рабочие ветки вливаются только в `dev`. После завершения code-side набора на exact `dev` head вручную запускается consolidated CI, затем на этом же candidate commit собирается production-like acceptance/evidence. Только green candidate продвигается отдельным `dev -> main` release PR; promotion не должен добавлять функциональные изменения.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- feature freeze и отсутствия известных необработанных code-side release blockers;
- production-like HTTPS deployment с реальными non-placeholder secrets/hosts;
- миграций clean DB + upgrade копии существующей БД;
- deploy/rollback smoke;
- полного `ops/release_smoke.py` без `--skip-disposable-registration`;
- **реального email verification smoke** на deliverable disposable/catch-all адресе;
- demo activation только после verification ownership proof;
- **реального password reset** через настроенный mail provider;
- login/refresh-cookie restore/logout/deactivation;
- representative durable P37 audit correlation по request id;
- desktop/mobile UX для client screens и Control Panel users/roles/tariffs/payments/audit/mail;
- secrets review frontend bundle/git/logs/audit/mail/payment metadata;
- real-seller data-accuracy минимум на трёх фиксированных периодах: все required metrics, `missing=0`, нет необъяснённых существенных денежных расхождений; protected input и passing report должны быть связаны с тем же live-validated WB account через `wb-live-data` proof;
- каждый tolerance override имеет `override_reason` + review evidence;
- backup + isolated restore evidence;
- полного beta manifest v2 для exact `0.9.0-beta.N` candidate.

До включения реальной почты `EMAIL_VERIFICATION_ENABLED=false` и `MAIL_DELIVERY_ENABLED=false` остаются безопасными deployment defaults; это позволяет выкатывать код/миграции без внезапной блокировки текущих пользователей, но **не закрывает beta acceptance**.

## Внешние blockers до RC

### Wildberries

Нужны фактические production partner/service credentials, разрешённые лимиты и real seller full-sync smoke без необъяснённых auth/rate-limit ошибок.

### Acquiring

Нужны merchant onboarding, sandbox/production credentials, HTTPS callback/return/fail URLs и реальные success/decline/cancel/retry/duplicate callback/refund/reconciliation scenarios. Code-side test/live isolation и journal уже есть.

### Production infrastructure

Нужны domain/DNS/TLS, secret management, production PostgreSQL/Redis topology и подтверждённый deploy/rollback.

### Operations

Нужно реально подключить uptime monitor, alert destination, centralized logs/error triage и проверить alert delivery. Audit trail должен участвовать в incident triage.

### Backup/restore

Нужно включить schedule/off-host storage и выполнить production-like restore drill с измеренными RPO/RTO.

### Legal

До RC должны быть утверждены и опубликованы non-draft terms/offer, privacy, personal-data consent, marketplace credential policy, refund/cancellation policy, retention/deletion policy и реквизиты оператора.

## Gate до `1.0.0-rc.1`

Все beta gates плюс реальный WB full sync, acquiring/refund smoke, active monitoring/logging, off-host backup/restore evidence, non-draft legal documents и полный `rc` evidence manifest exact commit.

## Gate до `1.0.0`

Stable выпускается из проверенного RC, если нет release-blocking defects, необработанных Critical/High security issues и необъяснённых финансовых расхождений; backup/rollback/legal доказаны; CHANGELOG/release notes финальны; stable evidence manifest сохранён; exact commit получает `VERSION=1.0.0` и tag `v1.0.0`.

Полная последовательность: [`RELEASE_ROADMAP.md`](RELEASE_ROADMAP.md). Smoke contract: [`RELEASE_SMOKE.md`](RELEASE_SMOKE.md). Evidence contract: [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).
