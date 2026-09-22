# WB Insight — release evidence

Release stage повышается только для конкретной версии и конкретного commit. Этот документ задаёт формат доказательств, которые подтверждают прохождение соответствующих gates.

## Зачем нужен manifest

Скриншоты, логи и ручные заметки быстро теряют связь с точной сборкой. `ops/release_evidence.py` создаёт manifest, который фиксирует:

- release stage;
- `VERSION`;
- полный 40-символьный commit SHA;
- environment;
- UTC timestamp;
- обязательные типы evidence;
- имя, размер и SHA-256 каждого evidence-файла.

Manifest не копирует содержимое artifacts и не предназначен для хранения секретов.

Начиная с P34 runner работает fail-closed:

- `beta` evidence принимается только для версии `*-beta.N`;
- `rc` evidence — только для `*-rc.N`;
- `stable` evidence — только для версии без prerelease suffix;
- commit обязан быть полным 40-символьным Git SHA;
- environment не может быть пустым;
- artifact kind должен входить в канонический contract;
- каждый artifact должен существовать и быть непустым;
- `data_accuracy` должен быть JSON-отчётом schema v1 со `status=pass`, ненулевыми period/metric counts и SHA-256 входа/policy.

Начиная с P40 фактический promotion выполняется через `ops/release_candidate_evidence.py`. Он сначала требует structured exact-head `ci` evidence, обязательную привязку isolated existing-database upgrade proof к deployment evidence и отдельный payment-isolation proof, и только после этого вызывает `ops/release_evidence.py --require-structured-runtime-evidence`.

## Structured runtime evidence

`ci` создаётся `ops/ci_acceptance.py`. Collector обращается к GitHub Actions API либо принимает сохранённый API payload через `--runs-json`, выбирает только runs с exact release SHA и требует successful/completed:

- Backend security;
- Frontend build;
- Database migrations;
- Release integrity;
- Release smoke contract;
- Systemd updater.

В report сохраняются только workflow name, run id/attempt, event и итоговый status/conclusion. `GITHUB_TOKEN`, job logs и их содержимое в evidence не копируются. Release-candidate изменение `VERSION` специально запускает все эти контуры, чтобы exact candidate SHA не наследовал зелёный статус от предыдущего commit.

`ops/database_upgrade_acceptance.py` доказывает upgrade **копии существующей БД**, а не только clean-schema migration. Он проверяет checksum encrypted backup, расшифровывает backup только во временный файл, восстанавливает его в отдельную временную PostgreSQL БД, выполняет `alembic upgrade head`, сверяет `current == heads`, выполняет `alembic check` и затем удаляет временную БД. Исходная БД не изменяется. В evidence не сохраняются пароль БД, passphrase или содержимое dump; сохраняются только release binding, SHA-256 encrypted backup, revisions, table counts и статусы проверок.

`deployment` создаётся `ops/systemd_acceptance.py`. В dev-first flow pre-promotion candidate проверяется на exact `dev` head с `TARGET_BRANCH=dev` / `--target-branch dev`; production/release default остаётся `main`. Для beta collector получает structured database-upgrade proof через `--database-upgrade-proof ... --require-database-upgrade-proof`, проверяет совпадение VERSION/commit/environment и связывает proof по SHA-256. Далее deployment evidence требует:

- clean exact-head checkout целевой ветки;
- immutable `venv.release.*` и Python 3.12;
- поддерживаемый Node;
- active/enabled backend, Celery worker и Beat;
- Celery ping;
- Alembic current=head на развернутой БД;
- привязанный isolated existing-database upgrade proof;
- валидный nginx config;
- local readiness;
- публичный HTTPS readiness;
- опубликованный frontend bundle текущей сборки;
- SHA-256 отдельного rollback-drill proof.

`core_smoke` и `account_lifecycle` создаются одним полным прогоном `ops/release_smoke.py --evidence-output ...`. Строгая проверка требует HTTPS origin и подтверждённые flags disposable registration, реального email verification, demo activation, legal evidence, refresh/deactivation, authenticated flow, **authenticated mail-gateway readiness preflight**, P37 audit correlation и logout. Для `account_lifecycle` дополнительно обязательны реальный password reset через почтовый provider, proof resend-throttle/idempotent queue materialization и подтверждение, что ранее выданный access JWT после reset получает `session_revoked`. Поэтому beta core smoke запускается с `SMOKE_MAIL_GATEWAY=true`; один только успешно доставленный disposable mail flow не заменяет отдельное доказательство, что Control Panel видит тот же effective transport как ready.

