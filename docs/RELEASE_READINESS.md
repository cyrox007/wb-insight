# WB Insight — Release Readiness

Дата ревизии: 22 сентября 2026 года.

## Текущий статус

- release baseline `main`: **`0.9.0-alpha.11`**; exact beta candidate в `dev`: **`0.9.0-beta.1`**.
- P31–P36 release-hardening baseline закрыт.
- P37 durable audit trail закрыт PR #74, merge `31434c26e98960c0f591bdcb969ba12d96af8263`.
- payment administration foundation закрыт PR #71, merge `e42c691eaa2f75d7149e78222ae605d039f2eabd`.
- P38/P39 verified email identity + durable/provider-neutral mail delivery закрыты PR #77, merge `5733ebd2b74a2947ce583dfa78734bdeb1335357`.
- P41 role-aware staff workspace и расширенное управление пользователями закрыты PR #119.
- P42 RuSender HTTPS transactional mail закрыт PR #120, merge `cf11b3c60cb24b74ce7dd9f1dc615bca6848343f`.
- P43 password recovery hardening закрыт PR #121, merge `560322d264bde219338498cdb076e920de2ab9c9`.
- P44 Control Panel UI/RBAC UX unification закрыт PR #122, merge `f9d775e25a49df765d7839b42bcd15f8b60976e1`.
- P47 DB-first mail bootstrap + auth-mail readiness diagnostics закрыт PR #125, merge `cf40d2738a3ac9028936a7c6a65e35e9fd6811fe`.
- P48 backend release warning cleanup закрыт PR #126, merge `aafac5564c4d4b1dcbb708f5787df56f8e499061`.
- P49 release-smoke mail gateway preflight закрыт PR #127, merge `46e08f966b0862dc523de718e4a20bc49eea3bdb`.
- P50 role-aware staff profile закрыт PR #128, merge `0118ce67e4bf79e7cbdffd285381ed48e668a991`.
- P52 staff operational attention закрыт PR #130, merge `59e186bb4c802adae243327d1499422a916956d8`.
- P53 safe RuSender machine diagnostics закрыт PR #131, merge `5ecbf3039d4b1d41404f0eecc73f36647130d331`.
- P54 client-health separation закрыт PR #132, merge `1e741cee7561aee8f4e118954009658cd9e31636`.
- P55 lifecycle admin target guards закрыты PR #133, merge `1c65c049d8a3731bfd957efa03b73371d9f40169`.
- P56 server-side user search/filter/pagination закрыт PR #134, merge `41fc7a6792d6395c5af4914613920d1dc9d57332`.
- P57 true fail-fast mail preflight ordering закрыт PR #135, merge `9c2e6b21a56bfa7e22d08d439f018bf8533eae88`.
- P58 mandatory mail readiness proof в beta evidence закрыт PR #136, merge `2626dc8a829a7de657d1d1098665acae6dba1add`.
- P59 strict RuSender evidence binding закрыт PR #137, merge `be242c71f5d52c1bd84af4b6f7b8a4d0a3af76a7`.
- P60 password-reset throttle + old-session revocation proof закрыт PR #138, merge `569547acaa3d12ed808bc906703ec2869f39c532`.
- P61 fail-closed beta smoke mode закрыт PR #139, merge `8f5f001bb4f8321e31cc50f96627e84025e39eb2`.
- P70 первичная синхронизация и очистка устаревшего кода закрыты PR #149, merge `e90960e98be2519b15e2889706400eef05b57a5f`.
- P71 отображение свежести синхронизации закрыто PR #150, merge `323c60d6ebfb09c41e8dea8020ac43177204bdde`.
- P72 непрерывная аналитика при фоновой синхронизации закрыта PR #151, merge `2ba177c920618ddb272246982d7a6553e6c16df7`.
- P73 понятные статусы подключений Wildberries закрыты PR #152, merge `5cac7b910fd17b7f598e7f9a7b1bd77ec0498bde`.
- P74 изоляция кэша кабинетов между сессиями закрыта PR #153, merge `a8dbea2ace821cbc9f4f3009e27e927a9d4fdb6b`.
- P75 транзакционная граница удаления WB-подключения закрыта PR #155, merge `c01aca53bc976d7cc2fc5c72c311fe5b2b77133e`.
- P76 русский системный контракт runtime-ядра закрыт PR #156, merge `beb653830cdba48dbb988ad81ae5da60a512c457`.
- основной WB Web v1 feature scope **заморожен**;
- текущий release stage — **P40 / issue #78: production-like beta acceptance и evidence closure**;
- candidate VERSION уже поднят до `0.9.0-beta.1`, но публикация/tag разрешены только после фактического P40 acceptance на exact `dev` commit.

## Code-side status: baseline закрыт; новая интеграция идёт через dev

