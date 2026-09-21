# История изменений WB Insight

Все записи ведутся на русском. Детальная техническая летопись с PR/SHA находится в [`docs/VERSION_HISTORY.md`](docs/VERSION_HISTORY.md), правила версионирования — в [`docs/VERSIONING.md`](docs/VERSIONING.md).

Версии до введения формальной release-policy 15 сентября 2026 года реконструированы по истории `main` и не означают существование соответствующих Git tags.

## [0.9.0-beta.1] — candidate, обновлено 2026-09-21

Подготовлен exact beta candidate для P40 production-like acceptance. Эта запись фиксирует candidate metadata; публикация `v0.9.0-beta.1` остаётся заблокированной до полного green P40 evidence.

- завершён code-side P40 hardening: production nginx `/api` routing, strict release-smoke provenance и cleanup authenticated sessions;
- live-WB/data provenance связывает credential validation/cleanup с тем же seller account и защищённым data-accuracy input;
- добавлен условный Sber sandbox merchant proof без сохранения merchant secrets/order/form URL в evidence;
- role-aware staff workspace отделяет рабочие приоритеты super_admin/admin/manager/support/analyst от seller dashboard; обычный клиент не получает Control Panel;
- расширено администрирование пользователей: профиль/контакты/staff-атрибуты, ручная email-верификация, activation/deactivation и revoke sessions с lifecycle/audit evidence;
- transactional mail получил нативный RuSender HTTPS provider: encrypted bearer token, provider idempotency/retry classification, Control Panel selector и тест отправки без зависимости от SMTP-портов хостинга;
- password recovery доведён до production flow: anti-enumeration, resend throttle, durable idempotency, digest-only one-time token, browser URL cleanup и session-version rotation;
- Control Panel приведён к единому responsive UI pattern для overview/users/user-detail/roles/tariffs/payments/mail/audit, включая light/dark/reduced-motion и доступные segmented/filter controls;
- UX acceptance расширен на role-aware staff states, lifecycle user-detail states и RuSender gateway; Release integrity теперь self-test-ит этот контракт;
- добавлен provider-neutral IMAP helper для real-mail acceptance: credentials только через environment, mailbox read-only, наружу выдаётся только URL с `#token=`;
- dev-first release flow закреплён: рабочие ветки идут в `dev`, а `main` принимает только release/release-candidate promotion;
- self-hosted CI переведён на consolidated validation и защищён от повторного накопления PostgreSQL anonymous volumes/CI images;
- frontend package metadata и lockfile синхронизированы с каноническим `VERSION`.

До фактического release обязательны consolidated exact-head CI, production-like deploy/rollback, real RuSender verification/recovery lifecycle, WB seller/data-accuracy, staff/client UX, secrets и backup/restore evidence, затем complete beta manifest.

## [0.9.0-alpha.11] — 2026-09-16

P34 — закрытие разрыва между beta readiness и release-evidence contract. PR #53, merge `2b0ce4522adda642f6af8fa78b30e5440a7469be`.

- beta manifest больше не может считаться полным только по `ci + core_smoke + data_accuracy`;
- обязательный beta evidence set синхронизирован с дорожной картой: `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`;
- RC наследует весь beta-набор и добавляет `wb_full_sync`, `sber_payment`, `operations`, `backup_restore`, `legal`; stable наследует RC и добавляет `rc_signoff`;
- release stage теперь связан с канонической версией: beta требует `*-beta.N`, RC — `*-rc.N`, stable — версию без prerelease suffix;
- `--commit` обязан быть полным 40-символьным Git SHA, environment — непустым;
- неизвестные и пустые evidence artifacts отклоняются;
- `data_accuracy` проверяется как machine-readable schema v1 со `status=pass`, ненулевыми periods/metrics и SHA-256 входа/policy;
- manifest schema поднята до v2;
- Release integrity содержит positive/negative contract tests для полного beta-набора, старого неполного набора, неверного SHA, alpha-version, пустого artifact и failing data-accuracy evidence;
- `RELEASE_EVIDENCE.md`, roadmap, readiness и versioning синхронизированы с фактическим contract.

