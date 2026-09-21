# WB Insight — дорожная карта до стабильного релиза

Дата актуализации: 21 сентября 2026 года.

Цель: первый публичный стабильный релиз **WB Insight Web v1 / `1.0.0` для продавцов Wildberries**.

В scope `1.0.0`: регистрация и сессия, подтверждение email, роли/admin, тарифы/demo/limits, подключение WB-кабинетов, автоматическая синхронизация, KPI/финансы/остатки/цены/реклама/unit-экономика, COGS, ручные расходы, план выручки, acquiring, управляемые transactional/user mail, production deployment, monitoring, backup/restore, versioned legal consent, безопасный account lifecycle и durable audit trail значимых действий пользователей/администраторов.

Не блокируют `1.0.0`: Ozon, AI-аналитик, native mobile и WB OAuth 2.0 onboarding после Catalog readiness.

## Текущее состояние

- release baseline `main`: **`0.9.0-alpha.11`**; exact candidate `dev`: **`0.9.0-beta.1`**;
- P34 закрыт PR #53, merge `2b0ce4522adda642f6af8fa78b30e5440a7469be`;
- P35 data-accuracy completeness hardening закрыт PR #56, merge `d2e782208228fbe60cb92b9e61fbf8d325f0e839`;
- P36 systemd deployment hardening закрыт PR #55 и последующими updater hotfixes;
- P37 durable audit trail закрыт PR #74, merge `31434c26e98960c0f591bdcb969ba12d96af8263`;
- payment administration foundation закрыт PR #71, merge `e42c691eaa2f75d7149e78222ae605d039f2eabd`;
- P38/P39 verified email identity + durable/provider-neutral mail delivery + campaigns закрыты PR #77, merge `5733ebd2b74a2947ce583dfa78734bdeb1335357`;
- P41 role-aware staff workspace + расширенное администрирование пользователей закрыт PR #119;
- P42 RuSender HTTPS transactional provider закрыт PR #120, merge `cf11b3c60cb24b74ce7dd9f1dc615bca6848343f`;
- P43 password-recovery hardening закрыт PR #121, merge `560322d264bde219338498cdb076e920de2ab9c9`;
- P44 Control Panel UI/RBAC UX unification закрыт PR #122, merge `f9d775e25a49df765d7839b42bcd15f8b60976e1`; issue #62 закрыт;
- dependency audits, release integrity, data-accuracy tooling и evidence manifest v2 остаются постоянными release gates;
- **WB Web v1 feature scope заморожен**: новые продуктовые функции не добавляются до beta, кроме исправления обнаруженных blocker-дефектов;
- текущий этап — **P40 / issue #78: production-like beta acceptance и закрытие evidence**;
- `0.9.0-beta.1` назначен exact candidate VERSION в `dev`; публикация/tag остаются заблокированы до фактического P40 acceptance и complete evidence.

Переход стадии определяется доказанными gates и exact-commit evidence, а не номером P-задачи.

## Этап A — P29 / `0.9.0-alpha.6` — закрыт

Результат: frontend/backend dependency security gates, исправленный dependency graph и канонический `docs/`-портал.

## Этап B — P30 / `0.9.0-alpha.7` — закрыт

P30 добавил versioned metric/tolerance policy, deterministic data-accuracy runner на `Decimal`, JSON/Markdown acceptance reports, SHA-256 input/policy binding, positive/negative CI fixtures и release-evidence manifest. Это сделало приёмку воспроизводимой, но не заменило фактическую production-like проверку.

## Этап C — P31 / `0.9.0-alpha.8` — закрыт

P31 закрыл account lifecycle baseline: password recovery с digest-only one-time tokens и URL fragment, anti-enumeration, durable `session_version`, отзыв JWT, cancel-at-period-end/undo, soft deactivation/retention, admin reactivation/revoke sessions, lifecycle events, support events и Sber late-payment safeguards.

Автоматический hard purge и юридические retention/refund сроки намеренно не придумываются кодом.

