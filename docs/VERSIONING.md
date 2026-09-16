# WB Insight — политика версионирования

WB Insight использует Semantic Versioning:

`MAJOR.MINOR.PATCH[-PRERELEASE]`

Примеры: `0.9.0-alpha.10`, `0.9.0-beta.1`, `1.0.0-rc.1`, `1.0.0`.

## Номера версии

### MAJOR

После первого stable-релиза увеличивается при несовместимых изменениях продукта или API. До `1.0.0` prerelease-разработка остаётся в major `0`.

### MINOR

Осмысленная продуктовая веха или новый уровень release-readiness. MINOR не является счётчиком коммитов.

### PATCH

Backward-compatible исправления опубликованной capability line. В prerelease-разработке итерации одной линии обозначаются `alpha.N`, `beta.N` или `rc.N`.

## Стадии

### alpha

Активная разработка и hardening. Могут оставаться code-side, external, operational или legal blockers. Наличие acceptance tooling само по себе не повышает stage.

### beta

Feature scope WB Web v1 заморожен. `0.9.0-beta.1` допускается только когда одновременно:

- P29 dependency/security hardening, P30 acceptance tooling, P31 account-lifecycle baseline, P32 registration/beta-smoke hardening и P33 production-config preflight слиты с green CI;
- известных необработанных code-side release blockers нет;
- production-like HTTPS environment воспроизводимо разворачивается из репозитория;
- core end-to-end smoke реально пройден, включая disposable registration/demo/legal evidence;
- password recovery проверен через фактический SMTP/provider;
- выполнена приёмочная сверка ключевой аналитики на реальном WB seller account;
- нет необъяснённых существенных денежных расхождений;
- сформирован полный beta release-evidence manifest для exact commit;
- оставшиеся blockers явно относятся к production activation/external onboarding или задачам, допустимым до RC.

### rc

`1.0.0-rc.1` — конкретная сборка, претендующая на stable. Она требует:

- production deployment и TLS;
- реальные WB partner credentials и seller smoke;
- реальный Sber acquiring/refund-reconciliation smoke;
- подключённые monitoring/alerts/uptime/logging;
- off-host encrypted backup и подтверждённый restore drill;
- утверждённые non-draft legal documents, включая retention/refund/cancellation policy;
- production-smoke account lifecycle;
- полный RC release-evidence manifest.

### stable

Первый публичный stable-релиз — `1.0.0`. Stable выпускается из проверенного RC, а не из новой функциональной ветки.

## Текущая release-линия

`main` находится на **`0.9.0-alpha.9`** после P32 / PR #49, merge `7206df554e6f98c2533160385d9ad7d27c704268`. Exact P32 head перед merge прошёл Backend security, Frontend build, Database migrations и Release integrity.

Ветка P33 `codex/p33-production-config-preflight` является кандидатом **`0.9.0-alpha.10`**. Она закрывает найденный при pre-beta аудите production-config blocker: приложение должно fail-closed при template/weak secrets, malformed Fernet key, example hosts и небезопасной recovery/Sber конфигурации. Повышение `main` до alpha.10 произойдёт только после полного green CI exact-head P33.

После merge P33 следующее повышение стадии — `0.9.0-beta.1` только после фактического production-like HTTPS deployment, полного smoke, SMTP recovery и real-seller data-accuracy acceptance с evidence manifest.

Каноническая последовательность:

1. `0.9.0-alpha.7` — acceptance tooling + release evidence baseline;
2. `0.9.0-alpha.8` — account-lifecycle code baseline;
3. `0.9.0-alpha.9` — registration transaction/demo/beta-smoke hardening, текущий `main` до merge P33;
4. `0.9.0-alpha.10` — production configuration fail-closed hardening, P33 candidate;
5. `0.9.0-beta.1` — feature freeze + реальный production-like + SMTP recovery + data-accuracy acceptance;
6. `1.0.0-rc.1` — production candidate после закрытия WB/Sber/prod/legal/ops blockers;
7. `1.0.0` — публичный WB Insight Web v1 Stable.

Stage нельзя повышать только из-за количества commits, номера P-задачи или наличия скрипта проверки. Если перед beta обнаружен реальный release-blocking code defect, он закрывается следующей alpha-итерацией с отдельным CI evidence. Gates определяются `docs/RELEASE_ROADMAP.md` и `docs/RELEASE_READINESS.md`.

## Source of truth

Корневой `VERSION` — каноническая версия продукта. Release PR синхронизирует:

- `VERSION`;
- `frontend/package.json`;
- `CHANGELOG.md`;
- для milestone — `docs/VERSION_HISTORY.md`, `docs/VERSIONING.md` и `docs/RELEASE_READINESS.md`.

Backend runtime читает `VERSION`; health endpoints показывают deployed version.

`package-lock.json` — dependency-resolution metadata, а не source of truth версии продукта.

## Release evidence

Начиная с P30 повышение stage требует manifest, созданный `ops/release_evidence.py`. Manifest связывает version, exact commit, environment и SHA-256 acceptance artifacts. Требуемые типы artifacts задокументированы в `docs/RELEASE_EVIDENCE.md`.

## Git tags

Внешне распространяемые prerelease/stable builds получают immutable tag с префиксом `v`, например:

- `v0.9.0-beta.1`;
- `v1.0.0-rc.1`;
- `v1.0.0`.

Реконструированные исторические milestones до введения формальной политики не означают, что соответствующий Git tag существовал.
