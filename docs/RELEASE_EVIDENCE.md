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

Начиная с P40 для фактического beta/RC/stable promotion используется дополнительный флаг `--require-structured-runtime-evidence`. Он запрещает подменить ключевые runtime gates произвольными текстовыми файлами и требует machine-readable evidence для `deployment`, `core_smoke`, `account_lifecycle` и `secrets_review`.

## Structured runtime evidence

`deployment` создаётся `ops/systemd_acceptance.py`. Строгая проверка связывает его с теми же `VERSION`, commit и environment, что и manifest, и требует:

- clean exact-head checkout целевой ветки;
- immutable `venv.release.*` и Python 3.12;
- поддерживаемый Node;
- active/enabled backend, Celery worker и Beat;
- Celery ping;
- Alembic current=head;
- валидный nginx config;
- local readiness;
- публичный HTTPS readiness;
- опубликованный frontend bundle текущей сборки;
- SHA-256 отдельного rollback-drill proof.

`core_smoke` и `account_lifecycle` создаются одним полным прогоном `ops/release_smoke.py --evidence-output ...`. Строгая проверка требует HTTPS origin и подтверждённые flags disposable registration, реального email verification, demo activation, legal evidence, refresh/deactivation, authenticated flow, P37 audit correlation и logout. Для `account_lifecycle` дополнительно обязателен реальный password reset через почтовый provider.

Один и тот же sanitized `release-smoke.json` допустимо привязать как `core_smoke` и `account_lifecycle`: manifest всё равно фиксирует его SHA-256 отдельно для каждого kind.

`secrets_review` создаётся `ops/secrets_review.py`. Scanner не сохраняет значения секретов и не копирует совпавшие строки. Он сравнивает реально настроенные secret values с:

- tracked worktree;
- всеми reachable Git blobs;
- `frontend/dist` текущей сборки;
- bounded systemd journal backend/Celery/Beat;
- дополнительными log paths, если они переданы оператором.

Для runtime/frontend дополнительно ищутся JWT-shaped values. Structured gate требует `status=pass`, ноль findings, совпадающие VERSION/commit/environment, выполненные Git-history и journal scans и наличие проверки обязательных production secrets (`DB_PASSWORD`, encryption/JWT/legal-evidence/WB service secrets). Условные SMTP/Sber secrets проверяются автоматически, когда реально настроены.

## Beta evidence

Для `beta` обязательны все следующие artifacts:

- `ci` — подтверждение green CI exact head;
- `deployment` — evidence production-like HTTPS deployment, migration/upgrade и deploy/rollback smoke;
- `core_smoke` — результат production-like `ops/release_smoke.py` без отключения disposable registration;
- `account_lifecycle` — login/refresh/logout/deactivation и реальный password-recovery smoke через настроенный SMTP/provider;
- `ux_smoke` — подтверждение основных desktop/mobile сценариев и критичных empty/loading/error states;
- `secrets_review` — machine-readable проверка отсутствия настроенных secrets/JWT в frontend, Git и runtime logs;
- `data_accuracy` — green JSON-результат `ops/data_accuracy_acceptance.py` на реальном WB seller dataset.

Канонический P40 пример:

```bash
python3 ops/systemd_acceptance.py \
  --environment staging-eu-1 \
  --public-base-url https://staging.example.com \
  --rollback-proof /secure/evidence/rollback-drill.txt \
  --require-rollback-proof \
  --output /secure/evidence/deployment.json

python3 ops/release_smoke.py \
  --base-url https://staging.example.com \
  --require-email-verification \
  --require-password-reset \
  --audit-smoke \
  --evidence-output /secure/evidence/release-smoke.json

python3 ops/secrets_review.py \
  --environment staging-eu-1 \
  --env-file /secure/runtime/wb-insight.env \
  --output /secure/evidence/secrets-review.json

RELEASE_SHA="$(git rev-parse HEAD)"
python3 ops/release_evidence.py \
  --stage beta \
  --environment staging-eu-1 \
  --commit "$RELEASE_SHA" \
  --require-structured-runtime-evidence \
  --artifact ci=/secure/evidence/ci.txt \
  --artifact deployment=/secure/evidence/deployment.json \
  --artifact core_smoke=/secure/evidence/release-smoke.json \
  --artifact account_lifecycle=/secure/evidence/release-smoke.json \
  --artifact ux_smoke=/secure/evidence/ux-smoke.txt \
  --artifact secrets_review=/secure/evidence/secrets-review.json \
  --artifact data_accuracy=/secure/evidence/data-accuracy.json \
  --output /secure/evidence/release-manifest.json
```

Путь к runtime env в примере условный: на конкретном host нужно передать фактический защищённый файл или экспортировать переменные через secret manager. `ops/secrets_review.py` не записывает их значения в evidence.

Переменные `SMOKE_EMAIL`, `SMOKE_PASSWORD`, `SMOKE_DISPOSABLE_EMAIL_TEMPLATE` и `SMOKE_MAIL_TOKEN_COMMAND` в примере предполагаются переданными через environment/secret manager и не должны попадать в evidence.

Наличие файлов само по себе не заменяет реальное выполнение проверок. Manifest обеспечивает полноту набора, stage/version binding и целостность artifacts; factual provenance внешних UX/data-accuracy evidence должна сохраняться владельцем релиза.

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

Новый обязательный gate добавляется в runner, `RELEASE_READINESS.md`, `RELEASE_ROADMAP.md` и этот документ одним PR.
