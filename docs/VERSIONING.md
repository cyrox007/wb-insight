# WB Insight — политика версионирования

WB Insight использует Semantic Versioning:

`MAJOR.MINOR.PATCH[-PRERELEASE]`

Примеры: `0.9.0-alpha.6`, `0.9.0-beta.1`, `1.0.0-rc.1`, `1.0.0`.

## Номера версии

### MAJOR

После первого stable-релиза увеличивается при несовместимых изменениях продукта или API. До `1.0.0` prerelease-разработка остаётся в major `0`.

### MINOR

Осмысленная продуктовая веха или новый уровень release-readiness. MINOR не является счётчиком коммитов.

### PATCH

Backward-compatible исправления опубликованной capability line. В prerelease-разработке итерации одной линии обозначаются `alpha.N`, `beta.N` или `rc.N`.

## Стадии

### alpha

Активная разработка и hardening. Могут оставаться code-side, external, operational или legal blockers.

### beta

Feature scope WB Web v1 заморожен. `0.9.0-beta.1` допускается только когда одновременно:

- P29 dependency/security hardening слит с полностью зелёным CI;
- известных необработанных code-side release blockers нет;
- production-like HTTPS environment воспроизводимо разворачивается из репозитория;
- core end-to-end smoke реально пройден;
- выполнена приёмочная сверка ключевой аналитики с реальными WB-источниками;
- нет необъяснённых существенных денежных расхождений;
- оставшиеся blockers явно относятся к production activation/external onboarding или задачам, допустимым до RC.

### rc

`1.0.0-rc.1` — конкретная сборка, претендующая на stable. Она требует:

- production deployment и TLS;
- реальные WB partner credentials и seller smoke;
- реальный Sber acquiring smoke;
- подключённые monitoring/alerts/uptime/logging;
- off-host encrypted backup и подтверждённый restore drill;
- утверждённые non-draft legal documents;
- закрытый account lifecycle или утверждённые безопасные support procedures;
- полный release smoke и сохранённый evidence.

### stable

Первый публичный stable-релиз — `1.0.0`. Stable выпускается из проверенного RC, а не из новой функциональной ветки.

## Текущая release-линия

`main` после P28 находится на **`0.9.0-alpha.5`**.

P29 — кандидат **`0.9.0-alpha.6`** в ветке `codex/p29-dependency-security-beta-readiness`. P29 закрывает frontend/backend dependency audits, package hygiene и полную ревизию документации.

Каноническая последовательность:

1. `0.9.0-alpha.6` — dependency/security + documentation baseline;
2. `0.9.0-beta.1` — feature freeze + production-like + data-accuracy acceptance;
3. `1.0.0-rc.1` — production candidate после закрытия WB/Sber/prod/legal/ops/account-lifecycle blockers;
4. `1.0.0` — публичный WB Insight Web v1 Stable.

Stage нельзя повышать только из-за количества commits или номера P-задачи. Gates определяются `docs/RELEASE_ROADMAP.md` и `docs/RELEASE_READINESS.md`.

## Source of truth

Корневой `VERSION` — каноническая версия продукта. Release PR синхронизирует:

- `VERSION`;
- `frontend/package.json`;
- `CHANGELOG.md`;
- для milestone — `docs/VERSION_HISTORY.md`, `docs/VERSIONING.md` и `docs/RELEASE_READINESS.md`.

Backend runtime читает `VERSION`; health endpoints показывают deployed version.

`package-lock.json` — dependency-resolution metadata, а не source of truth версии продукта.

## Git tags

Внешне распространяемые prerelease/stable builds получают immutable tag с префиксом `v`, например:

- `v0.9.0-beta.1`;
- `v1.0.0-rc.1`;
- `v1.0.0`.

Реконструированные исторические milestones до введения формальной политики не означают, что соответствующий Git tag существовал.
