# WB Insight — release smoke

Документ фиксирует обязательные проверки перед переходами `alpha -> beta -> rc -> stable`.

## 1. CI smoke

На release PR автоматически проверяются backend/frontend dependency audits и test suites, frontend production build, Alembic clean upgrade/check, production images/Compose/gateway routing, encrypted PostgreSQL backup/restore, canonical version metadata, data-accuracy/evidence contracts и синтаксис release tooling.

CI не доказывает доступность Wildberries, эквайринга и почтового провайдера из production-like окружения и не заменяет сверку денежных показателей на реальном seller account.

## 2. Production-like core smoke

Канонический runner: `ops/release_smoke.py`. Общая логика жизненного цикла вынесена в `ops/release_smoke_core.py`, а entrypoint содержит актуальную release-policy. Runner запускается только против отдельного HTTPS environment и не должен печатать пароли, access/refresh tokens, marketplace credentials, mail verification/reset tokens или содержимое тестовых писем.

Базовый запуск:

```bash
export SMOKE_BASE_URL=https://staging.example.com
export SMOKE_EMAIL=release-admin@example.com
export SMOKE_PASSWORD='...'
python3 ops/release_smoke.py
```

`SMOKE_BASE_URL` — публичный HTTPS origin production-like окружения. Допустимо также передать `https://staging.example.com/api`; runner нормализует оба варианта и отправляет backend-запросы через публичный nginx prefix `/api` ровно один раз.

`SMOKE_EMAIL`/`SMOKE_PASSWORD` — заранее подготовленный smoke user. Для `SMOKE_AUDIT=true` этот пользователь должен иметь `AUDIT_READ` (`admin`/`super_admin`).

При записи `--evidence-output` runner работает fail-closed: evidence обязано содержать exact Git commit и environment. `--commit` по умолчанию берётся из `RELEASE_SHA` либо из текущего `git rev-parse HEAD`; environment передаётся через `--environment` или `ACCEPTANCE_ENVIRONMENT`.

Полный core smoke состоит из двух изолированных частей: disposable registration lifecycle и основной authenticated smoke. Проверяются health/readiness/version, legal registry, registration/legal evidence/demo, login/refresh/logout, dashboard contract, deactivation и невозможность использовать отозванную сессию.

Только public checks:

```bash
python3 ops/release_smoke.py --base-url https://staging.example.com --public-only
```

`--skip-disposable-registration` / `SMOKE_SKIP_DISPOSABLE_REGISTRATION=true` разрешён только для диагностики. Такой прогон не закрывает beta gate.

Для фактического P40 используется fail-closed режим `--beta-gate` или `SMOKE_BETA_GATE=true`. Он проверяет обязательные входы до первого сетевого запроса и требует:

- HTTPS production-like origin и `VERSION=*-beta.N`;
- structured `--evidence-output`;
- disposable registration без skip;
- реальное email verification и password reset;
- authenticated mail-gateway preflight;
- staff/admin credentials, provider-neutral inbox hook и доставляемый `{uuid}` address;
- durable audit smoke;
- реальный `SMOKE_WB_TOKEN`.

**Beta gate больше не требует RuSender или другого конкретного поставщика.** Готовность почты определяется реальным состоянием шлюза и capabilities выбранного адаптера.

## 3. Реальная email verification и password recovery

Beta smoke обязан доказать реальную доставку писем. Нельзя закрывать beta с `EMAIL_VERIFICATION_ENABLED=false`, `PASSWORD_RESET_ENABLED=false` или адресом `@smoke.invalid`.

WB Insight может использовать SMTP либо HTTPS API-провайдеры, зарегистрированные в почтовом слое. RuSender и Resend являются текущими HTTPS-адаптерами и работают через исходящий порт 443; SMTP остаётся отдельным транспортом. Release acceptance не делает название провайдера частью бизнес-контракта.

Для реального mail flow нужны:

```bash
export SMOKE_DISPOSABLE_EMAIL_TEMPLATE='release-smoke+{uuid}@qa.example.com'
export SMOKE_MAIL_TOKEN_COMMAND='python3 ops/imap_mail_token_hook.py'
export SMOKE_REQUIRE_EMAIL_VERIFICATION=true
export SMOKE_REQUIRE_PASSWORD_RESET=true
export SMOKE_MAIL_GATEWAY=true
```

