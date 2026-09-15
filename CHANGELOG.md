# История изменений WB Insight

Все записи ведутся на русском. Детальная техническая летопись с PR/SHA находится в [`docs/VERSION_HISTORY.md`](docs/VERSION_HISTORY.md), правила версионирования — в [`docs/VERSIONING.md`](docs/VERSIONING.md).

Версии до введения формальной release-policy 15 сентября 2026 года реконструированы по истории `main` и не означают существование соответствующих Git tags.

## [0.9.0-alpha.6] — кандидат, 2026-09-15

P29 — dependency/security hardening и полная ревизия документации перед beta-validation.

- frontend dependency tree обновлён после фактического security audit;
- Axios переведён на исправленную release line `^1.18.0`;
- удалён ошибочно включённый в browser dependencies пакет `node`;
- безопасные transitive versions закреплены для `follow-redirects`, `form-data`, `nanoid` и `postcss`;
- CI теперь отдельно проверяет production и полный frontend dependency tree через `npm audit` с порогом High;
- backend CI дополнен `pip-audit` для production Python requirements;
- временный self-write lockfile flow отключён, постоянный frontend CI снова read-only;
- документация перестроена в единый `docs/`-портал: обзор, системные требования, установка, конфигурация, архитектура, функции, пользовательская/административная/разработческая инструкции, безопасность, API overview, данные и метрики, troubleshooting, account lifecycle, release roadmap/readiness;
- корневые `README.md` и `SETUP.md` приведены к текущему состоянию продукта;
- история версий и release gates синхронизированы с фактически слитым P28;
- до beta добавлен обязательный data-accuracy gate: сверка ключевой аналитики с реальными WB-источниками и исходной spreadsheet-моделью.

Версия становится mainline только после полного green CI и merge PR #44.

## [0.9.0-alpha.5] — 2026-09-15

P28 — browser-session hardening и release smoke. PR #43, merge `351cbcd7129c69959e138918b1d621a6475af210`.

- access JWT перенесён из persistent browser storage в память приложения;
- session после reload восстанавливается через HttpOnly refresh-cookie;
- refresh возвращает новый access token и безопасный user snapshot;
- concurrent 401 используют единый refresh flow;
- frontend CI запрещает persistent access-token storage;
- исправлен production API fallback на same-origin;
- nginx gateway дополнен `/billing` и `/legal`;
- release-integrity CI проверяет маршрутизацию на реально запущенном frontend container;
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

- `0.9.0-beta.1` — feature freeze + production-like deployment/core smoke + data-accuracy acceptance;
- `1.0.0-rc.1` — real WB/Sber/prod/legal/ops/account-lifecycle gates;
- `1.0.0` — публичный stable WB Insight Web v1 из проверенного RC.

Полный план: [`docs/RELEASE_ROADMAP.md`](docs/RELEASE_ROADMAP.md).
