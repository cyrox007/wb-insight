# WB Insight — подробная история версий

Дата полной ревизии: 16 сентября 2026 года.

Документ фиксирует продуктовые milestones, а не каждый commit. Версии до введения formal release policy являются ретроспективно реконструированными и не означают наличие соответствующего Git tag.

## 0.1.0-alpha.1 — реконструкция проекта

**Mainline:** PR #1. PR #2/#3 закрыты без merge.

Первый воспроизводимый backend/frontend baseline и основа будущей WB-интеграции.

## 0.2.0-alpha.1 — первая Unit Economy

**Mainline:** PR #4–#7.

Появились первые расчёты по WB reports и самостоятельный контур unit-экономики.

## 0.3.0-alpha.1 — sync и реклама

**Mainline:** PR #8–#12. PR #13 не слит.

Синхронизация WB получила первые recovery-fixes, добавлены advertising data/backend/frontend.

## 0.4.0-alpha.1 — консолидация БД и требований

**Mainline:** PR #14.

Уточнены persistence/schema требования и подготовлен системный production-аудит.

## 0.5.0-alpha.1 — P0–P4: production safety и durable sync

**Mainline:** PR #15–#19.

- auth/refresh/RBAC hardening;
- server-side tariff/account checks;
- secrets перестали возвращаться frontend;
- account-scoped `SyncJob`/`UserSyncState`;
- Redis rate limiting и bounded retries;
- актуализация WB API contracts;
- durable jobs с lease/checkpoint/crash recovery;
- Alembic/CI baseline.

## 0.6.0-alpha.1 — P5–P7: operational/marketing facts

**Mainline:** PR #20–#22.

Orders, sales/returns, Promotion API advertising, product funnel и retention/rolling refresh semantics.

## 0.7.0-alpha.1 — P8–P13: semantic/business layer

**Mainline:** PR #23–#28.

Unified metrics, multi-account scope, corrected Unit Economy, monthly plans, paid storage, historical COGS и manual expenses.

## 0.8.0-alpha.1 — P14–P18: feature-complete WB analytics alpha

**Mainline:** PR #29–#33.

Dashboard UX, seller settings, Inventory Risk/Replenishment, Price Monitoring и Finance/Reconciliation без demo KPI.

## 0.9.0-alpha.1 — P19–P24: release-hardening baseline

**Mainline:** PR #34–#39.  
**Commit после P24:** `ff0d278c32f0a770dc0cdbc0cf0ab9d98c2377ca`.

WB credential compliance, marketplace adapter/credential foundation, production WB token policy/live validation, health/readiness и Sber acquiring.

## 0.9.0-alpha.2 — P25: version governance и deployment

**PR:** #40  
**Merge:** `8cad1f098ae63c813ed36aad2c462d196484153a`.

Root `VERSION`, SemVer gates, production Docker/Compose, same-origin nginx, deploy/upgrade/rollback и release-integrity CI.

## 0.9.0-alpha.3 — P26: operations hardening

**PR:** #41  
**Merge:** `76ee8651298fff99b8bf6a11921dcbfbf0916c46`.

Operational monitoring, credential expiry signals, HTTP/5xx telemetry, Celery alerting, encrypted PostgreSQL backup/restore/drill и secure refresh-cookie contract.

## 0.9.0-alpha.4 — P27: legal consent foundation

**PR:** #42  
**Merge:** `591b3919eb80403a7e4225382d996dca63b8c039`.

Versioned legal registry, public legal API/pages, immutable consent evidence и backend enforcement регистрации, billing и marketplace connection. Тексты остаются draft до внешнего legal approval.

## 0.9.0-alpha.5 — P28: browser-session hardening и release smoke

**PR:** #43  
**Merge:** `351cbcd7129c69959e138918b1d621a6475af210`.

Access JWT перенесён в память, session restore выполняется через HttpOnly refresh-cookie, concurrent refresh дедуплицирован, production API стал same-origin, nginx routing проверяется в CI, добавлен `ops/release_smoke.py`.

## 0.9.0-alpha.6 — P29: dependency security и документационная ревизия

**PR:** #44  
**Merge:** `6a4e754738617085a22e540a84b5c8ee5e0854d1`.

- frontend dependency tree очищен по реальному `npm audit`;
- удалён runtime package `node`, обновлён Axios и закреплены безопасные transitive versions;
- frontend CI постоянно проверяет production и full dependency tree;
- backend получил `pip-audit`;
- уязвимая цепочка `python-jose -> ecdsa` удалена, HS256 JWT переведён на PyJWT;
- FastAPI/Starlette, cryptography и python-dotenv обновлены до исправленных версий;
- итоговый production Python audit не нашёл известных vulnerabilities;
- route regression tests переведены на публичный OpenAPI contract;
- gateway smoke получил bounded backend readiness;
- документация проекта полностью перестроена в канонический `docs/`-портал.

