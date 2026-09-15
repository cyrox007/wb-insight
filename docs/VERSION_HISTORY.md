# WB Insight — подробная история версий

Дата полной ревизии: 15 сентября 2026 года.

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

**Ветка:** `codex/p30-beta-readiness-data-accuracy`  
**Статус:** текущий кандидат; становится mainline только после green CI и merge.

Что входит в P30:

- versioned policy ключевых метрик WB Web v1 и их tolerances;
- deterministic `Decimal` comparator для expected/actual;
- machine-readable JSON и Markdown data-accuracy report;
- SHA-256 привязка отчёта к acceptance input и policy;
- positive/negative CI fixtures;
- release-evidence manifest, связывающий stage, exact commit, version, environment и hashes artifacts;
- отдельные evidence contracts для beta/RC/stable;
- CI self-test, который проверяет как успешный, так и заведомо провальный acceptance;
- `VERSION` теперь триггерит backend security и database-migration gates, чтобы каждый release candidate проходил полный контур.

Почему это всё ещё alpha: tooling создаёт доказуемый процесс, но не заменяет реальный production-like deployment и сверку на настоящем seller account. `0.9.0-beta.1` назначается только после фактического прохождения этих gates.

## Следующая стадия — 0.9.0-beta.1

Допускается только после:

- merge P30 с green CI;
- feature freeze WB Web v1;
- production-like HTTPS deployment из repo;
- core release smoke;
- disposable registration/demo/legal evidence;
- data-accuracy acceptance на реальном WB seller account и фиксированных периодах;
- отсутствия необъяснённых существенных денежных расхождений;
- сохранённого beta release-evidence manifest для exact commit.

## 1.0.0-rc.1

Требует фактического закрытия внешних/операционных gates: WB partner/service credentials и real seller full sync, Sber merchant payment smoke, production DNS/TLS, monitoring/logging, off-host backup/restore drill, non-draft legal documents и account lifecycle.

## 1.0.0 — WB Insight Web v1 Stable

Stable выпускается из проверенного RC. Перед тегом `v1.0.0` не должно оставаться release-blocking security defects или необъяснённых финансовых расхождений; backup/rollback/legal/release evidence должны быть подтверждены.

Подробные gates: `RELEASE_ROADMAP.md`, `RELEASE_READINESS.md`, `VERSIONING.md`.
