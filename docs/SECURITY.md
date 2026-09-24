# WB Insight — безопасность

## Совместимость шифрования токенов Wildberries

Новые WB-токены шифруются производным Fernet-ключом, зависящим от `API_TOKEN_ENCRYPTION_KEY` и идентификатора пользователя. Это изолирует ciphertext разных пользователей при одном мастер-ключе.

До 30 апреля 2026 года использовался прямой Fernet-ключ `API_TOKEN_ENCRYPTION_KEY`. Runtime сохраняет только обратную совместимость чтения: сначала пробуется текущая пользовательская схема, затем историческая. После успешной ручной проверки legacy-запись автоматически перешифровывается текущей схемой.

Legacy fallback не означает поддержку старого мастер-ключа после его ротации. Если ciphertext нельзя прочитать ни текущим пользовательским ключом, ни историческим форматом текущего мастер-ключа, секрет не восстанавливается: API возвращает безопасную ошибку и требует удалить подключение и добавить новый WB-токен.

## Основные принципы

WB Insight обрабатывает чувствительные данные продавца, поэтому security rules являются частью product contract, а не только deployment-настройкой.

## Сессия пользователя

- короткоживущий access token хранится только в памяти frontend;
- refresh session использует HttpOnly cookie;
- production cookie работает только по HTTPS;
- logout отзывает refresh session;
- CI проверяет, что access token не вернулся в persistent browser storage.

## Права доступа

Backend является source of truth для ролей, ownership и account scope. Frontend navigation guards используются только для интерфейса и не заменяют server-side authorization.

## Подключения marketplace

Данные доступа к кабинету проверяются до сохранения, хранятся в защищённом виде и после сохранения не возвращаются в browser. Детальный WB contract находится в `WB_ACCESS_TOKEN_REQUIREMENTS.md`.

## Секреты окружения

Production secrets задаются через deployment environment/secret store. Они не должны попадать в git, frontend bundle, screenshots, application logs или release evidence. Имена обязательных параметров приведены в `CONFIGURATION.md` и `.env.production.example`.

## Billing

Клиентский redirect не подтверждает оплату. Subscription активируется только после server-side проверки provider status. Idempotency защищает от повторной активации одной оплаты.

## Legal evidence

Backend проверяет точную версию принятого документа и сохраняет immutable evidence. Технические признаки сохраняются в privacy-minimized виде.

## CORS и gateway

Production использует same-origin nginx gateway. CORS настраивается точным allowlist HTTPS origins.

## Dependency security

Frontend CI выполняет production и full-tree `npm audit` с порогом high. Backend CI выполняет `pip-audit` production requirements. Найденные уязвимости должны быть исправлены или формально оценены до повышения release stage.

## База данных и backup

Schema управляется только Alembic. Backup scripts создают encrypted artifact и checksum; production-ready backup должен храниться вне основного host и проходить restore drill.

## Логирование

Логи не должны содержать session values, marketplace access data, банковские данные или содержимое запросов с чувствительными полями. Для диагностики используются безопасные identifiers и агрегированные operational signals.

## Проверка перед RC

До `1.0.0-rc.1` должны быть подтверждены dependency audits, HTTPS/cookie/CORS settings, tenant isolation, production secret handling, WB/Sber smoke, backup/restore drill и account lifecycle review.
