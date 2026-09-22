# WB Insight — конфигурация

Этот документ описывает группы переменных окружения. Реальные секреты не должны храниться в git. Production template: `/.env.production.example`.

## Общие параметры приложения

- `APP_ENV` — `development` или `production`.
- `DEBUG` — debug mode; в production должен быть `false`.
- `SERVER_HTTP_PROTOCOL`, `SERVER_ADDR`, `SERVER_PORT` — публичный адрес приложения/сервера.
- `ALLOWED_ORIGINS` — точный CORS allowlist frontend origins.

## PostgreSQL

Основные переменные:

- `DB_HOST`;
- `DB_PORT`;
- `DB_NAME`;
- `DB_USER`;
- `DB_PASSWORD`.

В production `compose.production.yml` переопределяет `DB_HOST=postgres` для container topology. При использовании managed PostgreSQL укажите реальный host и скорректируйте deployment topology.

## Redis

- `REDIS_URL`, пример: `redis://localhost:6379/0`.

Redis используется Celery и внутренними coordination/telemetry механизмами. `/health/ready` требует доступность Redis.

## Session / JWT

- `JWT_SECRET_KEY` — сильный случайный secret, обязателен в production;
- `ACCESS_TOKEN_EXPIRE_MINUTES` — TTL короткоживущего access JWT;
- `REFRESH_TOKEN_EXPIRE_DAYS` — TTL refresh session;
- `REFRESH_COOKIE_NAME` — имя HttpOnly cookie;
- `COOKIE_SECURE` — `true` в production;
- `COOKIE_SAMESITE` — обычно `lax` для same-origin flow;
- `COOKIE_DOMAIN` — задаётся только если нужен общий cookie domain.

Access JWT хранится frontend-ом только в памяти. После reload сессия восстанавливается через HttpOnly refresh cookie.

## Encryption / legal evidence

- `API_TOKEN_ENCRYPTION_KEY` — Fernet-compatible key для marketplace credentials;
- `LEGAL_EVIDENCE_HMAC_KEY` — отдельный random key для HMAC evidence legal consent. Production должен использовать независимый key; fallback к JWT secret существует как совместимость, но не является рекомендуемой production настройкой.

## Wildberries partner service

Production требует:

- `WB_SERVICE_ID`;
- `WB_SERVICE_SECRET`.

Дополнительно:

- `OPS_WB_SERVICE_SECRET_EXPIRES_AT` — timezone-aware дата ротации/истечения для alerts;
- `OPS_WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS` — окно предупреждения.

Seller credentials проходят отдельную validation policy. См. [`WB_ACCESS_TOKEN_REQUIREMENTS.md`](WB_ACCESS_TOKEN_REQUIREMENTS.md).

## WB rate limits / sync tuning

В `.env.production.example` зафиксированы интервалы и retry-настройки для Finance, Stocks, Content Cards, Prices, Operational data, Advertising, Funnel и Paid Storage.

Ключевые группы:

- `WB_*_MIN_INTERVAL_SECONDS` — минимальные интервалы запросов;
- `WB_*_LOOKBACK_DAYS` — rolling refresh depth;
- `WB_*_BATCH_SIZE` — batch limits;
- `WB_API_MAX_ATTEMPTS`, `WB_API_BACKOFF_BASE_SECONDS`, `WB_API_MAX_BACKOFF_SECONDS` — retry/backoff.

Не уменьшайте интервалы «для ускорения» без сверки с официальными лимитами WB. 429 должен обрабатываться transport layer, а не массовым параллелизмом worker-ов.

## Durable sync jobs

- `SYNC_JOB_LEASE_SECONDS` — lease processing job;
- `SYNC_JOB_MAX_ATTEMPTS` — bounded retry budget;
- `SYNC_JOB_RETRY_BASE_SECONDS`;
- `SYNC_JOB_RETRY_MAX_SECONDS`.

Значения должны быть согласованы с максимальной длительностью реального sync. Слишком короткий lease создаёт ложный recovery, слишком длинный замедляет восстановление после crash.

## Billing

- `ALLOW_FAKE_BILLING` — только development;
- `SBER_ACQUIRING_ENABLED` — включает реальный provider;
- `SBER_API_BASE_URL`;
- `SBER_USERNAME`;
- `SBER_PASSWORD`;
- `SBER_RETURN_URL`;
- `SBER_FAIL_URL`;
- `SBER_CURRENCY_CODE`;
- `SBER_HTTP_TIMEOUT_SECONDS`.

Production activation запрещена до merchant onboarding и smoke. Подробно: [`SBER_ACQUIRING.md`](SBER_ACQUIRING.md).

## Восстановление доступа

Password recovery включается отдельно от маркетинговой почты:

- `PASSWORD_RESET_ENABLED=true` — включает публичный recovery flow;
- `PASSWORD_RESET_BASE_URL` — HTTPS-страница `/reset-password`;
- `PASSWORD_RESET_TOKEN_TTL_MINUTES` — срок жизни одноразовой ссылки;
- `PASSWORD_RESET_RESEND_SECONDS` — минимальный интервал между письмами восстановления для одного аккаунта.

