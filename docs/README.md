# WB Insight — документация

Этот каталог — каноническая документация проекта. Если код, старый README и документ расходятся, сначала проверяется фактический код и конфигурация текущей версии, затем документация исправляется в том же pull request.

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
- [`MAIL_PROVIDERS.md`](MAIL_PROVIDERS.md) — общий контракт почтовых адаптеров, HTTPS-доставка через порт 443 и правила добавления нового провайдера.
- [`API_REFERENCE.md`](API_REFERENCE.md) — группы API и правила использования OpenAPI.
- [`DEVELOPMENT.md`](DEVELOPMENT.md) — правила веток, миграции, тесты и CI.
- [`SECURITY.md`](SECURITY.md) — модель угроз, сессии, секреты, реквизиты доступа и проверки безопасности.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — типовые проблемы запуска и синхронизации.

## Для администратора и эксплуатации

- [`ADMIN_GUIDE.md`](ADMIN_GUIDE.md) — роли, пользователи, тарифы и панель управления.
- [`OPERATIONS.md`](OPERATIONS.md) — health, monitoring, alerts, backup/restore и incident triage.
- [`INCIDENT_TRIAGE.md`](INCIDENT_TRIAGE.md) — глобальная очередь проблем, приоритизация и переход в сквозную диагностику.
- [`LOG_RETENTION_ARCHIVE.md`](LOG_RETENTION_ARCHIVE.md) — проверяемое архивирование audit/diagnostic журналов без автоматического удаления.
- [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md) — канонический container deploy/upgrade/rollback.
- [`SYSTEMD_DEPLOYMENT.md`](SYSTEMD_DEPLOYMENT.md) — эксплуатация существующей Ubuntu/systemd-установки и транзакционное обновление.
- [`ACCOUNT_LIFECYCLE.md`](ACCOUNT_LIFECYCLE.md) — жизненный цикл аккаунта и оставшиеся release-gaps.

## Интеграции и compliance

- [`WB_ACCESS_TOKEN_REQUIREMENTS.md`](WB_ACCESS_TOKEN_REQUIREMENTS.md) — допустимые реквизиты WB и необходимые права.
- [`SBER_ACQUIRING.md`](SBER_ACQUIRING.md) — платёжный сценарий и требования к production-активации.
- [`LEGAL_CONSENT.md`](LEGAL_CONSENT.md) — версии юридических документов и неизменяемые доказательства согласия.

## Релиз

- [`RELEASE_ROADMAP.md`](RELEASE_ROADMAP.md) — дорожная карта до `1.0.0`.
- [`RELEASE_READINESS.md`](RELEASE_READINESS.md) — текущее состояние готовности и блокеров.
- [`AUDIT_CLOSURE_2026_10_05.md`](AUDIT_CLOSURE_2026_10_05.md) — состояние выполнения требований аудита от 5 октября 2026 года.
- [`RELEASE_SMOKE.md`](RELEASE_SMOKE.md) — CI, production-like и внешние интеграционные проверки.
- [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md) — manifest доказательств beta/RC/stable для точного коммита.
- [`VERSIONING.md`](VERSIONING.md) — SemVer и правила `alpha -> beta -> rc -> stable`.
- [`VERSION_HISTORY.md`](VERSION_HISTORY.md) — подробная история развития.
- [`../CHANGELOG.md`](../CHANGELOG.md) — пользовательские заметки о версиях.

## Принципы документации

1. Каноническая версия продукта хранится в корневом `VERSION`.
2. Документация описывает только реализованное поведение; будущие функции явно маркируются как план.
3. Секреты, реальные WB-токены, банковские реквизиты доступа и персональные данные в документацию не попадают.
4. Изменение публичного поведения, конфигурации, схемы данных, release process или security contract сопровождается обновлением соответствующего документа.
5. Старые файлы `README-FOR-*` считаются историческими материалами и не являются источником истины.
6. Инструмент приёмки не является доказательством её прохождения: beta/RC/stable требуют evidence, полученный на соответствующей среде и точном коммите.
7. Исторический release candidate не должен описываться как текущая версия после дальнейшего развития `dev`.
8. Пользовательские и операторские сообщения, комментарии и документация проекта ведутся на русском языке; технические идентификаторы и названия протоколов сохраняют исходное написание.

Дата полной ревизии: **20 октября 2026 года**.
