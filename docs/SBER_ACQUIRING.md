# Интернет-эквайринг Сбера — WB Insight

Актуально для WB Insight Web v1 на 15 сентября 2026 года.

## Сценарий оплаты

WB Insight использует одностадийную регистрацию заказа через платёжный шлюз Сбера.

1. Frontend создаёт локальную платёжную попытку с `Idempotency-Key`.
2. Backend создаёт `Payment(status=pending, provider=sber)`.
3. Backend вызывает `register.do` server-to-server.
4. Сумма передаётся в минимальных единицах валюты (для RUB — копейки), валюта — `643`.
5. Сбер возвращает `orderId` и `formUrl`.
6. Backend сохраняет `orderId`, а frontend переводит покупателя на `formUrl`.
7. Возврат пользователя на `returnUrl` **не является доказательством оплаты**.
8. Callback Сбера **не является источником истины**: он только запускает повторную проверку.
9. Backend вызывает `getOrderStatusExtended.do` с merchant credentials и `orderId`.
10. Подписка активируется только если server-to-server ответ подтверждает `orderStatus=2` и `paymentState=DEPOSITED`.

Таким образом пользователь не может активировать тариф, подделав redirect/callback URL.

## Idempotency

Frontend генерирует один `Idempotency-Key` на одну попытку оплаты и повторно использует его при сетевом retry.

В БД действует уникальность:

`(user_id, provider, idempotency_key)`.

Повторный `create-payment` с тем же ключом и тем же тарифом возвращает существующий payment/form URL. Использование ключа для другой суммы или тарифа возвращает conflict.

Подписка содержит уникальный `payment_id`. Даже если callback и пользовательский `/confirm` приходят одновременно, payment блокируется `SELECT ... FOR UPDATE`, а одна и та же оплата не может создать две подписки.

## События платежей

`payment_events` хранит append-only технический журнал:

- registration/error;
- callback received;
- verified provider status;
- normalized provider status.

В журнал намеренно не записываются merchant username/password, полный callback body, PAN/email и другие неизвестные поля провайдера.

## Переменные окружения

```bash
SBER_ACQUIRING_ENABLED=true
SBER_API_BASE_URL=https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1
SBER_USERNAME=<sandbox merchant login>
SBER_PASSWORD=<sandbox merchant password>
SBER_RETURN_URL=https://app.example.com/billing/success
SBER_FAIL_URL=https://app.example.com/billing/success
SBER_CURRENCY_CODE=643
SBER_HTTP_TIMEOUT_SECONDS=10
```

Sandbox URL — только для development/staging. При `APP_ENV=production` приложение отказывается стартовать, если acquiring включён, но `SBER_API_BASE_URL` указывает на `ecomift.sberbank.ru`.

Production merchant credentials должны поступать из secret manager/deployment environment и никогда не попадать в git, frontend environment или лог.

## Управляемая конфигурация из Control Panel

Настройки Сбера из Control Panel проходят тот же fail-closed security contract до того, как могут стать рабочим payment runtime.

- `api_base_url` обязан использовать HTTPS без встроенных credentials, query и fragment;
- базовый путь шлюза должен быть ровно `/ecomm/gw/partner/api/v1`;
- test-режим допускает только `ecomift.sberbank.ru` и `ecomtest.sberbank.ru`;
- live-режим запрещает sandbox-hosts и допускает только шлюз в домене `sberbank.ru`;
- уже сохранённый небезопасный gateway остаётся видимым администратору, но runtime получает `ready=false` и не используется для checkout/status verification;
- в production `return_url` и `fail_url` должны использовать HTTPS;
- код валюты должен состоять ровно из трёх цифр;
- timeout должен быть конечным числом больше 0 и не больше 120 секунд.

Изменение provider config выполняется внутри вложенной транзакции/savepoint. Если финальная проверка readiness отклоняет конфигурацию, изменения откатываются внутри savepoint до того, как handler вернёт `400`; частично записанная конфигурация не должна сохраняться.

Control Panel показывает рекомендуемые gateway для test/live. Backend остаётся источником истины и повторно валидирует все значения независимо от браузера.

## Callback Сбера

Backend endpoint:

`GET|POST /billing/sber/callback`

Из callback используются только известные идентификаторы/служебные поля (`mdOrder`/`orderId`, `orderNumber`, `operation`, `status`). После нахождения локального платежа backend всегда самостоятельно запрашивает расширенный статус у Сбера перед изменением подписки.

В личном кабинете интернет-эквайринга callback URL должен указывать на публичный HTTPS backend endpoint.

## P40-проверка sandbox merchant

Для production-like beta acceptance используется отдельный secret-safe probe `ops/sber_sandbox_acceptance.py`. Он не создаёт локальную подписку и не принимает card data: через тот же backend adapter создаётся один **неоплаченный** sandbox order, затем выполняется `getOrderStatusExtended.do`.

Acceptance credentials передаются только через environment:

```bash
export ACCEPTANCE_ENVIRONMENT=staging-eu-1
export SMOKE_BASE_URL=https://staging.example.com
export SBER_TEST_API_BASE_URL=https://ecomtest.sberbank.ru/ecomm/gw/partner/api/v1
export SBER_TEST_USERNAME='<sandbox merchant login>'
export SBER_TEST_PASSWORD='<sandbox merchant password>'

/home/projects/wb/backend/venv/bin/python ops/sber_sandbox_acceptance.py \
  --output /secure/evidence/sber-sandbox.json
```

Runner привязывает evidence к exact `VERSION`, Git commit, environment и публичному HTTPS origin. Passing proof требует, что merchant credentials приняты sandbox gateway, order зарегистрирован, payment-form URL использует HTTPS, status query проходит, а acceptance order остаётся неоплаченным.

В `sber-sandbox.json` не сохраняются merchant login/password, gateway URL, Sber order id или payment-form URL. При ошибке сохраняется только стабильный error code. Сам sandbox order намеренно остаётся неоплаченным и может быть удалён/архивирован по правилам merchant sandbox кабинета.

Этот probe — дополнительное P40 evidence, когда test merchant credentials реально доступны. Он не заменяет production acquiring smoke перед RC/stable и не разрешает включать live acquiring без HTTPS/domain и production merchant onboarding.

## Перед production-релизом

Кодовая интеграция не заменяет merchant onboarding. До включения `SBER_ACQUIRING_ENABLED=true` в production необходимо:

- заключить/активировать интернет-эквайринг;
- получить отдельные test и production credentials;
- уточнить production gateway URL для договора;
- зарегистрировать HTTPS return/fail/callback URLs;
- провести sandbox сценарии success / decline / cancel / retry / duplicate callback;
- провести production smoke с минимально допустимой реальной оплатой и сверить операцию в merchant back office;
- проверить возврат/отмену по договорному процессу, прежде чем обещать self-service refund в интерфейсе.

## Официальные источники

- https://developers.sber.ru/docs/ru/sberpay-sdk/signup/sign-up-ecom
- https://developers.sber.ru/docs/ru/sberpay-sdk/web/signup/sign-up-ecom
- Общая документация шлюза, на которую ссылается Сбер: https://ecomtest.sberbank.ru/doc#tag/basicServices/operation/register