## Этап C2 — P32 / `0.9.0-alpha.9` — закрыт

**PR:** #49  
**Merge:** `7206df554e6f98c2533160385d9ad7d27c704268`.

Закрыты registration/demo transactional defects, единый lowercase `demo`, точное legal-consent evidence и встроенный disposable registration smoke: registration → demo → exact legal evidence → refresh → soft-deactivation → inactive login rejection.

## Этап C3 — P33 / `0.9.0-alpha.10` — закрыт

**PR:** #51  
**Merge:** `9dacaee426937c7466ac22cedd878e11b53cc472`.

Закрыт fail-closed production configuration: запрещены weak/template secrets, HTTP/example public endpoints, malformed encryption keys и небезопасная recovery/Sber конфигурация. `.env.production.example` намеренно не является готовым production env.

## Этап C4 — P34 / `0.9.0-alpha.11` — закрыт

**PR:** #53  
**Merge:** `2b0ce4522adda642f6af8fa78b30e5440a7469be`.

Beta evidence manifest v2 требует полный набор `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`, привязанный к корректному prerelease version и полному Git SHA. Data-accuracy artifact проверяется machine-readable.

## Этап C5 — P36: systemd deployment hardening — закрыт

**PR:** #55 + последующие updater hotfixes.

Production-like Ubuntu/systemd updater доведён до one-command deployment: runtime preflight, Python 3.12 immutable release venv, Alembic, frontend `npm ci`/build/publish, canonical Celery app, systemd restart/stability checks, backend readiness и безопасное сохранение предыдущего runtime. Updater сам обновляет собственную логику и не переносит установленный venv между путями.

P36 не повышал product version.

## Этап C6 — P35: обязательное data-accuracy coverage — закрыт

**PR:** #56  
**Merge:** `d2e782208228fbe60cb92b9e61fbf8d325f0e839`.

Каждая policy-required метрика должна присутствовать в каждом acceptance-периоде; input не может отключить required metric; tolerance override требует `override_reason`; missing и overrides отражаются в evidence. Необъяснённое существенное денежное расхождение блокирует release stage.

## Этап C7 — P37: durable audit trail — закрыт

**Issue:** #72  
**PR:** #74  
**Merge:** `31434c26e98960c0f591bdcb969ba12d96af8263`.

Реализованы:

- append-only durable `audit_events` + DB-level запрет UPDATE/DELETE;
- `X-Request-ID`/correlation, actor/role snapshot, target/result/source/safe error metadata;
- semantic action codes для state-changing и security-sensitive admin действий;
- privacy-safe hashed client evidence и recursive redaction без passwords/JWT/WB/payment/mail secrets;
- independent persistence denied/failed critical events;
- отдельный `AUDIT_READ` RBAC;
- Control Panel → «Аудит» с фильтрами, pagination и detail view.

Code-side P37 закрыт. Production-like representative audit correlation остаётся обязательной частью P40 acceptance.

## Этап C8 — P38/P39: verified email + mail delivery — закрыт

**Issues:** #75, #76  
**PR:** #77  
**Merge:** `5733ebd2b74a2947ce583dfa78734bdeb1335357`.

Реализованы:

- обязательная email verification при включённом production flag; digest-only одноразовые tokens, TTL/revoke/resend throttle;
- существующие аккаунты миграцией безопасно backfill-ятся как verified;
- demo активируется только после подтверждения email для новых verification-enabled registrations;
- `pending_email`: смена login email вступает в силу только после ownership proof; старые sessions/reset capabilities отзываются;
- единый durable mail outbox через Celery, bounded retry/backoff/idempotency;
- password reset переведён на общий mail layer;
- provider-neutral mail registry, SMTP как первый adapter;
- transactional mail отделён от marketing suppression;
- campaign draft/preview/test/immediate/scheduled launch/cancel, segmentation, suppression и delivery history;
- scheduled campaign scanner с row locking/due-time recheck и retry-safe materialization;
- pagination/status filters в Control Panel → «Рассылки»;
- mail failure-rate/stale-queue operational checks;
- marketing/test delivery fail-closed за `MAIL_DELIVERY_ENABLED`, auth mail не блокируется disabled campaign rows.