Один и тот же sanitized `release-smoke.json` допустимо привязать как `core_smoke` и `account_lifecycle`: manifest всё равно фиксирует его SHA-256 отдельно для каждого kind.

`ops/payment_acceptance.py` закрывает beta-gate **test/live isolation** в read-only режиме. Он авторизуется существующим Control Panel аккаунтом, проверяет provider catalog и payment journal filters, но ничего не меняет и не создаёт платежи. Proof требует:

- уникальные `(provider, mode)` пары;
- отдельные `sber/test` и `sber/live`, причём test не наследует live ENV credentials;
- `fake/test` выключен, не ready и не default в production-like acceptance;
- default provider, если задан, только один и только `live`;
- provider URLs не содержат userinfo/query/fragment;
- API payload не раскрывает secret-like поля;
- `journal?mode=test` не возвращает live rows, а `journal?mode=live` не возвращает test rows.

В payment evidence не сохраняются пароль Control Panel, JWT/cookies, credential hints, provider URLs/credentials или payment PII — только release binding, количество конфигураций/проверенных строк и итоговые checks. `ops/release_candidate_evidence.py --payment-proof ...` валидирует этот proof и добавляет его SHA-256 в `candidate_subproofs.payment_isolation` итогового manifest.

`ops/sber_sandbox_acceptance.py` закрывает условную P40-проверку Sber sandbox merchant **только когда test credentials реально доступны**. Runner использует тот же `SberAcquiringClient`, что backend: регистрирует один неоплаченный sandbox order, проверяет HTTPS payment-form URL и выполняет `getOrderStatusExtended.do`. Card data не вводится, подписка не активируется, а paid-state считается ошибкой acceptance. В evidence не сохраняются merchant login/password, gateway URL, Sber order id или payment-form URL. Если proof передан через `ops/beta_release_evidence.py --sber-sandbox-proof ...`, он проверяется на exact VERSION/commit/environment/public origin и SHA-256-bound в `candidate_subproofs.sber_sandbox`; отсутствие proof не делает beta manifest неполным, если sandbox credentials для окружения недоступны.

`ux_smoke` создаётся `ops/ux_acceptance.py`. Инструмент не выдаёт автоматическую визуальную оценку: проверку интерфейса выполняет человек, а runner делает эту проверку полной и привязанной к exact build. Контракт требует desktop/mobile evidence для публичных auth-экранов, billing success, основных dashboard-разделов, role-aware staff workspace и Control Panel (overview/users/user-detail/roles/tariffs/payments/mail/audit). Для staff workspace отдельно фиксируются super_admin/admin/manager/support/analyst priorities; для user-detail — inactive/unverified/staff states; для mail — RuSender gateway; для recovery — request-sent/reset-success/invalid-or-expired states. Для каждого required state сохраняются только имя evidence-файла, размер и SHA-256; сами изображения/видео остаются в защищённом evidence storage.

`secrets_review` создаётся `ops/secrets_review.py`. Scanner не сохраняет значения секретов и не копирует совпавшие строки. Он сравнивает реально настроенные secret values с:

- tracked worktree;
- всеми reachable Git blobs;
- `frontend/dist` текущей сборки;
- bounded systemd journal backend/Celery/Beat;
- дополнительными log paths, если они переданы оператором.

Для runtime/frontend дополнительно ищутся JWT-shaped values. Structured gate требует `status=pass`, ноль findings, совпадающие VERSION/commit/environment, выполненные Git-history и journal scans и наличие проверки обязательных production secrets (`DB_PASSWORD`, encryption/JWT/legal-evidence/WB service secrets). Условные SMTP/Sber secrets проверяются автоматически, когда реально настроены.

## Beta evidence

Для `beta` обязательны все следующие artifacts:

- `ci` — structured exact-head GitHub Actions evidence;
- `deployment` — evidence production-like HTTPS deployment, isolated existing-DB upgrade и deploy/rollback smoke;
- `core_smoke` — результат production-like `ops/release_smoke.py` без отключения disposable registration;
- `account_lifecycle` — login/refresh/logout/deactivation и реальный password-recovery smoke через настроенный provider (текущий production-like путь — RuSender HTTPS API);
- `ux_smoke` — structured human-reviewed desktop/mobile evidence основных экранов и критичных empty/loading/error states;
- `secrets_review` — machine-readable проверка отсутствия настроенных secrets/JWT в frontend, Git и runtime logs;
- `data_accuracy` — green JSON-результат `ops/data_accuracy_acceptance.py` на реальном WB seller dataset.

