# WB Insight — политика версионирования

WB Insight использует Semantic Versioning:

`MAJOR.MINOR.PATCH[-PRERELEASE]`

Примеры: `0.9.0-alpha.11`, `0.9.0-beta.1`, `1.0.0-rc.1`, `1.0.0`.

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

- P29 dependency/security hardening, P30 acceptance tooling, P31 account-lifecycle baseline, P32 registration/beta-smoke hardening, P33 production-config preflight и P34 evidence-contract hardening слиты с green CI;
- известных необработанных code-side release blockers нет;
- production-like HTTPS environment воспроизводимо разворачивается из репозитория;
- core end-to-end smoke реально пройден, включая disposable registration/demo/legal evidence;
- password recovery проверен через фактический SMTP/provider;
- основные desktop/mobile UX сценарии пройдены;
- выполнена проверка отсутствия secrets/JWT/WB credentials в frontend bundle, git и логах;
- выполнена приёмочная сверка ключевой аналитики на реальном WB seller account;
- нет необъяснённых существенных денежных расхождений;
- сформирован полный beta release-evidence manifest v2 для exact commit и версии `*-beta.N`;
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

`main` находится на **`0.9.0-alpha.11`** после P34 / PR #53, merge `2b0ce4522adda642f6af8fa78b30e5440a7469be`. Финальный exact head P34 `0d0d3d6c7c9f17f569f816bd79d9577b7fc226e6` прошёл Backend security, Frontend build, Database migrations и Release integrity.

`0.9.0-alpha.11` закрывает найденный после P33 governance blocker: release-evidence manifest v2 синхронизирован с фактическим beta readiness, требует полный beta evidence set, валидирует stage/version, полный Git SHA, непустые artifacts и machine-readable passing `data_accuracy`.

Следующее повышение стадии — `0.9.0-beta.1` только после фактического production-like HTTPS deployment, полного smoke, SMTP recovery, UX/secrets review и real-seller data-accuracy acceptance с evidence manifest v2. Новая alpha-итерация создаётся только если до beta обнаружится ещё один реальный code-side release blocker.

Каноническая последовательность:

1. `0.9.0-alpha.7` — acceptance tooling + release evidence baseline;
2. `0.9.0-alpha.8` — account-lifecycle code baseline;
3. `0.9.0-alpha.9` — registration transaction/demo/beta-smoke hardening;
4. `0.9.0-alpha.10` — production configuration fail-closed hardening;
5. `0.9.0-alpha.11` — beta evidence-contract closure, текущий `main`;
6. `0.9.0-beta.1` — feature freeze + реальный production-like + SMTP recovery + UX/secrets review + data-accuracy acceptance;
7. `1.0.0-rc.1` — production candidate после закрытия WB/Sber/prod/legal/ops blockers;
8. `1.0.0` — публичный WB Insight Web v1 Stable.

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

Начиная с P30 повышение stage требует manifest, созданный `ops/release_evidence.py`. С P34 manifest schema v2 связывает stage, соответствующую prerelease/stable `VERSION`, полный 40-символьный commit SHA, environment и SHA-256 acceptance artifacts. Beta manifest не может стать `complete`, если отсутствует любой из обязательных `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy` или `ci` artifacts. Требуемые типы и validation contract задокументированы в `docs/RELEASE_EVIDENCE.md`.

## Git tags

Внешне распространяемые prerelease/stable builds получают immutable tag с префиксом `v`, например:

- `v0.9.0-beta.1`;
- `v1.0.0-rc.1`;
- `v1.0.0`.

Реконструированные исторические milestones до введения формальной политики не означают, что соответствующий Git tag существовал.