Exact final head #77 прошёл Frontend build, Backend security, Database migrations и Release integrity перед merge.

## Этап C9 — P41–P44: staff UX, user administration и production mail — закрыт

После заморозки основного seller feature scope были закрыты эксплуатационные blocker-дефекты, найденные при подготовке acceptance:

- **P41 / PR #119** — role-aware workspace `/staff` для `super_admin/admin/manager/support/analyst`, least-privilege permissions для staff-ролей, отдельные приоритеты вместо seller dashboard по умолчанию, расширенная карточка пользователя, ручная email-верификация, reactivation/deactivation и revoke sessions с lifecycle audit;
- **P42 / PR #120** — нативный RuSender transactional provider через HTTPS 443, encrypted bearer token, provider idempotency, safe retry classification и Control Panel transport selector. Это снимает зависимость transactional mail от блокируемых SMTP-портов хостинга;
- **P43 / PR #121** — production-ready recovery UX, resend throttling, deterministic idempotency, audit correlation и немедленное удаление reset token из browser URL/history после capture;
- **P44 / PR #122** — единый Control Panel UI pattern, semantic theme tokens, shared segmented/filter controls, role-safe account health summary и актуализированный RBAC UX.

Эти изменения не расширяют seller analytics scope `1.0.0`: они закрывают доступность, безопасность и эксплуатационную готовность auth/admin/mail контуров перед P40.

## Этап D — P40 / `0.9.0-beta.1` candidate production-like validation — открыт

**Issue:** #78.

P40 не расширяет feature scope. Его задача — доказать работу продукта как единой системы и сформировать обязательный beta evidence set.

Обязательно:

- exact candidate commit развернут штатным `./update.sh` на production-like HTTPS environment;
- реальный domain/TLS и non-placeholder secrets;
- backend/Celery/Beat на Python 3.12, frontend build на поддерживаемой Node-линии;
- clean working tree, миграции clean DB + upgrade копии существующей БД;
- deploy/rollback evidence без destructive downgrade;
- полный `ops/release_smoke.py` без skip disposable registration;
- **реальная email verification** через доставляемый disposable/catch-all address, затем demo activation; текущий production-like transactional transport — RuSender HTTPS API;
- real-mail password reset через тот же provider-neutral acceptance hook, включая проверку resend throttling и повторный login после session-version rotation;
- login/refresh-cookie restore/logout/deactivation;
- representative P37 durable audit smoke с контролируемым request id;
- desktop/mobile UX для client screens, role-aware staff workspace и Control Panel users/user-detail/roles/tariffs/payments/audit/mail; отдельно фиксируются inactive/unverified user states и RuSender gateway screen;
- отсутствие secrets/JWT/WB/mail/payment credentials в frontend bundle, git, audit и logs;
- real-seller data-accuracy acceptance со всеми required метриками, `missing=0` и документированными overrides;
- backup/isolated restore drill;
- полный beta evidence manifest v2 для exact `0.9.0-beta.N` candidate.

P40 tooling расширяет release smoke безопасным inbox-hook contract: helper получает `KIND`/`EMAIL`, но token/link остаётся captured secret и не печатается в evidence. Audit correlation также входит в sanitized smoke evidence.

### Data-accuracy gate

На реальном WB seller account и нескольких фиксированных периодах сверяются orders/sales/returns, revenue, commissions, logistics/storage, advertising, COGS/manual expenses/taxes, profit, payout/reconciliation, inventory/prices и unit-economy ratios.

Приоритет источников: официальный WB source для соответствующего домена, seller inputs для управленческих данных и spreadsheet-модель как coverage/business reference. Spreadsheet не заменяет официальный источник, если прежняя формула была исправлена semantic layer.

