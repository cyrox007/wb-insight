# Sber internet acquiring — WB Insight

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

## Payment events

`payment_events` хранит append-only технический журнал:

- registration/error;
- callback received;
- verified provider status;
- normalized provider status.

В журнал намеренно не записываются merchant username/password, полный callback body, PAN/email и другие неизвестные поля провайдера.

## Environment

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

## Callback

Backend endpoint:

`GET|POST /billing/sber/callback`

Из callback используются только известные идентификаторы/служебные поля (`mdOrder`/`orderId`, `orderNumber`, `operation`, `status`). После нахождения локального платежа backend всегда самостоятельно запрашивает расширенный статус у Сбера перед изменением подписки.

В личном кабинете интернет-эквайринга callback URL должен указывать на публичный HTTPS backend endpoint.

## Перед production release

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
