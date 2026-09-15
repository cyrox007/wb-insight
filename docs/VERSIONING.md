# WB Insight — политика версионирования

WB Insight использует Semantic Versioning:

`MAJOR.MINOR.PATCH[-PRERELEASE]`

Примеры: `0.9.0-alpha.5`, `0.9.0-beta.1`, `1.0.0-rc.1`, `1.0.0`.

## Номера версии

### MAJOR

После первого stable-релиза увеличивается при несовместимых изменениях продукта или API. До `1.0.0` prerelease-разработка остаётся в major `0`.

### MINOR

Осмысленная продуктовая веха: новая завершённая функциональная область или новый уровень release-readiness. MINOR не является счётчиком коммитов.

### PATCH

Backward-compatible исправления уже опубликованной capability line. В prerelease-разработке обычные итерации одной линии обозначаются счётчиком `alpha.N`, `beta.N` или `rc.N`.

## Стадии

### alpha

Активная разработка. Допустимы незакрытые code-side, external, operational или legal blockers.

### beta

Feature scope WB Web v1 заморожен. `0.9.0-beta.1` разрешена только когда:

- все code-side P0 blockers закрыты;
- P28 слит с полностью зелёным CI;
- production-like environment разворачивается из репозитория;
- core end-to-end smoke реально пройден;
- оставшиеся blockers явно относятся к внешнему onboarding/production activation.

### rc

Конкретная сборка, претендующая на stable. `1.0.0-rc.1` требует:

- production deployment и TLS;
- реальный WB seller smoke;
- реальный Sber acquiring smoke;
- включённые monitoring/alerts/uptime/logging;
- off-host backup и подтверждённый restore drill;
- утверждённые non-draft legal documents;
- завершённый session hardening;
- полный release smoke и сохранённый evidence.

### stable

Первый публичный stable-релиз — `1.0.0`.

## Текущая release-линия

`main` после P27 находится на **`0.9.0-alpha.4`**.

P28 — кандидат **`0.9.0-alpha.5`** в ветке `codex/p28-session-hardening-release-smoke`. Версия становится канонической только после green CI и merge в `main`.

Дальнейшая последовательность:

1. `0.9.0-alpha.5` — browser-session hardening и release-smoke baseline;
2. `0.9.0-beta.1` — feature freeze и production-like validation;
3. `1.0.0-rc.1` — production candidate после закрытия external/ops/legal blockers;
4. `1.0.0` — публичный WB Insight Web v1 Stable.

Stage нельзя повышать только из-за количества commits или номера P-задачи. Gates определяются `docs/RELEASE_READINESS.md`.

## Source of truth

Корневой `VERSION` — каноническая версия продукта. Release PR синхронизирует:

- `VERSION`;
- `frontend/package.json`;
- раздел этой версии в `CHANGELOG.md`.

Backend runtime читает `VERSION`; `/health/live` и `/health/ready` показывают развёрнутую версию.

`package-lock.json` — dependency-resolution metadata и не считается source of truth product version.

## Git tags

Внешне распространяемые prerelease и stable builds получают immutable tag с префиксом `v`, например:

- `v0.9.0-beta.1`
- `v1.0.0-rc.1`
- `v1.0.0`

Реконструированные исторические версии до введения этой политики не означают, что соответствующий Git tag существовал.
