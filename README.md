# WB Insight

**Main:** `0.9.0-alpha.6` после P29. **Текущий кандидат:** `0.9.0-alpha.7` / P30. Каноническая версия ветки всегда находится в корневом `VERSION`.

WB Insight — web-сервис управленческой аналитики для продавцов Wildberries. Он собирает данные из официальных WB API, добавляет данные продавца (себестоимость, собственные расходы, налоговые параметры, план) и рассчитывает единый набор показателей для управления прибылью, рекламой, запасами, ценами и выплатами.

## Документация

Полный индекс: [`docs/README.md`](docs/README.md).

Основные документы:

- [Обзор проекта](docs/PROJECT_OVERVIEW.md)
- [Системные требования](docs/SYSTEM_REQUIREMENTS.md)
- [Установка и запуск](docs/INSTALLATION.md)
- [Конфигурация](docs/CONFIGURATION.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Функции](docs/FEATURES.md)
- [Руководство пользователя](docs/USER_GUIDE.md)
- [Данные и метрики](docs/DATA_AND_METRICS.md)
- [Data-accuracy acceptance](docs/DATA_ACCURACY_ACCEPTANCE.md)
- [Руководство администратора](docs/ADMIN_GUIDE.md)
- [Разработка](docs/DEVELOPMENT.md)
- [Безопасность](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Operations](docs/OPERATIONS.md)
- [Production deployment](docs/PRODUCTION_DEPLOYMENT.md)
- [Дорожная карта до 1.0.0](docs/RELEASE_ROADMAP.md)
- [Release readiness](docs/RELEASE_READINESS.md)
- [Release evidence](docs/RELEASE_EVIDENCE.md)
- [История версий](docs/VERSION_HISTORY.md)
- [CHANGELOG](CHANGELOG.md)

## WB Web v1

Первый стабильный релиз `1.0.0` ориентирован на Wildberries и включает:

- регистрацию, безопасную сессию и роли;
- тарифы/demo/лимиты;
- подключение WB-кабинетов;
- автоматическую account-scoped синхронизацию;
- Overview, Unit Economy, Finance/Reconciliation, Inventory, Prices и Ads;
- funnel и paid storage data;
- historical COGS, seller expenses и revenue plan;
- versioned legal consent;
- Сбер acquiring code path;
- production deployment, monitoring и backup/restore baseline.

Ozon, AI-аналитик, native mobile и WB OAuth onboarding не входят в `1.0.0`.

## Стек

Backend: Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, Alembic, Celery, Redis, httpx.

Frontend: Vue 3, Pinia, Vue Router, Axios, Vite, nginx.

Production baseline: Docker/Compose с отдельными migration/API/worker/beat/frontend процессами.

## Быстрый локальный запуск

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app:app --reload --host 0.0.0.0 --port 9000
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Полная инструкция: [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## CI / release discipline

Release candidate должен иметь green на одном exact head:

- backend tests + `pip-audit`;
- frontend npm audits + production build + session storage guard;
- Alembic upgrade/check;
- release integrity: version consistency, acceptance-tools self-test, Docker/Compose, nginx gateway smoke и backup/restore roundtrip.

Изменение `VERSION` автоматически запускает backend security и database migrations, поэтому release metadata не может обойти эти gates.

Переход `alpha -> beta -> rc -> stable` определяется release evidence, а не количеством commits. См. [`docs/VERSIONING.md`](docs/VERSIONING.md), [`docs/RELEASE_ROADMAP.md`](docs/RELEASE_ROADMAP.md) и [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md).

## Текущий фокус

P29 уже закрыл dependency/security hardening. P30 создаёт воспроизводимую сверку аналитики и evidence manifest. После P30 `0.9.0-beta.1` разрешена только при фактическом production-like smoke и реальной data-accuracy acceptance на seller account; сам merge tooling beta не назначает.
