# WB Insight — дорожная карта до стабильного релиза

Дата фиксации: 15 сентября 2026 года.

Цель: первый публичный стабильный релиз **WB Insight Web v1 / `1.0.0` для продавцов Wildberries**.

В scope `1.0.0`: регистрация и сессия, роли/admin, тарифы/demo/limits, подключение WB-кабинетов, автоматическая синхронизация, KPI/финансы/остатки/цены/реклама/unit-экономика, себестоимость, ручные расходы, план выручки, Сбер acquiring, production deployment, monitoring, backup/restore и versioned legal consent.

Не блокируют `1.0.0`: Ozon, AI-аналитик, native mobile и WB OAuth 2.0 onboarding после Catalog readiness.

## Текущее состояние

- `main`: `0.9.0-alpha.5`, P28 слит.
- P22–P28 закрыли основной code baseline: WB credential contract, marketplace foundation, Sber acquiring code, deployment, monitoring/backup baseline, legal-consent foundation, browser-session hardening и release-smoke runner.
- P29 готовится как `0.9.0-alpha.6`: dependency/security hardening перед beta.
- Переход стадии определяется release gates, а не номером P-задачи или количеством коммитов.

## Этап A — завершить P29 / `0.9.0-alpha.6`

Цель: убрать известные dependency/security blockers и получить чистый последний alpha baseline.

Обязательно:

- production frontend dependency audit без High/Critical;
- полный frontend dependency audit без High/Critical;
- backend dependency audit (`pip-audit` или эквивалент) без необработанных High/Critical;
- удалить временные self-write workflow/permissions, использованные только для регенерации lockfile;
- синхронизировать `VERSION`, frontend package metadata, CHANGELOG, VERSION_HISTORY и RELEASE_READINESS;
- backend tests, frontend build, Alembic, Docker/Compose, gateway smoke, backup/restore CI — green на одном финальном head;
- merge P29 только после green CI.

Выход этапа: `main = 0.9.0-alpha.6`, известных code-side P0 security blockers нет.

## Этап B — production-like validation / кандидат в `0.9.0-beta.1`

Цель: доказать, что продукт разворачивается и работает как единая система, а не только проходит unit/CI.

Обязательно:

- feature freeze WB Web v1: новые крупные функции не добавляются;
- поднять отдельный production-like HTTPS environment из репозитория;
- выполнить реальные миграции на чистой БД и upgrade существующей БД;
- проверить deploy и rollback приложения без destructive DB downgrade;
- выполнить core `ops/release_smoke.py`: health/readiness, legal registry, login, protected API, refresh-cookie restore, dashboard contract, logout/revocation;
- проверить регистрацию disposable user + demo subscription + legal consent evidence;
- пройти основные пользовательские сценарии на desktop и mobile: empty/loading/error states, profile, WB connections, dashboards, costs, expenses, plans, tariff flow;
- проверить отсутствие секретов/JWT/WB credentials в frontend bundle, git и application logs.

### Отдельный обязательный gate: точность аналитики

До beta должна быть выполнена приёмочная сверка минимум на одном реальном WB seller account и нескольких фиксированных периодах.

Сверяем WB Insight с официальными WB отчётами и исходной моделью Excel по доступным показателям:

- заказы, продажи и возвраты;
- выручка;
- комиссии WB;
- логистика и хранение;
- реклама;
- себестоимость;
- ручные расходы;
- налоги;
- прибыль;
- выплаты/reconciliation;
- остатки и цены;
- unit-экономика и производные KPI.

Для каждого расхождения фиксируются формула, источник и допустимый tolerance. Нельзя повышать стадию при необъяснённых денежных расхождениях.

Выход этапа: `0.9.0-beta.1` допускается только после green code baseline, feature freeze и успешного production-like core/data-accuracy smoke.

## Этап C — закрыть внешние и эксплуатационные blockers перед RC

### Wildberries

Нужно получить и настроить реальные partner credentials:

- `WB_SERVICE_ID`;
- `WB_SERVICE_SECRET`;
- сервисные API limits;
- отдельный реальный seller account для smoke.

Проверки:

- Base/Service token live validation;
- корректный permission mask и Read Only;
- `X-Client-Secret` + Bearer signing;
- полный sync orders/sales/products/stocks/prices/ads/funnel/paid-storage/finance;
- отсутствие необъяснённых 401/403/429;
- проверка ротации service secret и seller credential expiry alerts.

### Сбер acquiring

Нужно завершить merchant onboarding и получить sandbox/production credentials.

Проверки:

- success;
- decline;
- cancel;
- retry;
- duplicate callback;
- server-side status confirmation;
- ровно одна subscription на один подтверждённый payment;
- production HTTPS callback/return/fail URLs;
- минимальный production smoke-платёж;
- сверка с merchant back office.

