# История изменений WB Insight

Все записи ведутся на русском. Детальная техническая летопись с PR/SHA находится в [`docs/VERSION_HISTORY.md`](docs/VERSION_HISTORY.md), правила версионирования — в [`docs/VERSIONING.md`](docs/VERSIONING.md).

Версии до введения формальной release-policy 15 сентября 2026 года реконструированы по истории `main` и не означают существование соответствующих Git tags.

## [0.9.0-alpha.8] — кандидат, 2026-09-15

P31 — безопасный жизненный цикл аккаунта и support-процедуры перед beta.

- добавлен password recovery через одноразовую ссылку и подтверждённый email-канал;
- reset token генерируется криптографически случайным, а в PostgreSQL хранится только SHA-256 digest; старые и использованные ссылки инвалидируются;
- публичный reset request не раскрывает существование аккаунта, а недоставленный email откатывает созданный token;
- login/access/refresh JWT привязаны к durable `session_version`; смена пароля, отзыв сессий, деактивация и повторная активация делают старые токены недействительными;
- refresh-cookie по-прежнему управляется единым `core.session_cookie`, legacy cookie rewriting удалён;
- пользователь может отключить продление только платной `ACTIVE`-подписки; доступ сохраняется до конца оплаченного периода, demo не маскируется под платное автопродление;
- пользователь получил отдельный экран безопасности с recovery и подтверждаемой soft-deactivation;
- soft-deactivation немедленно закрывает доступ, отзывает marketplace credentials, инвалидирует reset-ссылки и ставит остановку продления, но не выполняет необратимый hard purge;
- технический retention после деактивации конфигурируется отдельно; окончательный срок остаётся зависимым от утверждённой legal/retention policy;
- control-panel получил явную admin-защиту lifecycle routes, отзыв сессий, reactivation и просмотр append-only lifecycle events;
- support может фиксировать только разрешённые access/payment/refund review events с actor/reference без прямого редактирования production DB;
- поздний успешный Sber callback для уже деактивированного пользователя сохраняет правдивый `SUCCEEDED` payment, но не создаёт новую подписку автоматически; случай остаётся в audit trail для reconciliation/refund;
- SMTP/recovery настройки fail-closed и password reset по умолчанию отключён до фактической настройки и smoke провайдера;
- добавлены regression tests lifecycle/session/payment invariants и Alembic migration `c8e5f1a2b934`.

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

- `0.9.0-beta.1` — feature freeze + реальный production-like deployment/core smoke + SMTP recovery smoke + data-accuracy acceptance;
- `1.0.0-rc.1` — real WB/Sber/prod/legal/ops gates;
- `1.0.0` — публичный stable WB Insight Web v1 из проверенного RC.

Полный план: [`docs/RELEASE_ROADMAP.md`](docs/RELEASE_ROADMAP.md).