Финальный exact head P34 `0d0d3d6c7c9f17f569f816bd79d9577b7fc226e6` прошёл Backend security, Frontend build, Database migrations и Release integrity.

Дополнительный hardening той же `alpha.11` baseline:

**P36 — systemd deployment hotfix. PR #55, merge `d4c8a20d6ecc75ab9cd8449bd55f6b2ce4242d9c`.**

- добавлен `ops/update_systemd.sh` для безопасного обновления Ubuntu/systemd deployment;
- updater fail-closed проверяет Python 3.12 и Node `^20.19` или `>=22.12` до изменения окружения;
- полный update требует clean Git tree и fast-forward-only `main`;
- backend разворачивается в fresh Python 3.12 venv, затем выполняются requirements, Alembic, frontend `npm ci`/build, controlled venv swap, restart backend/Celery/Beat и readiness check;
- предыдущий venv сохраняется для диагностики;
- добавлены `--preflight-only`, CI workflow `systemd-updater` и `docs/SYSTEMD_DEPLOYMENT.md`.

**P35 — обязательное data-accuracy coverage. PR #56, merge `d2e782208228fbe60cb92b9e61fbf8d325f0e839`.**

- каждая policy-required метрика теперь обязана присутствовать в каждом acceptance-периоде;
- пропущенная обязательная метрика становится `missing` и блокирует acceptance;
- input не может понизить обязательность через `required:false`;
- любое изменение tolerance/mode относительно policy требует `override_reason`;
- отчёт фиксирует required metric/observation counts и причины overrides;
- Release integrity проверяет passing, failing, incomplete, required-downgrade и tolerance-override scenarios;
- exact P35 head `7e88182533f7d3a8baf813bcaeeb19d7442db0d3` прошёл Release integrity полностью зелёным.

P35 и P36 не добавляют новую runtime capability и поэтому не создают отдельный product version: они усиливают существующий `0.9.0-alpha.11` pre-beta baseline. Beta всё ещё требует фактических production-like deployment/rollback, SMTP/lifecycle, UX/secrets review и real-seller data-accuracy evidence.

## [0.9.0-alpha.10] — 2026-09-16

P33 — fail-closed production configuration перед beta. PR #51, merge `9dacaee426937c7466ac22cedd878e11b53cc472`.

- добавлен единый production preflight, который запускается при импорте `settings` и поэтому одинаково защищает API, Celery worker/beat и Alembic;
- production больше не стартует с `DEBUG=true`, HTTP base URL/origin, зарезервированными `example.com/.org/.net` hostnames или `replace-with-*` endpoints;
- запрещены известные слабые/шаблонные DB/JWT/WB/Sber secrets; для production DB password требуется минимум 16 символов, для JWT secret — минимум 32;
- `API_TOKEN_ENCRYPTION_KEY` валидируется как реальный Fernet key до запуска приложения;
- `LEGAL_EVIDENCE_HMAC_KEY` стал отдельным обязательным production secret длиной минимум 32 символа; шаблонный ключ больше не может незаметно использоваться для consent evidence;
- при включённом Sber acquiring production требует реальные HTTPS gateway/return/fail URLs и неплейсхолдерные merchant credentials;
- при включённом password recovery production отклоняет example/reset URL, example SMTP host/sender, отключённый STARTTLS и шаблонные SMTP credentials;
- `.env.production.example` теперь явно помечен как намеренно неготовый к запуску до замены placeholders;
- Release integrity проверяет отрицательный contract: неизменённый production template обязан fail-closed, а CI-only безопасный набор должен успешно импортировать полный FastAPI app;
- добавлены regression tests на core production preflight, Sber и lifecycle/SMTP validation.

P33 прошёл exact-head green CI по Backend security, Frontend build, Database migrations и Release integrity. Он не означает прохождение beta-gates: production-like HTTPS deployment, реальный SMTP delivery smoke, WB seller data-accuracy acceptance и полный beta evidence manifest должны быть подтверждены фактически.

## [0.9.0-alpha.9] — 2026-09-16

P32 — надёжная регистрация и автоматизированный disposable beta-smoke. PR #49, merge `7206df554e6f98c2533160385d9ad7d27c704268`.