`SMOKE_DISPOSABLE_EMAIL_TEMPLATE` обязан содержать `{uuid}` и формировать реально доставляемый уникальный адрес/catch-all mailbox.

`SMOKE_MAIL_TOKEN_COMMAND` запускается без shell. Runner передаёт ему два последних argv: `KIND EMAIL`; те же значения доступны как `WB_SMOKE_MAIL_KIND` и `WB_SMOKE_EMAIL`. `KIND` принимает `email_verification` или `password_reset`. Helper должен дождаться соответствующего письма и вывести в stdout ровно одно значение: raw token либо полный URL, где secret находится только во fragment `#token=...`.

Runner захватывает stdout/stderr helper-а и не печатает их при ошибке. URL с `?token=` отвергается. Таймаут регулируется `SMOKE_MAIL_TOKEN_TIMEOUT_SECONDS` — по умолчанию 180 секунд, максимум 1800.

В репозитории есть provider-neutral helper `ops/imap_mail_token_hook.py`. Credentials передаются только через environment:

```bash
export SMOKE_IMAP_HOST=imap.provider.example
export SMOKE_IMAP_PORT=993
export SMOKE_IMAP_USERNAME='release-mailbox@example.com'
export SMOKE_IMAP_PASSWORD='...'
export SMOKE_IMAP_MAILBOX=INBOX
export SMOKE_MAIL_TOKEN_COMMAND='python3 ops/imap_mail_token_hook.py'
```

### Mail gateway preflight

До создания disposable account runner открывает отдельную короткоживущую staff/admin сессию и вызывает `GET /control-panel/mail/gateway`.

Обязательно проверяются:

- `ready=true`;
- фактический provider присутствует;
- реестр `capabilities` присутствует;
- `transactional=true`;
- при `SMOKE_REQUIRE_EMAIL_VERIFICATION=true` готов verification-контур;
- при `SMOKE_REQUIRE_PASSWORD_RESET=true` готов recovery-контур.

Если необходимо дополнительно закрепить конкретную конфигурацию окружения, можно передать:

```bash
export SMOKE_EXPECTED_MAIL_PROVIDER=resend
```

Это **не обязательное требование beta gate**, а дополнительная точная проверка: observed provider должен совпасть с указанным. Допустимый код не ограничен списком `smtp/rusender/resend`; корректность и возможности реального адаптера подтверждаются ответом backend.

При `--evidence-output` сохраняется только безопасная mail metadata:

- фактический provider;
- необязательный expected provider;
- config source;
- `transport_kind`;
- признаки `transactional`, `marketing`, `one_click_unsubscribe`;
- readiness verification/recovery.

Host credentials, API token, Key ID, sender address и provider response body в evidence не попадают.

`ops/beta_release_evidence.py` проверяет именно этот provider-neutral контракт. Beta binder требует готовый transactional transport и фактически доказанные verification/password-reset, но не требует конкретного бренда почтового сервиса.

Beta disposable flow доказывает:

1. registration возвращает `email_verification_required=true`;
2. письмо реально доставлено на уникальный адрес;
3. `/auth/email-verification/confirm` подтверждает адрес;
4. login разрешается только после подтверждения;
5. session identity содержит `email_verified=true`;
6. demo активируется после ownership proof;
7. exact legal consent evidence сохранён;
8. password reset проходит через тот же эффективный transactional transport;
9. два немедленных recovery-запроса возвращают одинаковый anti-enumeration response, а staff-only PII-free diagnostic подтверждает одну durable `password_reset` mail row;
10. после reset ранее выданный access JWT получает `session_revoked`, а новый пароль восстанавливает ту же identity;
11. refresh lifecycle и soft-deactivation остаются корректными.

Для локальной проверки контракта без сети:

```bash
python3 ops/release_smoke.py --self-test
PYTHONPATH=ops python3 ops/acceptance/beta_subproof_selftest.py
```

Self-test отдельно закрепляет, что `resend` и `smtp` не отклоняются только из-за имени провайдера, а провайдер без `transactional` capability не проходит beta evidence.