Дополнительно strict beta entrypoint требует `payment-isolation.json`, `backup-restore.json`, `wb-live-data.json` и защищённый `accuracy-input.json`. Live-WB proof обязан соответствовать тому же seller account и тому же `data_accuracy` input; все обязательные sub-proofs SHA-256-bound в manifest. `sber-sandbox.json` остаётся условным дополнительным proof: он валидируется и привязывается только когда test merchant credentials реально доступны.

Канонический P40 пример:

```bash
RELEASE_SHA="$(git rev-parse HEAD)"
export ACCEPTANCE_ENVIRONMENT=staging-eu-1
export TARGET_BRANCH=dev  # pre-promotion candidate; main остаётся release default

python3 ops/ci_acceptance.py \
  --commit "$RELEASE_SHA" \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --output /secure/evidence/ci.json

python3 ops/database_upgrade_acceptance.py \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --backup /secure/backups/wb-before-candidate.dump.enc \
  --env-file /secure/runtime/wb-insight.env \
  --passphrase-file /secure/runtime/backup-passphrase \
  --output /secure/evidence/database-upgrade.json

# Используется тот же encrypted backup; рядом должен лежать <backup>.sha256.
# Restore drill выполняется в изолированной временной БД и удаляет её после проверки.
python3 ops/backup_restore_acceptance.py \
  --backup /secure/backups/wb-before-candidate.dump.enc \
  --commit "$RELEASE_SHA" \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --output /secure/evidence/backup-restore.json

python3 ops/systemd_acceptance.py \
  --target-branch "$TARGET_BRANCH" \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --public-base-url https://staging.example.com \
  --database-upgrade-proof /secure/evidence/database-upgrade.json \
  --require-database-upgrade-proof \
  --rollback-proof /secure/evidence/rollback-drill.txt \
  --require-rollback-proof \
  --output /secure/evidence/deployment.json

# SMOKE_EMAIL/SMOKE_PASSWORD и реальный SMOKE_WB_TOKEN задаются через
# environment/secret manager. Для beta core_smoke обязан доказать wb_credential=true.
python3 ops/release_smoke.py \
  --base-url https://staging.example.com \
  --require-email-verification \
  --require-password-reset \
  --audit-smoke \
  --evidence-output /secure/evidence/release-smoke.json

python3 ops/payment_acceptance.py \
  --base-url https://staging.example.com \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --output /secure/evidence/payment-isolation.json

# Live WB/data provenance выполняется по двухпроходной схеме из
# docs/WB_LIVE_DATA_ACCEPTANCE.md. Здесь показан финальный binding pass:
python3 ops/wb_live_data_acceptance.py \
  --base-url https://staging.example.com \
  --email seller-acceptance@example.com \
  --accuracy-input /secure/evidence/accuracy-input.json \
  --data-accuracy /secure/evidence/data-accuracy.json \
  --commit "$RELEASE_SHA" \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --output /secure/evidence/wb-live-data.json

# Если Sber test merchant credentials доступны, они передаются только через environment:
export SBER_TEST_API_BASE_URL=https://ecomtest.sberbank.ru/ecomm/gw/partner/api/v1
export SBER_TEST_USERNAME='<sandbox merchant login>'
export SBER_TEST_PASSWORD='<sandbox merchant password>'
/home/projects/wb/backend/venv/bin/python ops/sber_sandbox_acceptance.py \
  --public-origin https://staging.example.com \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --output /secure/evidence/sber-sandbox.json

python3 ops/ux_acceptance.py \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --write-template /secure/evidence/ux-review-input.json
# После фактической desktop/mobile проверки reviewer заполняет template:
python3 ops/ux_acceptance.py \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --input /secure/evidence/ux-review-input.json \
  --output /secure/evidence/ux-smoke.json

python3 ops/secrets_review.py \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --env-file /secure/runtime/wb-insight.env \
  --output /secure/evidence/secrets-review.json

python3 ops/beta_release_evidence.py \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --commit "$RELEASE_SHA" \
  --payment-proof /secure/evidence/payment-isolation.json \
  --backup-restore-proof /secure/evidence/backup-restore.json \
  --wb-live-data-proof /secure/evidence/wb-live-data.json \
  --accuracy-input /secure/evidence/accuracy-input.json \
  --sber-sandbox-proof /secure/evidence/sber-sandbox.json \
  --artifact ci=/secure/evidence/ci.json \
  --artifact deployment=/secure/evidence/deployment.json \
  --artifact core_smoke=/secure/evidence/release-smoke.json \
  --artifact account_lifecycle=/secure/evidence/release-smoke.json \
  --artifact ux_smoke=/secure/evidence/ux-smoke.json \
  --artifact secrets_review=/secure/evidence/secrets-review.json \
  --artifact data_accuracy=/secure/evidence/data-accuracy.json \
  --output /secure/evidence/release-manifest.json

# Если Sber sandbox credentials недоступны, просто не передавайте --sber-sandbox-proof.
```