## Этап E — внешние и эксплуатационные blockers до RC

### Wildberries

Нужны реальные partner/service credentials, service limits и seller account. Проверяется полный sync orders/sales/products/stocks/prices/ads/funnel/paid-storage/finance без необъяснённых 401/403/429.

### Acquiring

Нужны merchant onboarding и sandbox/production credentials. Проверяются success, decline, cancel, retry, duplicate callback, server-side confirmation, одна subscription на payment, refund/reconciliation procedure и merchant back-office reconciliation. Payment test/live isolation уже поддерживается code-side.

### Production infrastructure

Нужны domain/DNS/TLS, secret management, PostgreSQL/Redis persistence/topology, один Celery Beat, migration procedure и проверенный deploy/rollback.

### Monitoring и incident readiness

Нужно фактически подключить uptime `/health/ready`, alert destination, centralized logs/error triage и проверить delivery alert. Durable audit используется как источник incident investigation и коррелируется с request/system/payment/sync/lifecycle events.

### Backup/restore

Нужно включить регулярный encrypted off-host backup, retention и выполнить restore drill с измеренными RPO/RTO.

### Legal

Draft-тексты заменяются утверждёнными versioned documents: terms/offer, privacy, personal-data consent, credential policy, refund/cancellation policy, retention/deletion policy и реквизиты оператора. Нужен immutable archive опубликованных версий и production `LEGAL_EVIDENCE_HMAC_KEY`.

## Этап F — `1.0.0-rc.1`

RC допускается только после beta и закрытия внешних/эксплуатационных blockers. Полный RC smoke включает registration/verification/legal/demo, login/refresh/logout/recovery, lifecycle/support, реальный WB credential + full sync, dashboards, COGS/expenses/plan, реальный acquiring + paid activation/refund reconciliation, idempotency, monitoring, audit, off-host backup, restore drill и deploy/rollback evidence.

## Этап G — `1.0.0` Stable

Stable выпускается из проверенного RC, а не из новой функциональной ветки. Перед `v1.0.0` нет необработанных Critical/High security issues, необъяснённых финансовых расхождений и release-blocking RC defects; audit retention/archive policy утверждена; backup/rollback доказаны; legal documents non-draft; CHANGELOG/release notes финальны; stable evidence manifest сохранён; exact commit получает `VERSION=1.0.0` и immutable tag `v1.0.0`.

## Ownership

Внутри репозитория закрыты P31 lifecycle, P32 registration/beta-smoke, P33 production-config, P34 evidence-contract, P35 data-accuracy completeness, P36 systemd deployment, P37 audit, P38/P39 verified identity/mail и последующие P41–P44 acceptance blockers (staff UX, user lifecycle administration, RuSender HTTPS transport, recovery/UI hardening). Текущая code-side работа — P40 acceptance tooling и только исправление дефектов, найденных фактическим acceptance.

Внешние действия владельца/инфраструктуры: domain/TLS, реальный mail provider + disposable/catch-all test mailbox, WB partner/seller credentials/limits, merchant credentials/refund procedure, legal approval/requisites/retention, alert/logging/object-storage providers и фактическое выполнение production-like deployment/smoke.

Внешний blocker не останавливает безопасное hardening tooling, но без фактического закрытия нельзя выдавать beta/RC/stable в обход gate.

## Каноническая последовательность

`0.9.0-alpha.11` (`main` baseline) -> `0.9.0-beta.1` exact candidate в `dev` -> P40 production-like acceptance/evidence -> promotion/tag `v0.9.0-beta.1` -> `1.0.0-rc.1` -> `1.0.0`.

Связанные документы: `RELEASE_SMOKE.md`, `DATA_ACCURACY_ACCEPTANCE.md`, `RELEASE_EVIDENCE.md`, `ACCOUNT_LIFECYCLE.md`, `SYSTEMD_DEPLOYMENT.md`, `VERSIONING.md`, `RELEASE_READINESS.md`.