- auth/session/RBAC, роли и Control Panel;
- role-aware staff workspace `/staff` для super_admin/admin/manager/support/analyst с least-privilege backend permissions;
- account-scoped durable WB sync;
- безопасная сводка свежести синхронизации по сущностям и выбранным кабинетам; первичная синхронизация отображается как выполняющаяся, а не как `NOT_SYNCED`;
- повторная синхронизация не скрывает последние успешно сохранённые показатели; общий статус свежести доступен во всех разделах аналитики продавца через лёгкий маршрут только для чтения;
- профиль и пустое состояние аналитики различают безопасные причины недоступности WB-подключения: отозвано, истёк срок, отключено или превышен лимит тарифа; добавление и удаление немедленно обновляют общий список кабинетов;
- кэш кабинетов изолирован между пользовательскими сессиями; сброс сессии очищает выбранный кабинет и блокирует применение поздних ответов предыдущего пользователя;
- ошибки записи БД при удалении WB-подключения не скрываются: транзакционная граница запроса выполняет откат, а общий обработчик `500` возвращает безопасное русское сообщение без деталей исключения;
- системные сообщения и документационные строки ядра БД, авторизации, доступа к WB-кабинетам и семантических метрик приведены к русскому системному контракту;
- общая интеграционная граница, mail adapters и Sber client используют русские комментарии/docstring и человекочитаемые ошибки без изменения машинных кодов внешних провайдеров;
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
- password reset/recovery через durable transactional mail, resend throttling и idempotency;
- digest-only reset/verification tokens, raw secrets только в URL fragment; reset token удаляется из browser URL/history сразу после capture;
- durable `session_version`, paid cancel-at-period-end/undo, self-service soft deactivation;
- durable append-only P37 audit trail + Control Panel «Аудит»;
- P38 email verification: new account login/demo gated by ownership proof when enabled;
- безопасная смена email через `pending_email`, session/reset invalidation после подтверждения;
- provider-neutral mail registry: SMTP + RuSender HTTPS transactional adapter;
- `MAIL_CONFIG_SOURCE=auto` использует DB-first runtime selection: placeholder ENV fallback не блокирует bootstrap реального encrypted provider, но fail-closed отклоняется, если реально становится effective;
- Control Panel mail gateway отдельно показывает readiness транспорта, email verification и password recovery;
- durable Celery mail outbox с retry/backoff/idempotency;
- campaign draft/preview/test/immediate/scheduled launch/cancel, segmentation, suppression и delivery history;
- campaign scheduling с row lock/due-time recheck и retry-safe materialization;
- mail failure-rate/stale-queue operational checks;
- Control Panel «Рассылки» с фильтрами/pagination/scheduling и выбором SMTP/RuSender transport;
- расширенная карточка пользователя: профиль, staff-атрибуты, ручная email-верификация, activation/deactivation и revoke sessions с audit/lifecycle evidence;
- единый responsive Control Panel UI pattern для overview/users/user-detail/roles/tariffs/payments/mail/audit;
- staff account profile скрывает seller-only тариф/WB/COGS/expenses controls; seller analytics остаётся отдельным secondary workspace;
- staff workspace содержит только permission-scoped operational attention; user/mail/payment/system агрегаты выдаются только при соответствующих backend permissions;
- client health отделён от внутренних staff accounts, чтобы операционные метрики не смешивали сотрудников и клиентов;
- Control Panel users использует server-side search/filter/pagination вместо unbounded full-list loading;
- admin lifecycle target guards защищают super_admin и запрещают случайную self-deactivation оператора через Control Panel;
- RuSender gateway/test diagnostics используют только bounded machine-readable provider error code без raw provider body/description;
- mail readiness preflight выполняется до disposable registration/inbox wait и оставляет sanitized provider/readiness metadata в structured smoke evidence;
- strict P40 evidence pin'ит expected/observed mail provider к RuSender без credentials/Key ID/sender address;
- password-reset production-like smoke доказывает resend throttle/idempotent queue materialization и `session_revoked` для ранее выданного access JWT;
- `ops/release_smoke.py --beta-gate` fail-closed валидирует обязательные P40 inputs до первого сетевого запроса;
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

## Promotion flow для `0.9.0-beta.1`

Рабочие ветки вливаются только в `dev`. После завершения code-side набора на exact `dev` head вручную запускается consolidated CI, затем на этом же candidate commit собирается production-like acceptance/evidence. Только green candidate продвигается отдельным `dev -> main` release PR; promotion не должен добавлять функциональные изменения.

## Gate до `0.9.0-beta.1`

Beta разрешена только после:

- feature freeze и отсутствия известных необработанных code-side release blockers;
- production-like HTTPS deployment с реальными non-placeholder secrets/hosts;
- миграций clean DB + upgrade копии существующей БД;
- deploy/rollback smoke;
- полного `ops/release_smoke.py --beta-gate` без `--skip-disposable-registration`; до первого HTTP-запроса strict mode должен подтвердить обязательные P40 inputs, а authenticated mail preflight — expected/observed `rusender` и readiness verification/recovery;
- **реального email verification smoke** на deliverable disposable/catch-all адресе через текущий RuSender HTTPS transactional provider;
- demo activation только после verification ownership proof;
- **реального password reset** через тот же provider: два немедленных request сохраняют одинаковый anti-enumeration response и материализуют ровно одну durable reset-mail row; старый access JWT после reset получает `session_revoked`; затем login новым паролем восстанавливает ту же identity;
- login/refresh-cookie restore/logout/deactivation;
- representative durable P37 audit correlation по request id;
- desktop/mobile UX для client screens, role-aware staff workspace и Control Panel overview/users/user-detail/roles/tariffs/payments/audit/mail; обязательны состояния inactive/unverified user и RuSender gateway;
- secrets review frontend bundle/git/logs/audit/mail/payment metadata;
- real-seller data-accuracy минимум на трёх фиксированных периодах: все required metrics, `missing=0`, нет необъяснённых существенных денежных расхождений; protected input и passing report должны быть связаны с тем же live-validated WB account через `wb-live-data` proof;
- каждый tolerance override имеет `override_reason` + review evidence;
- backup + isolated restore evidence;
- полного beta manifest v2 для exact `0.9.0-beta.N` candidate.

До включения реальной почты `EMAIL_VERIFICATION_ENABLED=false` и `MAIL_DELIVERY_ENABLED=false` остаются безопасными deployment defaults; это позволяет выкатывать код/миграции без внезапной блокировки текущих пользователей, но **не закрывает beta acceptance**. Для P40 canonical invocation используется `--beta-gate`, который такие неполные условия не пропускает.

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
