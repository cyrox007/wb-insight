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

- orders;
- sales/returns;
- Promotion API advertising;
- product funnel;
- retention/rolling refresh semantics.

## 0.7.0-alpha.1 — P8–P13: semantic/business layer

**Mainline:** PR #23–#28.

- unified metric semantics;
- multi-account dashboard scope;
- corrected Unit Economy;
- monthly revenue plans;
- paid storage;
- historical COGS;
- seller manual expenses.

## 0.8.0-alpha.1 — P14–P18: feature-complete WB analytics alpha

**Mainline:** PR #29–#33.

- единый Dashboard UX;
- seller settings;
- Inventory Risk/Replenishment;
- Price Monitoring;
- Finance/Reconciliation;
- удаление demo/hardcoded KPI из аналитических экранов.

## 0.9.0-alpha.1 — P19–P24: release-hardening baseline

**Mainline:** PR #34–#39.  
**Commit после P24:** `ff0d278c32f0a770dc0cdbc0cf0ab9d98c2377ca`.

- WB credential compliance по JWT metadata;
- marketplace adapter core;
- credential identity foundation;
- production WB token policy и live validation;
- release-readiness/health baseline;
- Sber acquiring с idempotency и server-side payment confirmation.

## 0.9.0-alpha.2 — P25: version governance и deployment

**PR:** #40  
**Merge:** `8cad1f098ae63c813ed36aad2c462d196484153a`.

- root `VERSION` стал source of truth;
- formal SemVer/stage gates;
- backend/frontend Docker images;
- production Compose topology;
- same-origin nginx gateway;
- deployment/upgrade/rollback runbook;
- release-integrity CI.

## 0.9.0-alpha.3 — P26: operations hardening

**PR:** #41  
**Merge:** `76ee8651298fff99b8bf6a11921dcbfbf0916c46`.

- operational health snapshot;
- stale/failed sync and lease checks;
- credential/service-secret expiry monitoring;
- HTTP/5xx telemetry;
- Celery operations monitor and alert webhook;
- encrypted PostgreSQL backup/restore/drill;
- CI backup/restore roundtrip;
- canonical secure refresh-cookie helper;
- удалён legacy GET refresh.

## 0.9.0-alpha.4 — P27: legal consent foundation

**PR:** #42  
**Merge:** `591b3919eb80403a7e4225382d996dca63b8c039`.

- versioned legal-document registry;
- public legal requirements/documents API;
- immutable consent evidence;
- backend enforcement регистрации, billing и marketplace connection;
- public legal pages;
- закрыт legacy credential-add bypass.

Тексты остаются draft до внешнего legal approval.

## 0.9.0-alpha.5 — P28: browser-session hardening и release smoke

**PR:** #43  
**Merge:** `351cbcd7129c69959e138918b1d621a6475af210`.

- access JWT перенесён из persistent browser storage в memory;
- session после reload восстанавливается через HttpOnly refresh cookie;
- refresh возвращает safe user snapshot;
- concurrent 401 используют единый refresh flow;
- frontend CI запрещает persistent access token;
- production API fallback стал same-origin;
- nginx gateway дополнен `/billing` и `/legal`;
- release-integrity реально проверяет container routing;
- `ops/release_smoke.py` формализует production-like smoke;
- добавлены backend session-restore regression tests.

P28 закрыл последний запланированный session hardening blocker, но во время CI выявились dependency vulnerabilities, поэтому beta не была назначена автоматически.

## 0.9.0-alpha.6 — P29: dependency security и документационная ревизия

**PR:** #44  
**Статус:** текущий кандидат; версия становится mainline только после green CI и merge.

Изменения кандидата:

- frontend dependency tree обновлён после фактического `npm audit`;
- Axios поднят в исправленную release line;
- удалена ошибочная runtime dependency `node` из browser manifest;
- безопасные transitive versions закреплены через overrides;
- постоянный CI gate: production + full-tree `npm audit`;
- backend CI дополнен `pip-audit` production requirements;
- временный lockfile self-write flow отключён и возвращён в read-only режим;
- документация полностью реструктурирована: overview, requirements, install, configuration, architecture, features, user/admin/developer/security guides, metrics, troubleshooting, roadmap/readiness/version history.

Цель `alpha.6`: последний чистый alpha code/documentation baseline перед production-like beta validation.

## Следующая стадия — 0.9.0-beta.1

Допускается только после:

- merge P29 с green CI;
- feature freeze WB Web v1;
- production-like HTTPS deployment;
- core release smoke;
- data-accuracy acceptance на реальном WB seller account;
- отсутствия необъяснённых существенных денежных расхождений.

## 1.0.0-rc.1

Требует фактического закрытия внешних/операционных gates:

- WB partner/service credentials и real seller smoke;
- Sber merchant onboarding и payment smoke;
- production DNS/TLS/deployment;
- monitoring/alerts/logging;
- off-host backup + restore drill;
- non-draft legal documents;
- account lifecycle/support procedures;
- полный release evidence.

## 1.0.0 — WB Insight Web v1 Stable

Stable выпускается из проверенного RC. Перед тегом `v1.0.0` не должно оставаться release-blocking security defects или необъяснённых финансовых расхождений; backup/rollback/legal/release evidence должны быть подтверждены.

Подробные gates: `RELEASE_ROADMAP.md`, `RELEASE_READINESS.md`, `VERSIONING.md`.
