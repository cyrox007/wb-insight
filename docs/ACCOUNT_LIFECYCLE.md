# WB Insight — жизненный цикл аккаунта

Дата ревизии: 15 сентября 2026 года.

Документ описывает технический baseline P31. Он не заменяет утверждённую юридическую policy по retention/refund и не означает, что внешний SMTP/Sber production flow уже проверен.

## 1. Сессии и немедленный отзыв доступа

У пользователя есть `session_version`. Она включается в access/refresh JWT как claim `sv` и сверяется backend с текущим состоянием БД.

Версия увеличивается при:

- успешной смене пароля;
- административном отзыве всех сессий;
- деактивации аккаунта;
- повторной активации аккаунта.

Поэтому уже выданный JWT перестаёт работать сразу после security-события, даже если его `exp` ещё не наступил. Refresh дополнительно требует активного пользователя и совпадения `session_version`.

## 2. Восстановление пароля

API:

- `POST /auth/password-reset/request`;
- `POST /auth/password-reset/confirm`.

Правила:

- request всегда возвращает одинаковый публичный ответ и не раскрывает существование email;
- token генерируется через криптографически случайный opaque secret;
- в БД хранится только SHA-256 digest, исходный token не сохраняется;
- новый request инвалидирует предыдущие неиспользованные token пользователя;
- token одноразовый и ограничен TTL;
- при ошибке SMTP созданный, но недоставленный token откатывается;
- успешный reset меняет bcrypt password, инвалидирует остальные reset-token и увеличивает `session_version`;
- деактивация аккаунта также инвалидирует ранее выданные reset-ссылки.

Password recovery по умолчанию выключен. Перед production-включением нужны HTTPS `PASSWORD_RESET_BASE_URL`, реальный SMTP/provider и smoke доставки.

## 3. Отмена платной подписки

API:

- `POST /account/subscription/cancel` — отключить продление;
- `DELETE /account/subscription/cancel` — отозвать отмену.

Отмена применяется только к действующей платной подписке со статусом `active`. Demo-период не трактуется как платное автопродление.

При отмене:

- текущий оплаченный период не обрывается;
- сохраняются `cancel_at_period_end`, время и причина запроса;
- действие фиксируется в lifecycle audit trail.

Фактический refund/ошибочный платёж не выполняется этим endpoint. До появления отдельного provider refund API он обрабатывается по утверждённой Sber/support policy с обязательной audit-записью.

## 4. Деактивация аккаунта

Пользователь может выполнить soft-deactivation через `/account/deactivate`. В интерфейсе действие вынесено в «Безопасность аккаунта» и требует явного подтверждения.

При деактивации:

- `is_active=false` немедленно закрывает вход;
- `session_version` отзывается;
- marketplace credentials становятся inactive/revoked;
- неиспользованные password-reset tokens инвалидируются;
- для текущего доступа отключается дальнейшее продление;
- записываются `deactivated_at`, причина и `retention_until`;
- создаётся append-only lifecycle event.

Это **не hard delete**. Значение `ACCOUNT_DEACTIVATION_RETENTION_DAYS=90` — технический default до утверждения финальной legal/retention policy. Автоматический необратимый purge P31 намеренно не выполняет.

## 5. Повторная активация

Администратор может re-activate пользователя через control panel. При этом:

- аккаунт снова становится active;
- deactivation metadata очищается;
- `session_version` снова увеличивается;
- ранее отозванные marketplace credentials автоматически не восстанавливаются;
- старые password-reset links не оживают;
- действие фиксируется audit trail.

Пользователь после reactivation входит заново и при необходимости повторно подключает WB.

## 6. Поздний callback оплаты после деактивации

Факт оплаты определяется серверной проверкой Sber. Если банк подтвердил `DEPOSITED` уже после деактивации аккаунта:

- payment сохраняется как `succeeded`, потому что это финансовый факт;
- новая subscription для inactive account автоматически **не создаётся**;
- создаётся `subscription_activation_skipped` payment event;
- support выполняет reconciliation/refund по утверждённой процедуре.

Так account lifecycle не может «воскресить» доступ через запоздавший callback.

## 7. Admin/support procedure

Все `/control-panel/users/*` lifecycle routes имеют явную admin dependency поверх общего control-panel permission middleware.

Администратор может:

- soft-deactivate пользователя;
- re-activate пользователя;
- отозвать все sessions;
- прочитать lifecycle events;
- добавить только allowlisted support event.

Allowlist support events:

- `support_access_review`;
- `support_payment_review`;
- `support_refund_requested`;
- `support_refund_completed`.

Support event требует причины, допускает bounded `reference_id` и сохраняет actor. Этот endpoint не даёт произвольно изменять платежи/балансы/подписки; его задача — заменить ручное редактирование production DB проверяемым append-only следом.

## 8. Audit и данные

`account_lifecycle_events` — append-only технический журнал account/security/support событий. HTTP AuditMiddleware также фиксирует mutating lifecycle/control-panel routes без request body, паролей и токенов.

Raw password-reset token, пароль, WB credential и SMTP password не должны попадать в event data или логи.

## 9. Что остаётся внешним до RC

Code-side baseline P31 не закрывает внешние доказательства:

- реальный SMTP/provider и recovery delivery smoke;
- утверждённый retention срок и процедура окончательного удаления;
- утверждённая refund/cancellation policy;
- реальный Sber refund/reconciliation procedure;
- production-like end-to-end lifecycle smoke и сохранённое release evidence.

Эти пункты остаются release gates в `RELEASE_READINESS.md` и `RELEASE_ROADMAP.md`.