- исправлен реальный demo-onboarding bug: `TariffPlan.code` канонически использует lowercase `demo`, а `create_demo_subscription()` больше не ищет несовместимый `DEMO`;
- `insert_user()` больше не проглатывает ошибку `flush()`: DB failure передаётся владельцу request-транзакции и не оставляет `AsyncSession` в скрытом failed-state;
- registration handler явно откатывает `IntegrityError` и возвращает стабильный `409 REGISTRATION_CONFLICT` без утечки деталей БД;
- ошибка создания базовой роли `user` теперь откатывает регистрацию целиком, вместо частично созданного аккаунта;
- регистрация пользователя, роль, immutable legal consent evidence и demo subscription остаются единым транзакционным сценарием;
- добавлен authenticated read-only `GET /legal/consents/me`, возвращающий только пользовательскую consent-аудит информацию без `ip_hmac`/`user_agent_hmac`;
- `ops/release_smoke.py` по умолчанию создаёт disposable user, принимает актуальные registration documents, проверяет активную demo subscription и точные сохранённые document version/SHA-256;
- disposable smoke дополнительно доказывает cookie-only refresh restore, soft-deactivation, отсутствие refresh после деактивации и запрет повторного login для inactive account;
- disposable account использует отдельный HTTP client и автоматически деактивируется после проверки; credentials/session values не печатаются;
- добавлены regression tests на propagation DB failure, rollback duplicate/role failure, lowercase demo lookup и privacy-safe consent API;
- `--skip-disposable-registration`/`SMOKE_SKIP_DISPOSABLE_REGISTRATION` оставлены только как явный escape hatch для специализированных прогонов.

P32 усиливает code-side beta acceptance baseline, но **не означает прохождение beta-gates**: production-like HTTPS deployment, реальный SMTP recovery smoke, WB seller data-accuracy acceptance и полный beta evidence manifest по-прежнему должны быть выполнены фактически.

## [0.9.0-alpha.8] — 2026-09-15

P31 — безопасный жизненный цикл аккаунта и support-процедуры перед beta. PR #47, merge `6cb34aa9b4633e20d1810b6a5edd690056cde986`.

- добавлен password recovery через одноразовую ссылку и подтверждённый email-канал;
- reset token генерируется криптографически случайным, а в PostgreSQL хранится только SHA-256 digest; старые и использованные ссылки инвалидируются;
- raw reset token передаётся во frontend через URL fragment `#token=...`, поэтому nginx/HTTP access logs не получают секрет в request URI;
- публичный reset request не раскрывает существование аккаунта, а недоставленный email откатывает созданный token;
- production password recovery fail-closed требует HTTPS reset URL и `SMTP_STARTTLS=true`; SMTP TLS использует системную проверку сертификата;
- login/access/refresh JWT привязаны к durable `session_version`; смена пароля, отзыв сессий, деактивация и повторная активация делают старые токены недействительными;
- refresh-cookie по-прежнему управляется единым `core.session_cookie`, legacy cookie rewriting удалён;
- пользователь может отключить продление только платной `ACTIVE`-подписки; доступ сохраняется до конца оплаченного периода, demo не маскируется под платное автопродление;
- пользователь получил отдельный экран безопасности с recovery и подтверждаемой soft-deactivation;
- soft-deactivation немедленно закрывает доступ, отзывает marketplace credentials, инвалидирует reset-ссылки и ставит остановку продления, но не выполняет необратимый hard purge;
- технический retention после деактивации конфигурируется отдельно; окончательный срок остаётся зависимым от утверждённой legal/retention policy;
- late Sber callback и account deactivation сериализованы через блокировку строки пользователя: платёж сохраняет правдивый `SUCCEEDED`, но деактивированный аккаунт не получает новую подписку из race-condition;
- control-panel получил явную admin-защиту lifecycle routes, отзыв сессий, reactivation и просмотр append-only lifecycle events;
- обычный `admin` не может выполнять security-sensitive reactivation/revoke-sessions над `super_admin`; такие действия требуют `super_admin`;
- support может фиксировать только разрешённые access/payment/refund review events с actor/reference без прямого редактирования production DB;
- `/account/*` добавлен в production same-origin nginx gateway и закреплён container smoke-проверкой;
- password reset по умолчанию отключён до фактической настройки и smoke SMTP-провайдера;
- добавлены regression tests lifecycle/session/payment/RBAC/transport invariants и Alembic migration `c8e5f1a2b934`;
- Alembic model registry и migration comments синхронизированы с ORM, чтобы `alembic check` не допускал schema drift.

