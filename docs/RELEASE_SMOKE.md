# WB Insight — release smoke

Документ фиксирует обязательную проверку сборки перед переходом `alpha -> beta -> rc -> stable`.

## Уровни smoke

Release smoke разделён на три уровня, потому что CI не располагает реальными seller credentials, merchant account и production инфраструктурой.

### 1. CI smoke — выполняется на каждом release PR

Автоматически проверяется:

- backend test suite;
- frontend production build;
- запрет сохранения `access_token` и user identity в `localStorage`/`sessionStorage`;
- Alembic upgrade/check на чистом PostgreSQL;
- production Docker images;
- production Compose model;
- реальный nginx container routing для `/auth`, `/dashboard`, `/billing`, `/legal`, `/control-panel`, `/health`;
- encrypted PostgreSQL backup/restore roundtrip.

CI smoke не доказывает доступность Wildberries или Сбер из production environment.

### 2. Production-like smoke — `ops/release_smoke.py`

Запускается против уже развёрнутого HTTPS environment.

Обязательные переменные:

```bash
export SMOKE_BASE_URL=https://staging.example.com
export SMOKE_EMAIL=release-smoke@example.com
export SMOKE_PASSWORD='...'
python3 ops/release_smoke.py
```

Smoke runner не печатает пароль, JWT, refresh cookie или WB token.

Проверяется:

1. `/health/live` и точная deployed version;
2. `/health/ready`;
3. legal registry для registration, billing и marketplace credential contexts;
4. login;
5. protected profile API;
6. удаление access JWT из памяти клиента и восстановление session только через HttpOnly refresh cookie;
7. dashboard API contract;
8. logout;
9. невозможность refresh после logout.

Только публичные проверки:

```bash
python3 ops/release_smoke.py --base-url https://staging.example.com --public-only
```

### 3. External integration smoke

#### Wildberries

В dedicated staging/smoke account можно передать:

```bash
export SMOKE_WB_TOKEN='...'
python3 ops/release_smoke.py
```

Runner:

- получает актуальные marketplace legal requirements;
- выполняет live validation seller credential;
- сохраняет credential;
- проверяет успешный API response;
- удаляет созданный credential в `finally` cleanup.

Токен не выводится в stdout/stderr.

После этого отдельно проверяется полный Celery sync и наличие фактов во всех разделах: orders/sales, products/stocks, prices, ads, funnel, paid storage и finance.

#### Сбер

Для sandbox или заранее разрешённого production smoke:

```bash
export SMOKE_BILLING_TARIFF=pro
python3 ops/release_smoke.py
```

Runner создаёт новый idempotent payment attempt и печатает только внутренний `payment_id`. Если provider вернул payment page, оператор завершает платёж вручную, после чего обязательны:

- server-side confirmation;
- активная subscription, связанная с тем же payment;
- duplicate callback/refresh без второй subscription;
- сверка статуса в merchant back office.

Нельзя запускать billing phase на боевом тарифе без заранее согласованного smoke-платежа.

## Регистрация

Полный RC smoke должен также проверять регистрацию нового пользователя с актуальными legal consent. Этот шаг выполняется в disposable staging environment или с заранее определённой процедурой очистки тестового пользователя. Нельзя создавать бесконтрольные smoke accounts в production.

Обязательная последовательность:

1. получить `/legal/requirements/registration` или `registration_legal`;
2. создать уникальный smoke account;
3. убедиться, что создана demo subscription;
4. убедиться, что в `legal_consents` зафиксированы точные version/SHA-256/timestamp;
5. продолжить session/WB/dashboard/billing smoke;
6. удалить/деактивировать smoke account по утверждённой operational procedure.

## Полный WB Web v1 release smoke

Перед `1.0.0-rc.1` должны быть подтверждены все шаги:

- [ ] регистрация нового disposable smoke user;
- [ ] legal consent evidence регистрации;
- [ ] demo subscription;
- [ ] login и refresh после reload без persistent access JWT;
- [ ] подключение реального WB seller account;
- [ ] полный sync без необъяснённых 401/403;
- [ ] Overview;
- [ ] Unit Economy;
- [ ] Finance/Reconciliation;
- [ ] Inventory;
- [ ] Prices;
- [ ] Ads;
- [ ] COGS и manual expenses;
- [ ] monthly revenue plan;
- [ ] Sber payment init;
- [ ] success payment confirmation;
- [ ] paid subscription activation;
- [ ] duplicate callback/idempotency;
- [ ] logout и невозможность refresh после logout;
- [ ] удаление WB credential;
- [ ] monitoring получает ожидаемые operational signals;
- [ ] encrypted off-host backup создан;
- [ ] restore drill успешен.

## Release evidence

Для каждого beta/RC/stable прогона сохраняются:

- commit SHA и version;
- environment;
- дата/время UTC;
- результат CI workflows;
- результат `release_smoke.py` без секретов;
- WB sync evidence;
- Sber merchant back-office evidence;
- backup/restore drill result;
- список известных release blockers.

Секреты, JWT, refresh cookies, seller credentials и merchant passwords в release evidence не сохраняются.
