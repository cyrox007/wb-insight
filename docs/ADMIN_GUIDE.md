# WB Insight — руководство администратора

## Роли

Control Panel доступен только административным ролям. Backend обязан проверять роль независимо от frontend navigation guard.

Основные роли текущего baseline:

- обычный пользователь — свои кабинеты, аналитика, настройки и billing;
- `admin` — административные функции;
- `super_admin` — расширенные системные функции, включая operations health.

## Control Panel

Маршрут: `/control-panel`.

Основные разделы:

- пользователи;
- редактирование пользователя;
- тарифы;
- редактирование тарифа.

## Пользователи

Администратор должен использовать UI/API, а не прямое изменение строк БД. При изменении пользователя необходимо сохранять системные инварианты ролей и не раскрывать marketplace secrets.

Перед блокировкой/изменением доступа учитывайте активную подписку и связанные кабинеты.

## Тарифы

Тариф задаёт коммерческие ограничения продукта, включая допустимое число WB-кабинетов. Изменения тарифа должны проверяться на существующих подписках и не должны молча нарушать backend limits.

## Operations health

Super-admin endpoint агрегирует operational состояние без выдачи seller secrets/PII. Проверяются, в частности:

- recent failed sync jobs;
- processing jobs с истёкшим lease;
- stale sync states;
- срок действия marketplace credentials;
- срок ротации WB service secret;
- HTTP request/5xx telemetry.

Подробно: `OPERATIONS.md`.

## Работа с обращением пользователя

Запрашивайте минимально необходимую информацию:

- user/account identifier;
- marketplace account identifier;
- период;
- экран/операция;
- timestamp;
- текст безопасной ошибки.

Не просите отправлять пароль, access/refresh session, WB secret или merchant credentials.

## Платежи

Если пользователь сообщает об оплате без активированной подписки:

1. найти внутренний payment attempt;
2. проверить server-side provider status;
3. проверить PaymentEvent/idempotency;
4. проверить, существует ли subscription, связанная с payment;
5. не активировать тариф только на основании screenshot/redirect клиента.

Ручное исправление допустимо только по утверждённой support procedure с audit trail.

## Синхронизация

При проблеме sync различайте:

- invalid/expired credential;
- недостаточные permissions;
- WB 429/rate limit;
- временный внешний 5xx/network error;
- stale/crashed job;
- отсутствие данных в источнике.

Не деактивируйте credential из-за любого внешнего 4xx/5xx без классификации.

## Безопасность административных действий

- используйте отдельные admin accounts;
- не делитесь session между сотрудниками;
- ограничивайте доступ к production;
- административные изменения, влияющие на оплату/доступ, должны иметь audit trail;
- операции с backups/secrets выполняются вне Control Panel по operations runbook.

## Что ещё требуется до stable

Account lifecycle пока требует дополнительного hardening: password reset/recovery, cancellation/refund procedure, account deletion/retention и support flows. Текущий статус — `ACCOUNT_LIFECYCLE.md` и `RELEASE_ROADMAP.md`.