## 4. Durable audit correlation smoke

P37 считается подтверждённым на production-like environment только после representative durable audit smoke:

```bash
export SMOKE_AUDIT=true
python3 ops/release_smoke.py
```

Runner отправляет security-sensitive Control Panel read с уникальным `X-Request-ID`, затем ищет событие через `/control-panel/audit/` и требует совпадение request id, успешный result и audit path. Raw secrets/PII в evidence не выводятся.

## 5. Wildberries integration smoke

В dedicated seller account runner использует отдельно переданный через environment `SMOKE_WB_TOKEN`; токен не следует передавать CLI-аргументом или сохранять в evidence. Проверяется актуальный marketplace legal requirement, live credential validation и обязательный storage/cleanup временного credential.

Для beta sanitized `core_smoke` должен содержать `wb_credential=true`. Отдельный live-WB/data provenance gate дополнительно связывает data-accuracy с конкретным seller account.

Для RC выполняется полный Celery sync заявленных доменов и отсутствие необъяснённых auth/permission/rate-limit ошибок; sanitized результат сохраняется как evidence kind `wb_full_sync`.

## 6. Data-accuracy acceptance

До beta выбираются фиксированные периоды реального seller account и сравниваются WB Insight, официальные WB-источники и, где применимо, исходная spreadsheet-модель.

Канонический runner: `ops/data_accuracy_acceptance.py`; policy: `ops/acceptance/wb_v1_metric_policy.json`. Все policy-required метрики должны присутствовать в каждом периоде, `missing=0`, а tolerance override требует `override_reason`. Необъяснённое существенное денежное расхождение блокирует повышение release stage.

Green JSON сохраняется как evidence kind `data_accuracy`.

## 7. Эквайринг

Для sandbox/согласованного production test:

```bash
export SMOKE_BILLING_TARIFF=pro
python3 ops/release_smoke.py
```

Проверяются payment attempt, provider page, server-side confirmation, paid subscription activation, idempotency/duplicate callback, decline/cancel/retry и merchant back-office reconciliation. Test/live события должны оставаться различимыми в payment journal.

Для RC sanitized proof сохраняется как evidence kind `sber_payment`.

## 8. Operations smoke

Перед beta/RC по соответствующему gate подтверждаются deployment/rollback, active backend/Celery/Beat, `/health/ready`, secrets review, desktop/mobile UX, role-aware staff workspace, реальная transactional mail delivery, durable audit, backup/restore. Перед RC дополнительно подключаются внешний uptime monitor, alert destination, centralized logs, off-host encrypted backup и измеренный restore drill/RPO/RTO.

## WB Web v1 checklist

- [ ] HTTPS production-like deployment на exact candidate commit;
- [ ] real email verification + demo activation;
- [ ] real password reset;
- [ ] legal consent evidence;
- [ ] login/refresh/logout/deactivation;
- [ ] durable audit correlation;
- [ ] role-aware staff workspace для super_admin/admin/manager/support/analyst;
- [ ] Control Panel overview/users/user-detail/roles/tariffs/payments/audit/mail desktop/mobile;
- [ ] user-detail inactive/unverified/staff states;
- [ ] готовый transactional mail gateway и реальная тестовая доставка независимо от бренда провайдера;
- [ ] real WB seller connection + full sync;
- [ ] data-accuracy acceptance;
- [ ] Overview / Unit Economy / Finance / Inventory / Prices / Ads;
- [ ] COGS/manual expenses/revenue plan;
- [ ] acquiring success/decline/cancel/retry/idempotency;
- [ ] monitoring/alerts/logging;
- [ ] off-host backup + restore drill;
- [ ] deploy/rollback evidence;
- [ ] non-draft legal documents before RC.

## Release evidence

После фактического прогона evidence связывается с exact commit/version через `ops/release_evidence.py`; contract описан в `RELEASE_EVIDENCE.md`.

Для beta manifest v2 обязательны `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`. Real email verification/password reset и audit smoke входят в sanitized `core_smoke`/`account_lifecycle` evidence.

Release evidence не должно содержать passwords, session values, mail tokens, marketplace credentials, merchant credentials или raw customer PII.