Для private repository `ops/ci_acceptance.py` получает `GITHUB_TOKEN` через environment/secret manager. Значение токена в report не попадает. При необходимости GitHub API payload можно заранее сохранить защищённо и передать через `--runs-json`.

Путь к runtime env в примере условный: на конкретном host нужно передать фактический защищённый файл или экспортировать переменные через secret manager. `ops/database_upgrade_acceptance.py` и `ops/secrets_review.py` не записывают значения этих секретов в evidence.

`SMOKE_EMAIL`/`SMOKE_PASSWORD` используются и core smoke, и read-only payment acceptance; они предполагаются переданными через environment/secret manager. `SMOKE_DISPOSABLE_EMAIL_TEMPLATE` и `SMOKE_MAIL_TOKEN_COMMAND` также не должны попадать в evidence.

UX template нельзя отмечать `pass` без фактической проверки: `ops/ux_acceptance.py` проверяет полноту, release binding и integrity файлов, но не заменяет человеческую визуальную оценку.

Наличие файлов само по себе не заменяет реальное выполнение проверок. Manifest обеспечивает полноту набора, stage/version binding и целостность artifacts; factual provenance human UX review и real-seller data-accuracy evidence должна сохраняться владельцем релиза.

## RC evidence

Для `rc` требуется весь beta-набор и дополнительно:

- `wb_full_sync` — реальный production WB credential/full-sync smoke;
- `sber_payment` — реальный acquiring/refund/reconciliation smoke;
- `operations` — active monitoring/alerts/logging evidence;
- `backup_restore` — off-host encrypted backup и production-like restore drill;
- `legal` — опубликованные non-draft legal documents и operator details.

`deployment` и `account_lifecycle` уже являются обязательной частью beta contract и повторно не добавляются только на RC.

## Stable evidence

Для `stable` требуется весь RC набор плюс `rc_signoff` — итоговое подтверждение, что стабильная версия выпускается из проверенного RC без новых функциональных изменений.

## Exit codes

- `0` — все обязательные artifacts присутствуют и проходят встроенную валидацию;
- `1` — manifest создан, но обязательных artifact kinds не хватает;
- `2` — ошибка version/stage/commit/environment, неизвестный/пустой/невалидный artifact или другая ошибка входных данных.

## Хранение

Release evidence должно храниться отдельно от application secrets и обычных логов. Допустимо защищённое object storage или другой immutable/retention-controlled storage.

В evidence запрещено включать:

- WB seller token;
- `WB_SERVICE_SECRET`;
- Sber merchant password;
- access/refresh JWT;
- backup passphrase;
- raw customer personal data.

Если доказательство содержит чувствительные operational details, в manifest достаточно SHA-256 самого защищённого файла.

## Имена artifacts

Названия kind являются частью release contract и не меняются произвольно:

- `ci`
- `deployment`
- `core_smoke`
- `account_lifecycle`
- `ux_smoke`
- `secrets_review`
- `data_accuracy`
- `wb_full_sync`
- `sber_payment`
- `operations`
- `backup_restore`
- `legal`
- `rc_signoff`

`database-upgrade.json`, `payment-isolation.json`, `backup-restore.json`, `wb-live-data.json` и защищённый `accuracy-input.json` участвуют в P40 как связанные sub-proofs, а не как новые top-level artifact kinds beta contract. Database-upgrade SHA-256-bound внутри `deployment.json`; payment isolation хранится в `candidate_subproofs.payment_isolation`; strict `ops/beta_release_evidence.py` дополнительно требует и hash-bind'ит backup/restore, live-WB proof и исходный accuracy input. `sber-sandbox.json` — условный P40 sub-proof: при наличии test merchant credentials он валидируется и записывается в `candidate_subproofs.sber_sandbox`, но beta gate не фальсифицирует его наличие, если таких credentials нет.

Новый обязательный gate добавляется в runner, `RELEASE_READINESS.md`, `RELEASE_ROADMAP.md` и этот документ одним PR.
