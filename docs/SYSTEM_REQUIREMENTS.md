# WB Insight — системные требования

Документ разделяет обязательные software requirements и ориентировочные ресурсы. Ресурсные значения до нагрузочного тестирования являются стартовыми рекомендациями, а не гарантией производительности.

## Поддерживаемое ПО

### Backend development

- Python **3.12**;
- `pip` и `venv`;
- PostgreSQL **16** рекомендуется;
- Redis **7** рекомендуется;
- рабочий компилятор/системные библиотеки только если какая-либо Python dependency не имеет wheel для платформы.

### Frontend development

- Node.js: `^20.19.0` или `>=22.12.0` согласно `frontend/package.json`;
- для CI используется Node.js **22.12.0**;
- npm с поддержкой lockfile v3;
- современный Chromium/Firefox/Safari для проверки UI.

### Container deployment

- Linux host;
- Docker Engine с Compose plugin;
- возможность запускать PostgreSQL 16 и Redis 7 либо доступ к внешним managed PostgreSQL/Redis;
- TLS termination через внешний reverse proxy/load balancer;
- persistent storage для БД и отдельное off-host место для encrypted backups.

## Рекомендуемые ресурсы для разработки

Для локального запуска API + PostgreSQL + Redis + frontend:

- 4 CPU threads;
- 8 GB RAM;
- 10+ GB свободного SSD;
- стабильное интернет-соединение для npm/PyPI и WB API.

Минимальная конфигурация может быть ниже, но одновременная работа PostgreSQL, Celery, Vite и тестов станет заметно медленнее.

## Стартовый production baseline

До нагрузочного тестирования для пилотной установки рекомендуется не менее:

- application host: 2 vCPU / 4 GB RAM;
- PostgreSQL: 2 vCPU / 4 GB RAM с SSD и регулярными backups;
- Redis: 512 MB–1 GB RAM для небольшого числа кабинетов;
- достаточный диск для фактов WB, индексов и логов с мониторингом роста;
- отдельное off-host/object storage для backup artifacts.

При росте количества кабинетов первым масштабируется Celery worker layer и PostgreSQL. Celery Beat должен оставаться одним активным scheduler instance, если не внедрён отдельный distributed scheduler/leader election.

## Сеть

Production должен иметь исходящий HTTPS-доступ как минимум к:

- официальным API Wildberries;
- endpoint Сбер acquiring при включённом acquiring;
- alert webhook/provider, если настроен;
- package registries нужны только на этапе build, а не runtime при использовании готовых images.

Входящий публичный трафик должен идти по HTTPS. Backend не требуется публиковать напрямую: production frontend/nginx работает как same-origin gateway.

## Браузер пользователя

Поддерживается современный evergreen browser с JavaScript, cookies и TLS. Refresh session использует HttpOnly cookie, поэтому блокировка обязательных first-party cookies нарушит восстановление сессии.

## Часовой пояс

Backend хранит/обрабатывает timestamps с timezone-aware semantics. Пользовательский профиль содержит timezone; расчётные периоды и некоторые WB-day semantics должны проверяться при изменении timezone. По умолчанию в UI присутствует `Europe/Moscow`.

## Что проверить перед production

Реальные требования к CPU/RAM/disk фиксируются после production-like теста с ожидаемым числом кабинетов и объёмом исторических данных. До `1.0.0-rc.1` необходимо зафиксировать:

- пиковый CPU/RAM API и worker;
- длительность полного initial sync;
- размер БД после заданного периода истории;
- время backup и restore;
- фактические RPO/RTO;
- допустимую Celery concurrency с учётом WB rate limits.
