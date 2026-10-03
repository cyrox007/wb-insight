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

Восстановление пароля включается отдельно от маркетинговой почты:

- `PASSWORD_RESET_ENABLED=true` — включает публичный сценарий восстановления;
- `PASSWORD_RESET_BASE_URL` — HTTPS-страница `/reset-password`;
- `PASSWORD_RESET_TOKEN_TTL_MINUTES` — срок жизни одноразовой ссылки;
- `PASSWORD_RESET_RESEND_SECONDS` — минимальный интервал между письмами восстановления для одного аккаунта.

Endpoint не раскрывает существование аккаунта: одинаковый успешный ответ возвращается для неизвестного, неактивного, неподтверждённого и ограниченного по частоте адреса. Одноразовый token создаётся только worker-ом непосредственно перед отправкой письма, в БД хранится только SHA-256 digest, а после смены пароля `session_version` отзывает ранее выданные сессии.

## Почтовый транспорт

Почтовая подсистема построена вокруг общего контракта адаптера. Бизнес-логика регистрации, восстановления доступа, системных уведомлений и кампаний не проверяет имя конкретного провайдера, а использует заявленные возможности транспорта: транзакционную отправку, кампании, RFC-заголовки, one-click unsubscribe, Reply-To, preview и идемпотентность.

Сейчас зарегистрированы три адаптера:

- `smtp` — классический SMTP-транспорт; поддерживает транзакционную почту, кампании и RFC-заголовки;
- `rusender` — HTTPS API на исходящем порту `443`; используется для транзакционных писем и не зависит от доступности SMTP-портов хостера;
- `resend` — второй независимый HTTPS API на исходящем порту `443`; поддерживает транзакционные письма, Reply-To, RFC-заголовки и маркетинговые кампании.

Подробный capability-контракт и правила добавления новых адаптеров описаны в [`MAIL_PROVIDERS.md`](MAIL_PROVIDERS.md).

Общие параметры:

- `MAIL_CONFIG_SOURCE` — `auto`, `environment` или `database`;
- при `auto` зашифрованная конфигурация из БД имеет приоритет, а ENV используется только как резервный источник, если в БД ещё нет провайдера;
- `environment` остаётся fail-closed на старте: включённая почтовая функция требует полностью валидный ENV-транспорт;
- `MAIL_PROVIDER` — `smtp`, `rusender` или `resend` для ENV-конфигурации;
- `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` — общая идентичность отправителя для всех адаптеров;
- `SMTP_REPLY_TO_EMAIL` используется только адаптерами, объявляющими поддержку Reply-To;
- `MAIL_DELIVERY_ENABLED` разрешает маркетинговые кампании только если выбранный адаптер объявляет `marketing=true` и настроена безопасная отписка.

### SMTP

Основные параметры:

- `SMTP_HOST`;
- `SMTP_PORT`;
- `SMTP_USERNAME` и `SMTP_PASSWORD` — указываются только вместе;
- `SMTP_STARTTLS=true` — обязательно в production;
- `SMTP_TIMEOUT_SECONDS`.

SMTP требует доступности исходящего почтового порта у хостера. Если `25`, `465` или `587` заблокированы, используйте HTTPS API-адаптер.

### RuSender

ENV-параметры:

- `RUSENDER_API_BASE_URL=https://api.rusender.ru`;
- `RUSENDER_KEY_ID` — числовой ID активированного ключа отправки;
- `RUSENDER_API_TOKEN` — bearer token с permission `external_mail.send`;
- `RUSENDER_TIMEOUT_SECONDS`.

Текущий transactional endpoint RuSender передаёт sender/recipient identity, subject, plain-text + HTML body, `previewTitle`, `idempotencyKey` и безопасные custom `X-*` headers. Возвращаемый `uuid` сохраняется как `provider_message_id`, когда провайдер его прислал. Любой подтверждённый HTTP `2xx` считается принятым.

RuSender в текущем адаптере не объявляет поддержку используемых WB Insight RFC 8058 заголовков маркетинговой рассылки, поэтому `marketing=false`.

### Resend

ENV-параметры:

- `RESEND_API_BASE_URL=https://api.resend.com`;
- `RESEND_API_TOKEN` — API-токен провайдера;
- `RESEND_TIMEOUT_SECONDS`.

Resend работает через HTTPS `443`, не требует отдельного ID ключа и поддерживает `Reply-To`, пользовательские/RFC-заголовки и `Idempotency-Key`. Поэтому его можно использовать как для подтверждения email и восстановления доступа, так и для кампаний без открытия SMTP-портов.

Перед production-отправкой отправляющий домен должен быть подтверждён у провайдера. API-токен хранится только в зашифрованных secrets и не возвращается frontend-у; Control Panel получает только короткий SHA-256 fingerprint.

Для маркетинговых кампаний дополнительно необходимы:

- `MAIL_DELIVERY_ENABLED=true`;
- `MAIL_UNSUBSCRIBE_BASE_URL`;
- стойкий независимый `MAIL_UNSUBSCRIBE_HMAC_KEY` длиной не менее 32 символов.

Для verification/password-reset provider idempotency key привязан к **attempt**, а не только к durable `MailMessage`: одноразовый token создаётся внутри транзакции непосредственно перед отправкой и откатывается при неопределённой transport-ошибке. Новый attempt получает новый token и новый provider key, поэтому провайдер не может дедуплицировать retry к уже недействительной первой ссылке. Durable queue idempotency при этом продолжает защищать от повторного создания одной и той же операции.

Маркетинговые кампании запускаются только через адаптер, который объявляет поддержку `marketing` и RFC 8058. SMTP и Resend эти возможности поддерживают; текущий transactional endpoint RuSender — нет. Приложение добавляет `List-Unsubscribe`, `List-Unsubscribe-Post`, `List-ID`, `Precedence: bulk` и видимую ссылку отписки. Verification/recovery остаются транзакционными и не получают bulk/unsubscribe metadata.

### Диагностика попадания в спам

Успешный HTTP-ответ API или успешная передача SMTP доказывают только приём письма транспортом. Inbox placement зависит также от доменной аутентификации и репутации. Для полученного письма проверяйте:

- SPF = `PASS`;
- DKIM = `PASS`, подпись относится к ожидаемому отправляющему домену/провайдеру;
- DMARC = `PASS`, домен `From:` выровнен с SPF или DKIM identity;
- TLS и корректные forward/reverse DNS/PTR на стороне транспортного провайдера;
- низкую долю жалоб/отказов и отправку тестов только на существующие адреса.

Произвольные дополнительные `X-*` headers не исправляют SPF/DKIM/DMARC или репутацию отправителя. Если проверки проходят, а письмо всё равно попадает в spam, следующим этапом являются диагностика репутации/прогрева/содержимого у выбранного почтового провайдера и postmaster-инструменты принимающей почты.

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