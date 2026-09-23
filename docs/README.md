# WB Insight — документация

Этот каталог — каноническая документация проекта. Если код, старый README и документ расходятся, сначала проверяется фактический код и конфигурация текущей версии, затем документация исправляется в том же PR.

## Быстрый вход

- [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) — что такое WB Insight, для кого он и что входит в WB Web v1.
- [`SYSTEM_REQUIREMENTS.md`](SYSTEM_REQUIREMENTS.md) — поддерживаемое ПО и ориентиры по ресурсам.
- [`INSTALLATION.md`](INSTALLATION.md) — локальная установка, запуск и production baseline.
- [`CONFIGURATION.md`](CONFIGURATION.md) — переменные окружения и секреты.
- [`USER_GUIDE.md`](USER_GUIDE.md) — путь пользователя от регистрации до аналитики и оплаты.
- [`ONBOARDING.md`](ONBOARDING.md) — минимальный путь от регистрации до первых полезных данных и диагностика подключения WB.
- [`FEATURES.md`](FEATURES.md) — функции продукта и назначение каждого раздела.
- [`DATA_AND_METRICS.md`](DATA_AND_METRICS.md) — источники данных, смысл ключевых показателей и правила сверки.
- [`DATA_ACCURACY_ACCEPTANCE.md`](DATA_ACCURACY_ACCEPTANCE.md) — обязательная сверка аналитики перед beta.

## Для разработчика

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — компоненты, потоки данных и границы ответственности.
- [`API_REFERENCE.md`](API_REFERENCE.md) — группы API и правила использования OpenAPI.
- [`DEVELOPMENT.md`](DEVELOPMENT.md) — workflow разработки, миграции, тесты и CI.
- [`SECURITY.md`](SECURITY.md) — модель угроз, сессии, секреты, credentials и security gates.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — типовые проблемы запуска и синхронизации.

## Для администратора и эксплуатации

- [`ADMIN_GUIDE.md`](ADMIN_GUIDE.md) — роли, пользователи, тарифы и control panel.
- [`OPERATIONS.md`](OPERATIONS.md) — health, monitoring, alerts, backup/restore и incident triage.
- [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md) — канонический container deploy/upgrade/rollback.
- [`SYSTEMD_DEPLOYMENT.md`](SYSTEMD_DEPLOYMENT.md) — эксплуатация существующей Ubuntu/systemd-установки, безопасное обновление и переход backend venv на Python 3.12.
- [`ACCOUNT_LIFECYCLE.md`](ACCOUNT_LIFECYCLE.md) — жизненный цикл аккаунта и оставшиеся release-gaps.

## Интеграции и compliance

- [`WB_ACCESS_TOKEN_REQUIREMENTS.md`](WB_ACCESS_TOKEN_REQUIREMENTS.md) — допустимые WB credentials и permissions.
- [`SBER_ACQUIRING.md`](SBER_ACQUIRING.md) — acquiring flow и требования к production activation.
- [`LEGAL_CONSENT.md`](LEGAL_CONSENT.md) — versioned legal documents и immutable consent evidence.

## Релиз

- [`RELEASE_ROADMAP.md`](RELEASE_ROADMAP.md) — дорожная карта до `1.0.0`.
- [`RELEASE_READINESS.md`](RELEASE_READINESS.md) — текущий статус blockers/gates.
- [`RELEASE_SMOKE.md`](RELEASE_SMOKE.md) — CI, production-like и external integration smoke.
- [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md) — manifest доказательств beta/RC/stable для exact commit.
- [`VERSIONING.md`](VERSIONING.md) — SemVer и правила `alpha -> beta -> rc -> stable`.
- [`VERSION_HISTORY.md`](VERSION_HISTORY.md) — подробная история развития.
- [`../CHANGELOG.md`](../CHANGELOG.md) — пользовательские release notes.

## Принципы документации

1. Каноническая версия продукта хранится в корневом `VERSION`.
2. Документация описывает только реализованное поведение; будущие функции маркируются как roadmap/backlog.
3. Секреты, реальные WB tokens, merchant credentials и персональные данные в документацию не попадают.
4. Изменение публичного поведения, конфигурации, схемы данных, release process или security contract должно сопровождаться обновлением соответствующего документа.
5. Старые файлы `README-FOR-*` считаются историческими материалами и не являются source of truth.
6. Acceptance tooling не считается доказательством прохождения acceptance: beta/RC/stable требуют evidence, полученный на соответствующей среде и exact commit.

Дата полной ревизии: 16 сентября 2026 года.