P31 закрывает code-side baseline account lifecycle, но не объявляет beta: до `0.9.0-beta.1` всё ещё нужны реальный production-like HTTPS deployment, SMTP smoke, core release smoke, WB seller data-accuracy acceptance и полный beta evidence manifest.

## [0.9.0-alpha.7] — 2026-09-15

P30 — beta-readiness acceptance tooling и release evidence. PR #46, merge `77f1ec19cbe565cdbaca2a65a2c4cd7d5199ff5f`.

- добавлена versioned policy сверки ключевых WB Web v1 метрик;
- денежные значения сравниваются через `Decimal`, без ошибок float-округления;
- поддерживаются absolute/relative/either/both tolerance modes;
- обязательное отсутствующее значение и превышение tolerance блокируют acceptance;
- `ops/data_accuracy_acceptance.py` формирует машинный JSON и Markdown-отчёт с SHA-256 входа и policy;
- добавлены положительный и отрицательный CI fixtures, чтобы runner не мог «всегда проходить»;
- `ops/release_evidence.py` связывает stage, exact commit, version, environment и SHA-256 evidence artifacts;
- определены обязательные evidence kinds отдельно для beta, RC и stable;
- Release integrity получил отдельный `acceptance-tools` job с positive/negative contract tests;
- изменение корневого `VERSION` теперь автоматически запускает Backend security и Database migrations, поэтому release-candidate head всегда проходит полный backend/migration gate;
- добавлены `docs/DATA_ACCURACY_ACCEPTANCE.md` и `docs/RELEASE_EVIDENCE.md`;
- P30 намеренно не назначает beta: `0.9.0-beta.1` разрешена только после фактического production-like smoke и реальной data-accuracy сверки.

## [0.9.0-alpha.6] — 2026-09-15

P29 — dependency/security hardening и полная ревизия документации. PR #44, merge `6a4e754738617085a22e540a84b5c8ee5e0854d1`.

- frontend dependency tree обновлён после фактического security audit;
- Axios переведён на исправленную release line `^1.18.0`;
- удалён ошибочно включённый в browser dependencies пакет `node`;
- безопасные transitive versions закреплены для `follow-redirects`, `form-data`, `nanoid` и `postcss`;
- CI проверяет production и полный frontend dependency tree через `npm audit`;
- backend CI дополнен `pip-audit` production requirements;
- первый backend audit выявил проблемы в `cryptography`, `ecdsa`, `pyasn1`, `python-dotenv`, `starlette`;
- цепочка `python-jose -> ecdsa` удалена, HS256 JWT переведён на PyJWT;
- FastAPI/Starlette, cryptography и python-dotenv обновлены до исправленных веток;
- итоговый backend audit: `No known vulnerabilities found`;
- route tests переведены с внутренних структур FastAPI на публичный OpenAPI contract;
- nginx container smoke получил bounded backend-readiness retry;
- временный self-write lockfile flow отключён, постоянный frontend CI read-only;
- документация перестроена в единый `docs/`-портал;
- root README/SETUP и история версий приведены к фактическому состоянию;
- до beta закреплён обязательный data-accuracy gate.

## [0.9.0-alpha.5] — 2026-09-15

P28 — browser-session hardening и release smoke. PR #43, merge `351cbcd7129c69959e138918b1d621a6475af210`.

- access JWT перенесён из persistent browser storage в память приложения;
- session после reload восстанавливается через HttpOnly refresh-cookie;
- refresh возвращает новый access token и безопасный user snapshot;
- concurrent 401 используют единый refresh flow;
- frontend CI запрещает persistent access-token storage;
- production API fallback переведён на same-origin;
- nginx gateway дополнен `/billing` и `/legal`;
- release-integrity проверяет маршрутизацию на реально запущенном frontend container;
- добавлены backend session-restore regression tests;
- добавлены `ops/release_smoke.py` и `docs/RELEASE_SMOKE.md`.