`alpha.6` является первым baseline после P28, где frontend и backend dependency audits входят в обязательный CI gate.

## 0.9.0-alpha.7 — P30: beta acceptance tooling

**PR:** #46  
**Merge:** `77f1ec19cbe565cdbaca2a65a2c4cd7d5199ff5f`.

- versioned policy ключевых метрик WB Web v1 и их tolerances;
- deterministic `Decimal` comparator для expected/actual;
- machine-readable JSON и Markdown data-accuracy report;
- SHA-256 привязка отчёта к acceptance input и policy;
- positive/negative CI fixtures;
- release-evidence manifest, связывающий stage, exact commit, version, environment и hashes artifacts;
- отдельные evidence contracts для beta/RC/stable;
- CI self-test успешного и намеренно провального acceptance;
- изменение `VERSION` запускает backend security и database-migration gates.

P30 делает приёмку воспроизводимой, но сам по себе не является фактом прохождения production-like acceptance.

## 0.9.0-alpha.8 — P31: account lifecycle baseline

**PR:** #47  
**Merge:** `6cb34aa9b4633e20d1810b6a5edd690056cde986`.

P31 закрыл запланированные code-side lifecycle gaps:

- email password recovery с одноразовыми hashed reset tokens и anti-enumeration response;
- raw reset secret передаётся через URL fragment `#token=...`, поэтому HTTP/nginx access logs не получают его в request URI;
- production recovery fail-closed требует HTTPS reset URL и `SMTP_STARTTLS=true`, TLS использует системную проверку сертификата;
- durable `session_version` для немедленного отзыва access/refresh JWT;
- paid subscription cancel-at-period-end без обрыва оплаченного доступа;
- demo исключён из paid cancellation semantics;
- self-service soft deactivation с retention metadata;
- деактивация отзывает sessions, WB credentials и ранее выданные reset links;
- admin reactivation не восстанавливает старые marketplace credentials;
- lifecycle/support действия сохраняются в append-only audit events;
- support review/refund evidence доступно через allowlisted control-panel API без ручной правки production DB;
- late Sber callback и account deactivation сериализованы блокировкой строки пользователя: подтверждённый payment остаётся финансовым фактом, но inactive account не получает subscription из race-condition;
- обычный `admin` не может выполнять reactivation/revoke-sessions над `super_admin`; security-sensitive lifecycle mutation такого аккаунта требует `super_admin`;
- `/account/*` включён в production same-origin nginx gateway и проверяется container smoke-тестом;
- добавлены recovery/security UI и regression tests lifecycle/session/payment/RBAC/transport invariants;
- Alembic revision `c8e5f1a2b934` после `b7d4e6f8a921`; clean upgrade и metadata check прошли CI exact-head кандидата.

P31 не вводит автоматический hard purge и не объявляет юридически утверждённый retention/refund процесс: это остаётся внешним legal/operator gate.

## 0.9.0-alpha.9 — P32: registration и beta-smoke hardening

**PR:** #49  
**Merge:** `7206df554e6f98c2533160385d9ad7d27c704268`.

P32 появился не как плановая функциональная фаза, а после release-smoke ревизии `alpha.8`, которая обнаружила два code-side дефекта регистрации:

- `create_demo_subscription()` искал `TariffPlan.code == "DEMO"`, хотя ORM и исходная migration фиксируют канонический lowercase `demo`;
- `insert_user()` проглатывал DB flush exception и возвращал `None`, оставляя request `AsyncSession` в failed transaction перед автоматическим commit dependency.

Исправления P32:

- единый lowercase `demo` contract;
- DB persistence errors регистрации распространяются до transaction owner;
- `IntegrityError` явно rollback-ится и возвращает безопасный `409 REGISTRATION_CONFLICT`;
- ошибка назначения базовой роли откатывает регистрацию;
- роль, consent evidence и demo subscription остаются в одной request-транзакции;
- добавлен privacy-safe read-only endpoint собственных consent records без IP/User-Agent HMAC;
- release smoke автоматически выполняет disposable registration → demo → exact consent evidence → refresh → soft-deactivation → inactive login rejection;
- disposable smoke запускается по умолчанию и может быть отключён только явным escape hatch для специализированного прогона;
- cleanup временного аккаунта устойчив к частичному падению smoke;
- regression suite фиксирует transaction, demo-code и consent-privacy contracts.

P32 прошёл exact-head green CI по Backend security, Frontend build, Database migrations и Release integrity перед merge. Это подтверждает code-side baseline, но не является доказательством прохождения production-like smoke в целевом окружении.

## 0.9.0-alpha.10 — P33: fail-closed production configuration

**PR:** #51  
**Merge:** `9dacaee426937c7466ac22cedd878e11b53cc472`.