Endpoint не раскрывает существование аккаунта: одинаковый успешный ответ возвращается для неизвестного, неактивного, неподтверждённого и throttled адреса. Одноразовый token создаётся только worker-ом непосредственно перед отправкой письма, в БД хранится только SHA-256 digest, а после смены пароля `session_version` отзывают ранее выданные сессии.

## Почтовый транспорт

WB Insight поддерживает два транспорта:

- `smtp` — универсальный SMTP-адаптер; может использоваться для транзакционной почты и маркетинговых кампаний;
- `rusender` — нативный RuSender HTTPS API для транзакционных писем (email verification, password recovery, системные уведомления и gateway test).

Общие параметры:

- `MAIL_CONFIG_SOURCE` — `auto`, `environment` или `database`;
- при `auto` encrypted DB config имеет приоритет. ENV становится fallback только если в БД нет provider row; incomplete/example fallback в production считается недоступным на runtime, но не мешает приложению стартовать и настроить реальный provider из Control Panel;
- `environment` остаётся fail-closed на startup: включённая auth-mail capability требует полностью валидный ENV transport;
- `MAIL_PROVIDER` — `smtp` или `rusender` для ENV-конфигурации;
- `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` — sender identity, используются обоими адаптерами;
- `MAIL_DELIVERY_ENABLED` — разрешает маркетинговые кампании. Для текущего RuSender transactional adapter должен оставаться `false`.

RuSender ENV:

- `RUSENDER_API_BASE_URL=https://api.rusender.ru`;
- `RUSENDER_KEY_ID` — числовой ID активированного ключа отправки;
- `RUSENDER_API_TOKEN` — bearer token с permission `external_mail.send`;
- `RUSENDER_TIMEOUT_SECONDS`.

При `MAIL_CONFIG_SOURCE=auto` или `database` RuSender можно настроить из Control Panel. API token хранится только в encrypted secrets и после сохранения не возвращается frontend-у. Вместо секрета UI показывает короткий SHA-256 fingerprint эффективного token-а, чтобы безопасно отличать старый сохранённый credential от нового рабочего token-а при диагностике. Экран шлюза отдельно показывает готовность transport, email verification и password recovery, поэтому наличие рабочего provider не маскирует выключенный feature flag или отсутствующий HTTPS base URL. DB-managed endpoint намеренно закреплён на `https://api.rusender.ru`, чтобы bearer token нельзя было перенаправить на сторонний host.

RuSender transport передаёт `idempotencyKey` и сохраняет возвращаемый `uuid` как `provider_message_id`. При HTTP-ошибке adapter извлекает только bounded machine-readable provider code из JSON-ответа; raw description/body не сохраняются и не возвращаются. Gateway test показывает этот безопасный код администратору для диагностики. Маркетинговые кампании пока не используют transactional endpoint RuSender: текущий контракт custom headers допускает только `X-*`, поэтому приложение не заявляет через него RFC 8058 one-click unsubscribe.

## Operations monitoring

- `OPS_SYNC_STALE_MINUTES`;
- `OPS_FAILED_JOB_LOOKBACK_MINUTES`;
- `OPS_CREDENTIAL_EXPIRY_WARNING_DAYS`;
- `OPS_HTTP_METRICS_ENABLED`;
- `OPS_HTTP_ERROR_WINDOW_MINUTES`;
- `OPS_HTTP_5XX_RATE_THRESHOLD`;
- `OPS_HTTP_MIN_REQUESTS`;
- `OPS_ALERT_CHECK_INTERVAL_SECONDS`;
- `OPS_ALERT_REPEAT_SECONDS`;
- `OPS_ALERT_WEBHOOK_URL` — optional HTTPS endpoint;
- `OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS`.

Подробно: [`OPERATIONS.md`](OPERATIONS.md).

## Backup

Backup scripts читают:

- `BACKUP_DIR`;
- `BACKUP_RETENTION_DAYS`;
- `BACKUP_ENCRYPTION_PASSPHRASE_FILE`.

Passphrase file должен находиться вне repository и вне backup directory. Backup считается production-ready только при off-host копии и успешном restore drill.

## Frontend

Development:

- `VITE_API_BASE_URL` — backend URL, например `http://localhost:9000`.

Production default — same-origin. Не встраивайте secrets в `VITE_*`: frontend environment попадает в browser bundle.

## Docker Compose

- `PUBLIC_HTTP_PORT` — host port frontend/nginx; default `8080`.

Compose использует `.env.production` для build/runtime orchestration. Секреты предпочтительно инжектировать через platform secret store; template в репозитории служит контрактом имён, а не способом хранения production values.

## Production fail-closed правила

Production должен отказываться запускаться или предоставлять критичную capability при отсутствии обязательной безопасной конфигурации. В частности:

- нет слабого fallback для JWT/encryption key;
- WB cloud integration не должна работать без partner service credentials;
- fake billing выключен;
- cookie secure;
- legal consent evidence имеет production secret;
- CORS не должен быть wildcard для authenticated browser flow.