### Production infrastructure

Нужно:

- production host/cluster;
- domain + DNS;
- TLS;
- production secret store/env;
- PostgreSQL и Redis с подтверждённым persistence/availability планом;
- один Celery Beat instance;
- migration release procedure;
- deploy/rollback drill.

### Monitoring и incident readiness

Нужно реально подключить, а не только иметь код:

- внешний uptime monitor на `/health/ready`;
- alert destination;
- централизованные structured logs;
- error tracking или эквивалентный процесс triage;
- проверку alert delivery;
- финальную настройку thresholds на production-like traffic.

### Backup / restore

Нужно:

- ежедневный автоматический encrypted backup;
- off-host/object storage;
- retention;
- restore drill из реального backup в отдельную БД;
- подтверждённые фактические RPO/RTO;
- зафиксированный результат drill.

### Legal

Нужно заменить draft-документы утверждёнными versioned документами:

- пользовательское соглашение/оферта;
- privacy policy;
- согласие на обработку персональных данных;
- credential policy;
- refund/cancellation policy;
- реквизиты оператора/продавца услуги.

Обязательно сохранить immutable archive каждой опубликованной версии и production `LEGAL_EVIDENCE_HMAC_KEY`.

## Этап D — account lifecycle и публичная эксплуатация

Перед RC нужно отдельно закрыть жизненный цикл аккаунта, чтобы public stable не зависел от ручного вмешательства разработчика.

Обязательные решения и реализация:

- восстановление/сброс пароля через подтверждённый канал;
- понятный путь отмены платной подписки и возврата в соответствии с утверждённой policy;
- процедура деактивации/удаления аккаунта и retention персональных данных;
- support/admin procedure для заблокированного пользователя, ошибочного платежа и потерянного доступа;
- audit trail административных действий, влияющих на доступ/оплату.

Если часть этих сценариев сознательно остаётся manual/support-mediated в `1.0.0`, это должно быть явно описано в legal/support runbook и не должно требовать прямого изменения БД оператором.

## Этап E — `1.0.0-rc.1`

RC допускается только когда этапы A–D закрыты и полный release smoke подтверждён evidence.

Полный RC smoke включает:

- disposable registration + legal evidence + demo;
- login/refresh/logout;
- реальный WB seller credential;
- полный WB sync;
- все основные dashboard sections;
- COGS, expenses, monthly plan;
- реальный Sber payment flow и paid subscription activation;
- duplicate callback/idempotency;
- monitoring signals;
- off-host encrypted backup;
- restore drill;
- deploy/rollback evidence.

Для RC сохраняются commit SHA, version, environment, UTC timestamp, CI results, smoke output без секретов, WB/Sber evidence, backup/restore evidence и список известных проблем.

## Этап F — `1.0.0` Stable

Stable выпускается из проверенного RC, а не из новой функциональной ветки.

Перед тегом `v1.0.0`:

- нет открытых Critical/High security issues без формально принятого исключения;
- нет необъяснённых финансовых/аналитических расхождений;
- нет release-blocking ошибок по результатам RC эксплуатации;
- production backup актуален;
- rollback plan проверен;
- legal documents опубликованы как non-draft;
- CHANGELOG и release notes финальны;
- все release evidence сохранены;
- exact RC commit либо его минимальный release-fix descendant получает `VERSION=1.0.0` и immutable tag `v1.0.0`.

После deploy `1.0.0` включается усиленный post-release monitoring; новые функции идут уже в следующую release line.

## Кто от кого зависит

### Код/репозиторий — выполняем внутри проекта

P29 security, staging/release automation, data-accuracy acceptance tooling, account-lifecycle gaps, bugfixes по smoke, release evidence templates, CI gates и versioning.

### Внешние действия владельца продукта/инфраструктуры

WB partner credentials и service limits, Сбер merchant onboarding/credentials, production domain/hosting/TLS, legal approval и реквизиты, выбор alert/logging/object-storage providers.

Внешний blocker не блокирует разработку остальных этапов, но без его фактического закрытия нельзя повышать релиз в `1.0.0-rc.N`/`1.0.0`.

## Каноническая последовательность

`0.9.0-alpha.5` -> `0.9.0-alpha.6` (P29 security) -> `0.9.0-beta.1` (feature freeze + production-like + data accuracy) -> `1.0.0-rc.1` (real WB/Sber/prod/legal/ops) -> `1.0.0` (stable).

Источник деталей smoke: `docs/RELEASE_SMOKE.md`. Политика версий: `docs/VERSIONING.md`. Текущий статус blockers: `docs/RELEASE_READINESS.md`.
