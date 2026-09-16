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

## Beta evidence

Для `beta` обязательны все следующие artifacts:

- `ci` — подтверждение green CI exact head;
- `deployment` — evidence production-like HTTPS deployment, migration/upgrade и deploy/rollback smoke;
- `core_smoke` — результат production-like `ops/release_smoke.py` без отключения disposable registration;
- `account_lifecycle` — login/refresh/logout/deactivation и реальный password-recovery smoke через настроенный SMTP/provider;
- `ux_smoke` — подтверждение основных desktop/mobile сценариев и критичных empty/loading/error states;
- `secrets_review` — проверка отсутствия secrets/JWT/WB credentials в frontend bundle, git и логах;
- `data_accuracy` — green JSON-результат `ops/data_accuracy_acceptance.py` на реальном WB seller dataset.

Пример:

```bash
python3 ops/release_evidence.py \
  --stage beta \
  --environment staging-eu-1 \
  --commit "$RELEASE_SHA" \
  --artifact ci=/secure/evidence/ci.txt \
  --artifact deployment=/secure/evidence/deployment.txt \
  --artifact core_smoke=/secure/evidence/core-smoke.txt \
  --artifact account_lifecycle=/secure/evidence/account-lifecycle.txt \
  --artifact ux_smoke=/secure/evidence/ux-smoke.txt \
  --artifact secrets_review=/secure/evidence/secrets-review.txt \
  --artifact data_accuracy=/secure/evidence/data-accuracy.json \
  --output /secure/evidence/release-manifest.json
```

Наличие файлов само по себе не заменяет реальное выполнение проверок. Manifest обеспечивает полноту набора, stage/version binding и целостность artifacts; factual provenance внешних smoke/evidence должна сохраняться владельцем релиза.

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
