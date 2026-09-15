# WB Insight — release evidence

Release stage повышается только для конкретной версии и конкретного commit. Этот документ задаёт формат доказательств, которые подтверждают прохождение соответствующих gates.

## Зачем нужен manifest

Скриншоты, логи и ручные заметки быстро теряют связь с точной сборкой. `ops/release_evidence.py` создаёт manifest, который фиксирует:

- release stage;
- `VERSION`;
- commit SHA;
- environment;
- UTC timestamp;
- обязательные типы evidence;
- имя, размер и SHA-256 каждого evidence-файла.

Manifest не копирует содержимое artifacts и не предназначен для хранения секретов.

## Beta evidence

Для `beta` обязательны:

- `ci` — подтверждение green CI exact head;
- `core_smoke` — результат production-like `ops/release_smoke.py`;
- `data_accuracy` — green результат `ops/data_accuracy_acceptance.py`.

Пример:

```bash
python3 ops/release_evidence.py \
  --stage beta \
  --environment staging-eu-1 \
  --commit "$RELEASE_SHA" \
  --artifact ci=/secure/evidence/ci.txt \
  --artifact core_smoke=/secure/evidence/core-smoke.txt \
  --artifact data_accuracy=/secure/evidence/data-accuracy.json \
  --output /secure/evidence/release-manifest.json
```

## RC evidence

Для `rc` к beta evidence добавляются:

- `wb_full_sync`;
- `sber_payment`;
- `deployment`;
- `operations`;
- `backup_restore`;
- `legal`;
- `account_lifecycle`.

Это соответствует Definition of Done: реальный WB sync, acquiring, production deployment/TLS, активная эксплуатационная наблюдаемость, off-host backup/restore, non-draft legal и закрытый account lifecycle.

## Stable evidence

Для `stable` требуется весь RC набор плюс `rc_signoff` — итоговое подтверждение, что стабильная версия выпускается из проверенного RC без новых функциональных изменений.

## Exit codes

- `0` — все обязательные artifact kinds присутствуют;
- `1` — manifest создан, но обязательных artifacts не хватает;
- `2` — ошибка входных аргументов/файлов.

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
- `core_smoke`
- `data_accuracy`
- `wb_full_sync`
- `sber_payment`
- `deployment`
- `operations`
- `backup_restore`
- `legal`
- `account_lifecycle`
- `rc_signoff`

Новый обязательный gate добавляется в runner, `RELEASE_READINESS.md`, `RELEASE_ROADMAP.md` и этот документ одним PR.
