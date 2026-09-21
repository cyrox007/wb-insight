# WB Insight — release smoke

Документ фиксирует обязательные проверки перед переходами `alpha -> beta -> rc -> stable`.

## 1. CI smoke

На release PR автоматически проверяются backend/frontend dependency audits и test suites, frontend production build, Alembic clean upgrade/check, production images/Compose/gateway routing, encrypted PostgreSQL backup/restore, canonical version metadata, data-accuracy/evidence contracts и синтаксис release tooling.

CI не доказывает доступность Wildberries/эквайринга/mail provider из production-like environment и не заменяет сверку денежных показателей на реальном seller account.

## 2. Production-like core smoke

Канонический runner: `ops/release_smoke.py`. Он запускается только против отдельного HTTPS environment и не должен печатать passwords, access/refresh tokens, marketplace credentials, mail verification/reset tokens или содержимое тестовых писем.

Базовый запуск:

```bash
export SMOKE_BASE_URL=https://staging.example.com
export SMOKE_EMAIL=release-admin@example.com
export SMOKE_PASSWORD='...'
python3 ops/release_smoke.py
```

`SMOKE_BASE_URL` — публичный HTTPS origin production-like окружения. Допустимо также передать `https://staging.example.com/api`; runner нормализует оба варианта и отправляет backend-запросы через публичный nginx prefix `/api` ровно один раз. Произвольные path в `SMOKE_BASE_URL` отвергаются, а sanitized evidence по-прежнему привязывается к чистому HTTPS origin без `/api`.

`SMOKE_EMAIL`/`SMOKE_PASSWORD` — заранее подготовленный smoke user. Для `SMOKE_AUDIT=true` этот пользователь должен иметь `AUDIT_READ` (`admin`/`super_admin`).

При записи `--evidence-output` runner работает fail-closed: evidence обязано содержать exact Git commit и environment. `--commit` по умолчанию берётся из `RELEASE_SHA` либо из текущего `git rev-parse HEAD`; environment передаётся через `--environment` или `ACCEPTANCE_ENVIRONMENT`. Поэтому sanitized `core_smoke`/`account_lifecycle` нельзя переиспользовать для другого candidate commit с той же версией.

Полный core smoke состоит из двух изолированных частей: disposable registration lifecycle и основной authenticated smoke. Проверяются health/readiness/version, legal registry, registration/legal evidence/demo, login/refresh/logout, dashboard contract, deactivation и невозможность использовать отозванную сессию.

Только public checks:

```bash
python3 ops/release_smoke.py --base-url https://staging.example.com --public-only
```

`--skip-disposable-registration` / `SMOKE_SKIP_DISPOSABLE_REGISTRATION=true` разрешён только для диагностики. Такой прогон не закрывает beta gate.

## 3. P40: реальная email verification и password recovery через RuSender

После P38/P39/P42/P43 beta smoke обязан доказать реальную доставку писем. Нельзя закрывать beta с `EMAIL_VERIFICATION_ENABLED=false` или адресом `@smoke.invalid`. Текущий production-like transactional transport — RuSender HTTPS API, поэтому SMTP-порты хостинга не участвуют в этом acceptance.

Runner поддерживает provider-neutral inbox hook. Нужны:

```bash
export SMOKE_DISPOSABLE_EMAIL_TEMPLATE='release-smoke+{uuid}@qa.example.com'
export SMOKE_MAIL_TOKEN_COMMAND='/opt/wb-smoke/read-mail-token'
export SMOKE_REQUIRE_EMAIL_VERIFICATION=true
export SMOKE_REQUIRE_PASSWORD_RESET=true
```

`SMOKE_DISPOSABLE_EMAIL_TEMPLATE` обязан содержать `{uuid}` и формировать реально доставляемый уникальный адрес/catch-all mailbox.

`SMOKE_MAIL_TOKEN_COMMAND` запускается **без shell**. Runner передаёт ему два последних argv: `KIND EMAIL`; те же значения доступны как `WB_SMOKE_MAIL_KIND` и `WB_SMOKE_EMAIL`. `KIND` сейчас принимает `email_verification` или `password_reset`. Helper должен дождаться соответствующего письма и вывести в stdout ровно одно значение: raw token либо полный URL, где secret находится только во fragment `#token=...`.

Runner захватывает stdout/stderr helper-а и никогда не печатает их при ошибке. URL с `?token=` отвергается. Таймаут регулируется `SMOKE_MAIL_TOKEN_TIMEOUT_SECONDS` (по умолчанию 180 секунд, максимум 1800).

Beta disposable flow доказывает:

1. registration возвращает `email_verification_required=true`;
2. письмо реально доставлено на уникальный адрес;
3. `/auth/email-verification/confirm` подтверждает адрес;
4. login разрешается только после подтверждения;
5. session identity содержит `email_verified=true`;
6. demo активируется после ownership proof;
7. exact legal consent evidence сохранён;
8. password reset проходит через тот же реальный RuSender transport;
9. повторные recovery-запросы не создают неконтролируемый поток писем, а idempotency/throttle сохраняют anti-enumeration contract;
10. новый пароль работает, старые sessions отозваны;
11. refresh lifecycle и soft-deactivation остаются корректными.

Для локального smoke контракта без сети:

```bash
python3 ops/release_smoke.py --self-test
```

## 4. Durable audit correlation smoke

P37 считается подтверждённым на production-like environment только после representative durable audit smoke:

```bash
export SMOKE_AUDIT=true
python3 ops/release_smoke.py
```

Runner отправляет security-sensitive Control Panel read с уникальным `X-Request-ID`, затем ищет событие через `/control-panel/audit/` и требует совпадение request id, успешный result и audit path. Raw secrets/PII в evidence не выводятся.

## 5. Wildberries integration smoke

В dedicated seller account runner использует отдельно переданный через environment `SMOKE_WB_TOKEN`; токен не следует передавать CLI-аргументом или сохранять в evidence. Проверяется актуальный marketplace legal requirement, live credential validation и обязательный storage/cleanup временного credential.

Для **P40 beta** strict candidate gate требует, чтобы sanitized `core_smoke` содержал `wb_credential=true`, поэтому production-like core smoke запускается с реальным `SMOKE_WB_TOKEN`. Отдельный live-WB/data provenance gate дополнительно связывает data-accuracy с конкретным seller account.

Для RC выполняется уже полный Celery sync заявленных доменов и отсутствие необъяснённых auth/permission/rate-limit ошибок; sanitized результат сохраняется как evidence kind `wb_full_sync`.

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

Перед beta/RC по соответствующему gate подтверждаются deployment/rollback, active backend/Celery/Beat, `/health/ready`, secrets review, desktop/mobile UX, role-aware staff workspace, RuSender mail delivery, durable audit, backup/restore. Перед RC дополнительно подключаются внешний uptime monitor, alert destination, centralized logs, off-host encrypted backup и измеренный restore drill/RPO/RTO.

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
- [ ] RuSender gateway state и тестовая transactional доставка;
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

Для beta manifest v2 обязательны `ci`, `deployment`, `core_smoke`, `account_lifecycle`, `ux_smoke`, `secrets_review`, `data_accuracy`. Real email verification/password reset и P37 audit smoke входят в sanitized `core_smoke`/`account_lifecycle` evidence, а не создают обход существующего manifest contract.

Release evidence не должно содержать passwords, session values, mail tokens, marketplace credentials, merchant credentials или raw customer PII.