## [0.9.0-alpha.4] — 2026-09-15

P27 — versioned legal documents и consent evidence. PR #42, merge `591b3919eb80403a7e4225382d996dca63b8c039`.

- backend registry legal documents с `code`, `version`, SHA-256;
- публичные legal requirements/documents API и страницы;
- immutable `legal_consents`;
- backend enforcement регистрации, billing и marketplace connection;
- privacy-minimized technical evidence;
- закрыт legacy credential-add bypass;
- тексты намеренно остаются draft до внешнего legal approval.

## [0.9.0-alpha.3] — 2026-09-15

P26 — operations hardening. PR #41, merge `76ee8651298fff99b8bf6a11921dcbfbf0916c46`.

- operational health, stale/failed sync и lease checks;
- credential/service-secret expiry monitoring;
- HTTP/5xx telemetry и deduplicated alerts;
- encrypted PostgreSQL backup/restore и isolated drill;
- реальный backup/restore CI roundtrip;
- исправлен production refresh-cookie contract и удалён legacy GET refresh.

## [0.9.0-alpha.2] — 2026-09-15

P25 — version governance и production deployment. PR #40, merge `8cad1f098ae63c813ed36aad2c462d196484153a`.

- root `VERSION` стал source of truth;
- формализованы SemVer и `alpha -> beta -> rc -> stable` gates;
- production Docker images и Compose topology;
- same-origin nginx gateway;
- deployment/upgrade/rollback runbook;
- release-integrity CI.

## [0.9.0-alpha.1] — 2026-09-15

P19–P24, PR #34–#39 — release-hardening baseline.

- WB credential compliance и JWT metadata validation;
- marketplace adapter foundation;
- credential identity/encryption foundation;
- WB production permissions/read-only/service policy и live validation;
- health/release-readiness baseline;
- Sber acquiring с idempotency и server-side confirmation.

## [0.8.0-alpha.1] — 2026-09-15

P14–P18, PR #29–#33 — feature-complete WB analytics alpha.

- единый Dashboard UX без demo KPI;
- seller settings;
- Inventory Risk/Replenishment;
- Price Monitoring;
- Finance/Reconciliation.

## [0.7.0-alpha.1] — 2026-09-15

P8–P13, PR #23–#28 — semantic/business layer.

- unified metrics semantics;
- multi-account scope;
- корректная Unit Economy;
- monthly revenue plans;
- Paid Storage;
- historical COGS и seller expenses.

## [0.6.0-alpha.1] — 2026-09-14

P5–P7, PR #20–#22 — operational/marketing fact layer.

- orders;
- sales/returns;
- advertising;
- product funnel;
- durable source cursors/rolling refresh.

## [0.5.0-alpha.1] — 2026-09-14

P0–P4, PR #15–#19 — production-safety и durable sync foundation.

- auth/RBAC/security baseline;
- account-scoped sync;
- WB transport hardening;
- актуальные API contracts;
- durable jobs с lease/checkpoint/recovery;
- migration/test CI baseline.

## [0.4.0-alpha.1] — 2026-05-07

PR #14 — консолидация БД/требований и подготовка к production-аудиту.

## [0.3.0-alpha.1] — 2026-05-06

PR #8–#12 — ранняя WB-синхронизация и рекламный контур. PR #13 закрыт без merge.

## [0.2.0-alpha.1] — 2026-05-05

PR #4–#7 — первые полезные расчёты и Unit Economy.

## [0.1.0-alpha.1] — 2026-03-30

PR #1 — первый воспроизводимый backend/frontend baseline. PR #2/#3 закрыты без merge.

---

## Следующие release stages

- `0.9.0-beta.1` — feature freeze + реальный production-like deployment/core smoke + SMTP recovery smoke + UX/secrets review + data-accuracy acceptance;
- `1.0.0-rc.1` — real WB/Sber/prod/legal/ops gates;
- `1.0.0` — публичный stable WB Insight Web v1 из проверенного RC.

Полный план: [`docs/RELEASE_ROADMAP.md`](docs/RELEASE_ROADMAP.md).