P33 появился после финального pre-beta code audit, который обнаружил, что production runtime формально мог стартовать с шаблонными или слабыми значениями из `.env.production.example`.

Исправления P33:

- единый production preflight запускается при импорте `settings`, поэтому применяется к API, Alembic и Celery-процессам;
- запрещены `DEBUG=true`, HTTP public URLs/origins, зарезервированные example-hosts и `replace-with-*` endpoints;
- production DB/JWT/WB/Sber secrets проверяются на известные weak/template значения, а критичные DB/JWT/legal-evidence keys имеют минимальную длину;
- API-token encryption key проверяется реальным `Fernet(...)` до запуска runtime;
- `LEGAL_EVIDENCE_HMAC_KEY` стал отдельным обязательным production secret;
- включённый Sber требует реальные HTTPS gateway/return/fail URLs и merchant credentials;
- включённый password recovery требует реальный HTTPS reset host, реальный SMTP host/sender domain, STARTTLS и неплейсхолдерные credentials;
- `.env.production.example` намеренно не проходит startup validation до замены placeholders;
- Release integrity проверяет одновременно fail-closed template и успешный full-app import с CI-only безопасными overrides;
- regression suite закрепляет production/Sber/lifecycle validation contracts.

Первый CI-прогон P33 поймал несовместимость порядка recovery-validation и ошибку тестового Sber fixture; они были исправлены до merge. Финальный exact head `272dabc04f16290bca71bd1030ffe24b8a2186bd` прошёл Backend security, Frontend build, Database migrations и Release integrity полностью зелёными.

P33 закрывает найденный code-side production-config blocker, но не является фактом production-like deployment или внешней acceptance.

## 0.9.0-alpha.11 — P34: beta evidence-contract closure

**PR:** #53  
**Merge:** `2b0ce4522adda642f6af8fa78b30e5440a7469be`.

P34 появился после post-P33 сверки `RELEASE_ROADMAP.md`, `RELEASE_READINESS.md` и `ops/release_evidence.py`. Был найден governance blocker: runner мог формально выдать полный beta manifest по трём artifacts (`ci`, `core_smoke`, `data_accuracy`), хотя beta readiness уже требовал deployment/rollback, реальный SMTP/account-lifecycle smoke, desktop/mobile UX и secrets review.

P34:

- синхронизировал обязательный beta evidence set с фактическим readiness: `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`;
- сделал RC строгим superset beta и stable — superset RC;
- ввёл manifest schema v2;
- связал stage с версией: beta требует `*-beta.N`, RC — `*-rc.N`, stable — версию без prerelease suffix;
- требует полный 40-символьный Git SHA и непустой environment;
- отклоняет неизвестные и пустые artifacts;
- проверяет `data_accuracy` как schema v1 JSON со `status=pass`, ненулевыми periods/metrics и SHA-256 input/policy;
- расширил Release integrity positive/negative tests, включая старый неполный beta-набор, invalid SHA, alpha-version для beta, empty artifact и failing data-accuracy evidence;
- синхронизировал `RELEASE_EVIDENCE.md`, roadmap/readiness/versioning/CHANGELOG.

Финальный exact head `0d0d3d6c7c9f17f569f816bd79d9577b7fc226e6` прошёл Backend security, Frontend build, Database migrations и Release integrity полностью зелёными. P34 не является доказательством прохождения внешней acceptance: beta всё ещё требует реальных evidence artifacts из production-like environment.

## Следующая стадия — 0.9.0-beta.1

Допускается только после:

- feature freeze WB Web v1 на текущем `0.9.0-alpha.11` baseline и отсутствия известных необработанных code-side blockers;
- production-like HTTPS deployment из repo с реальными non-placeholder secrets/hosts и deploy/rollback evidence;
- фактического core release smoke, включая disposable registration/demo/legal evidence;
- реального SMTP/recovery и account-lifecycle smoke;
- desktop/mobile UX smoke и secrets review;
- data-accuracy acceptance на реальном WB seller account и фиксированных периодах;
- отсутствия необъяснённых существенных денежных расхождений;
- сохранённого beta release-evidence manifest v2 для exact `*-beta.N` commit.

## 1.0.0-rc.1

Требует фактического закрытия внешних/операционных gates: WB partner/service credentials и real seller full sync, Sber merchant payment/refund smoke, production DNS/TLS, monitoring/logging, off-host backup/restore drill и non-draft legal documents.

## 1.0.0 — WB Insight Web v1 Stable

Stable выпускается из проверенного RC. Перед тегом `v1.0.0` не должно оставаться release-blocking security defects или необъяснённых финансовых расхождений; backup/rollback/legal/release evidence должны быть подтверждены.

Подробные gates: `RELEASE_ROADMAP.md`, `RELEASE_READINESS.md`, `VERSIONING.md`.
