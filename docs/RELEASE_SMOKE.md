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
- реальный nginx container routing для `/auth`, `/dashboard`, `/billing`, `/legal`, `/account`, `/control-panel`, `/health`;
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

Runner не должен печатать passwords, access/refresh tokens, marketplace credentials или raw PII test-user values.

По умолчанию полный core smoke состоит из двух изолированных частей:

1. disposable registration lifecycle на отдельном временном аккаунте;
2. основной smoke через заранее подготовленного пользователя из `SMOKE_EMAIL`/`SMOKE_PASSWORD`.

Core checks:

1. `/health/live` и deployed version;
2. `/health/ready`;
3. legal registry для registration/billing/marketplace contexts;
4. disposable registration с актуальными legal documents;
5. активная demo subscription после регистрации;
6. точные persisted consent `document_code/version/SHA-256` через authenticated `/legal/consents/me`;
7. cookie-only refresh restore disposable account;
8. soft-deactivation disposable account;
9. невозможность refresh/login после деактивации;
10. login основного smoke user;
11. protected profile API;
12. cookie-only session restore после потери in-memory access token;
13. dashboard API contract;
14. logout;
15. невозможность refresh после logout.

Disposable account создаётся с уникальными synthetic email/phone и после проверки soft-deactivate-ится. Он не hard-delete-ится, потому что текущая lifecycle policy намеренно сохраняет retention/audit evidence до утверждения окончательной legal policy.

Только public checks:

```bash
python3 ops/release_smoke.py --base-url https://staging.example.com --public-only
```

Для специализированного окружения disposable registration можно **явно** отключить:

```bash
python3 ops/release_smoke.py --skip-disposable-registration
```

или `SMOKE_SKIP_DISPOSABLE_REGISTRATION=true`. Такой прогон не закрывает beta gate disposable registration/demo/legal evidence.

Sanitized output полного core smoke сохраняется как evidence kind `core_smoke`.

## 3. Disposable registration smoke contract

Начиная с P32 disposable flow встроен в `ops/release_smoke.py` и запускается по умолчанию для любого непубличного полного smoke.

Runner обязан доказать:

1. получение актуальных registration legal requirements;
2. успешное создание уникального test user;
3. создание активной `demo` subscription;
4. наличие immutable consent evidence с точными текущими document version/SHA-256;
5. cookie-only session restore;
6. успешную self-service soft-deactivation;
7. отсутствие действующего refresh session после деактивации;
8. отказ повторного login с `USER_INACTIVE`.

Read-only `/legal/consents/me` возвращает только consent audit fields и намеренно не возвращает privacy-sensitive `ip_hmac`/`user_agent_hmac`.

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
