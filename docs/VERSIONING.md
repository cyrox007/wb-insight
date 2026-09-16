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

Активная разработка и hardening. Могут оставаться code-side, external, operational или legal blockers. Наличие acceptance/deployment tooling само по себе не повышает stage.

### beta

Feature scope WB Web v1 заморожен. `0.9.0-beta.1` допускается только когда одновременно:

- P29 dependency/security hardening, P30 acceptance tooling, P31 account-lifecycle baseline, P32 registration/beta-smoke, P33 production-config, P34 evidence-contract, P35 data-accuracy completeness и P36 systemd deployment hardening закрыты;
- известных необработанных code-side release blockers нет;
- production-like HTTPS environment воспроизводимо разворачивается из репозитория;
- при systemd deployment backend/Celery/Beat фактически работают из Python 3.12 environment, frontend собирается на Node `^20.19` или `>=22.12`, update начинается из clean Git tree;
- clean DB migration и upgrade существующей БД подтверждены;
- deploy/rollback smoke пройден;
- core end-to-end smoke реально пройден, включая disposable registration/demo/legal evidence;
- password recovery проверен через фактический SMTP/provider;
- основные desktop/mobile UX сценарии пройдены;
- выполнена проверка отсутствия secrets/JWT/WB credentials в frontend bundle, git и логах;
- выполнена приёмочная сверка ключевой аналитики на реальном WB seller account;
- в каждом acceptance-периоде присутствуют все policy-required метрики, `missing=0`;
- tolerance override допустим только с `override_reason` и review evidence;
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

`main` находится на **`0.9.0-alpha.11`**. В эту baseline входят:

- P34 / PR #53, merge `2b0ce4522adda642f6af8fa78b30e5440a7469be` — beta evidence-contract closure;
- P36 / PR #55, merge `d4c8a20d6ecc75ab9cd8449bd55f6b2ce4242d9c` — systemd updater/runtime hardening без product version bump;
- P35 / PR #56, merge `d2e782208228fbe60cb92b9e61fbf8d325f0e839` — обязательное data-accuracy coverage без product version bump.

P35 и P36 оставлены внутри `0.9.0-alpha.11`, потому что они усиливают release/deployment tooling и acceptance contract, но не добавляют новую runtime capability и не меняют публичную схему продукта.

`0.9.0-alpha.11` теперь закрывает два дополнительных pre-beta обхода: production-like systemd update нельзя считать успешным на старом Python/Node environment, а data-accuracy нельзя пройти через пропуск policy-required метрик или необъяснённое расширение tolerance.

Следующее повышение стадии — `0.9.0-beta.1` только после фактического production-like HTTPS deployment, полного smoke, SMTP recovery, UX/secrets review и real-seller data-accuracy acceptance с evidence manifest v2. Новая alpha-итерация создаётся только если до beta обнаружится новый реальный code-side/runtime release blocker.

Каноническая последовательность:

1. `0.9.0-alpha.7` — acceptance tooling + release evidence baseline;
2. `0.9.0-alpha.8` — account-lifecycle code baseline;
3. `0.9.0-alpha.9` — registration transaction/demo/beta-smoke hardening;
4. `0.9.0-alpha.10` — production configuration fail-closed hardening;
5. `0.9.0-alpha.11` — beta evidence-contract closure + P35/P36 pre-beta hardening, текущий `main`;
6. `0.9.0-beta.1` — feature freeze + реальный production-like + SMTP recovery + UX/secrets review + data-accuracy acceptance;
7. `1.0.0-rc.1` — production candidate после закрытия WB/Sber/prod/legal/ops blockers;
8. `1.0.0` — публичный WB Insight Web v1 Stable.

Stage нельзя повышать только из-за количества commits, номера P-задачи или наличия скрипта проверки. Если перед beta обнаружен реальный release-blocking code defect, он закрывается hardening-итерацией с отдельным CI evidence. Если изменение касается только deployment/release tooling и не меняет runtime capability, отдельный product version bump не обязателен, но история и release gates должны быть обновлены.

Gates определяются `docs/RELEASE_ROADMAP.md` и `docs/RELEASE_READINESS.md`.

## Source of truth

Корневой `VERSION` — каноническая версия продукта. Release PR синхронизирует:

- `VERSION`;
- `frontend/package.json`;
- `CHANGELOG.md`;
- для milestone — `docs/VERSION_HISTORY.md`, `docs/VERSIONING.md` и `docs/RELEASE_READINESS.md`.

Backend runtime читает `VERSION`; health endpoints показывают deployed version.

`package-lock.json` — dependency-resolution metadata, а не source of truth версии продукта.

## Release evidence

Начиная с P30 повышение stage требует manifest, созданный `ops/release_evidence.py`. С P34 manifest schema v2 связывает stage, соответствующую prerelease/stable `VERSION`, полный 40-символьный commit SHA, environment и SHA-256 acceptance artifacts. Beta manifest не может стать `complete`, если отсутствует любой из обязательных `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy` или `ci` artifacts.

P35 дополнительно требует, чтобы `data_accuracy` evidence был получен из полного набора policy-required метрик по каждому acceptance-периоду; missing required observation блокирует результат, а tolerance override требует `override_reason`.

Требуемые типы и validation contract задокументированы в `docs/RELEASE_EVIDENCE.md` и `docs/DATA_ACCURACY_ACCEPTANCE.md`.

## Git tags

Внешне распространяемые prerelease/stable builds получают immutable tag с префиксом `v`, например:

- `v0.9.0-beta.1`;
- `v1.0.0-rc.1`;
- `v1.0.0`.

Реконструированные исторические milestones до введения формальной политики не означают, что соответствующий Git tag существовал.
