# WB Insight — live WB/data provenance gate

Перед `0.9.0-beta.1` passing `data-accuracy.json` должен быть связан с тем же реальным Wildberries-кабинетом, который прошёл live credential validation на production-like deployment. Одного вручную подготовленного JSON недостаточно.

## Что делает runner

`ops/wb_live_data_acceptance.py`:

1. авторизуется тестовым seller account через публичный HTTPS origin;
2. получает актуальные legal requirements для `marketplace_credential`;
3. временно добавляет реальный WB token через штатный API, поэтому используется тот же live validation path, что и у пользователя;
4. берёт возвращённый `external_account_id`, но **не сохраняет его** — вместо этого строит HMAC-SHA256 fingerprint с отдельным `WB_ACCEPTANCE_FINGERPRINT_KEY`;
5. в `finally` удаляет временный credential;
6. проверяет, что `accuracy-input.json` содержит тот же `wb_account_fingerprint`;
7. проверяет SHA-256 связи input → passing `data-accuracy.json`, отсутствие `fail/missing` и минимум три acceptance-периода;
8. создаёт `wb-live-data.json`, связанный с exact VERSION/commit/environment/public origin.

Evidence не содержит password, access/refresh JWT, WB token, fingerprint key, raw external account id, seller email или реальные денежные значения.

## Секреты

Не передавайте password/WB token/fingerprint key аргументами командной строки. Runner намеренно читает их только из environment/secret manager:

```bash
export WB_ACCEPTANCE_PASSWORD='...'
export WB_ACCEPTANCE_TOKEN='...'
export WB_ACCEPTANCE_FINGERPRINT_KEY='...at-least-16-bytes...'
```

`WB_ACCEPTANCE_EMAIL` и `WB_ACCEPTANCE_BASE_URL` также можно передавать через environment.

## Подготовка fingerprint

Сначала выполните безопасный probe. Он создаёт временный credential, валидирует его у WB и удаляет его; наружу выводится только keyed fingerprint:

```bash
python3 ops/wb_live_data_acceptance.py \
  --base-url https://staging.example.com \
  --email seller-acceptance@example.com \
  --fingerprint-only
```

Полученный `wb_account_fingerprint=<64 hex>` добавляется в защищённый `accuracy-input.json` рядом с `seller_alias`:

```json
{
  "dataset_id": "seller-acceptance-2026-09",
  "seller_alias": "seller-01",
  "wb_account_fingerprint": "<64 hex>",
  "periods": [
    {"label": "period-1", "start_date": "...", "end_date": "...", "metrics": []},
    {"label": "period-2", "start_date": "...", "end_date": "...", "metrics": []},
    {"label": "period-3", "start_date": "...", "end_date": "...", "metrics": []}
  ]
}
```

Каждый реальный период по-прежнему обязан содержать полный набор required metrics из `ops/acceptance/wb_v1_metric_policy.json`; сокращённый пример выше показывает только provenance field.

После заполнения всех реальных значений сначала создаётся обычный data-accuracy report:

```bash
python3 ops/data_accuracy_acceptance.py \
  --input /secure/evidence/accuracy-input.json \
  --output-json /secure/evidence/data-accuracy.json \
  --output-md /secure/evidence/data-accuracy.md
```

Затем live binding запускается повторно тем же fingerprint key и WB account:

```bash
RELEASE_SHA="$(git rev-parse HEAD)"
export RELEASE_SHA
export ACCEPTANCE_ENVIRONMENT=staging-eu-1

python3 ops/wb_live_data_acceptance.py \
  --base-url https://staging.example.com \
  --email seller-acceptance@example.com \
  --accuracy-input /secure/evidence/accuracy-input.json \
  --data-accuracy /secure/evidence/data-accuracy.json \
  --output /secure/evidence/wb-live-data.json
```

Если реальный credential принадлежит другому seller account, fingerprint не совпадёт и gate завершится ошибкой.

## Beta manifest

`ops/beta_release_evidence.py` теперь требует `--wb-live-data-proof` и сам защищённый `--accuracy-input`. Он проверяет:

- exact VERSION/commit/environment;
- HTTPS origin;
- совпадение origin с deployment evidence;
- SHA-256 привязку proof → `data_accuracy` report → исходный accuracy input;
- совпадение account fingerprint в input и live proof;
- успешную live WB credential validation + cleanup;
- passing data accuracy и минимум три периода.

Пример фрагмента финальной команды:

```bash
python3 ops/beta_release_evidence.py \
  --environment "$ACCEPTANCE_ENVIRONMENT" \
  --commit "$RELEASE_SHA" \
  --payment-proof /secure/evidence/payment-isolation.json \
  --backup-restore-proof /secure/evidence/backup-restore.json \
  --wb-live-data-proof /secure/evidence/wb-live-data.json \
  --accuracy-input /secure/evidence/accuracy-input.json \
  --artifact data_accuracy=/secure/evidence/data-accuracy.json \
  ... \
  --output /secure/evidence/release-manifest.json
```

В итоговом manifest хранятся только SHA-256/размер/имя `wb-live-data.json` и защищённого accuracy input в `candidate_subproofs`; чувствительные seller данные остаются в защищённом evidence storage.
