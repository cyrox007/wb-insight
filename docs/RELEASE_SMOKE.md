# WB Insight — release smoke

Документ фиксирует обязательные проверки перед переходами `alpha -> beta -> rc -> stable`.

## 1. CI smoke

На release PR автоматически проверяются:

- backend dependency audit и test suite;
- frontend production/full dependency audits;
- frontend production build;
- запрет persistent browser storage для `access_token`;
- Alembic upgrade/check на чистом PostgreSQL;
- production Docker images;
- Compose model;
- реальный nginx container routing для `/auth`, `/dashboard`, `/billing`, `/legal`, `/control-panel`, `/health`;
- encrypted PostgreSQL backup/restore roundtrip;
- consistency canonical product version;
- acceptance-tools positive/negative contracts.

Изменение `VERSION` запускает backend security и database migrations, поэтому release-candidate metadata не обходит эти gates.

CI smoke не доказывает доступность WB/Сбер из production environment и не доказывает корректность денежных показателей на реальном кабинете.

## 2. Production-like core smoke

Runner: `ops/release_smoke.py`. Запускается против отдельного HTTPS environment.

```bash
export SMOKE_BASE_URL=https://staging.example.com
export SMOKE_EMAIL=release-smoke@example.com
export SMOKE_PASSWORD='...'
python3 ops/release_smoke.py
```

Runner не должен печатать credentials/session values.

Core checks:

1. `/health/live` и deployed version;
2. `/health/ready`;
3. legal registry для registration/billing/marketplace contexts;
4. login;
5. protected profile API;
6. cookie-only session restore после потери in-memory access token;
7. dashboard API contract;
8. logout;
9. невозможность refresh после logout.

Только public checks:

```bash
python3 ops/release_smoke.py --base-url https://staging.example.com --public-only
```

Sanitized output core smoke сохраняется как evidence kind `core_smoke`.

## 3. Disposable registration smoke

Для beta/RC в disposable staging environment:

1. получить актуальные registration legal requirements;
2. создать уникального test user;
3. проверить demo subscription;
4. проверить точные document version/SHA-256/timestamp в consent evidence;
5. продолжить session/dashboard smoke;
6. удалить/деактивировать test account утверждённым способом.

## 4. Wildberries integration smoke

В dedicated seller account runner может использовать отдельно переданный `SMOKE_WB_TOKEN`.

Проверяется:

- актуальный marketplace legal requirement;
- live credential validation;
- успешное сохранение подключения;
- cleanup созданного credential;
- затем полный Celery sync: orders/sales, products/stocks, prices, ads, funnel, paid storage, finance;
- отсутствие необъяснённых auth/permission/rate-limit ошибок.

Для RC sanitized результат полного sync сохраняется как evidence kind `wb_full_sync`.

## 5. Data-accuracy acceptance

До beta выбираются фиксированные периоды реального seller account и сравниваются WB Insight, официальные WB-источники и, где применимо, исходная spreadsheet-модель.

Минимум сверяются:

- orders/sales/returns;
- revenue;
- commissions;
- logistics/storage;
- advertising;
- COGS/manual expenses/taxes;
- profit;
- payout/reconciliation;
- inventory/prices;
- unit-economy ratios.

Канонический runner: `ops/data_accuracy_acceptance.py`. Policy: `ops/acceptance/wb_v1_metric_policy.json`. Подробности: `DATA_ACCURACY_ACCEPTANCE.md`.

Для каждого существенного расхождения сохраняется причина или bug reference. Необъяснённое денежное расхождение блокирует повышение release stage. Green JSON output сохраняется как evidence kind `data_accuracy`.

## 6. Сбер acquiring smoke

Для sandbox или заранее согласованного production test:

```bash
export SMOKE_BILLING_TARIFF=pro
python3 ops/release_smoke.py
```

Проверяются:

- payment attempt;
- provider payment page;
- server-side status confirmation;
- paid subscription activation;
- duplicate callback/status refresh без второй subscription;
- decline/cancel/retry;
- сверка с merchant back office.

Для RC sanitized proof сохраняется как evidence kind `sber_payment`.

## 7. Operations smoke

Перед RC дополнительно подтверждаются:

- внешний uptime monitor видит `/health/ready`;
- alert destination получает test signal;
- structured logs доступны для incident triage;
- encrypted backup создан и перенесён off-host;
- isolated restore drill успешен;
- фактические RPO/RTO записаны;
- deploy/rollback procedure проверена.

Результаты входят в evidence kinds `operations`, `backup_restore` и `deployment`.

## Полный WB Web v1 RC checklist

- [ ] disposable registration;
- [ ] legal consent evidence;
- [ ] demo subscription;
- [ ] login/refresh/logout без persistent access JWT;
- [ ] реальный WB seller connection;
- [ ] полный WB sync;
- [ ] data-accuracy acceptance;
- [ ] Overview;
- [ ] Unit Economy;
- [ ] Finance/Reconciliation;
- [ ] Inventory;
- [ ] Prices;
- [ ] Ads;
- [ ] COGS/manual expenses/revenue plan;
- [ ] Sber success/decline/cancel/retry/idempotency;
- [ ] paid subscription activation;
- [ ] removal WB credential;
- [ ] monitoring/alerts/logging;
- [ ] off-host backup;
- [ ] restore drill;
- [ ] deploy/rollback evidence;
- [ ] account lifecycle/support procedures;
- [ ] non-draft legal documents.

## Release evidence

После фактического прогона evidence связывается с exact commit/version командой `ops/release_evidence.py`; contract описан в `RELEASE_EVIDENCE.md`.

Для beta обязательны как минимум `ci`, `core_smoke`, `data_accuracy`. RC и stable требуют расширенный набор согласно manifest contract.

Release evidence не должно содержать пароли, session values, marketplace access data, merchant credentials или raw customer PII.
