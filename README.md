# WB Insight

Current version: **0.9.0-alpha.2**.

WB Insight — web-сервис аналитики для продавцов Wildberries. Проект собирает данные через официальный WB API, связывает операционные, маркетинговые и финансовые факты и рассчитывает показатели, которые продавец использует для управления прибылью.

Версионная политика: [`docs/VERSIONING.md`](docs/VERSIONING.md). Подробная история: [`CHANGELOG.md`](CHANGELOG.md).

## Текущий release scope

Первый стабильный релиз — **WB Insight Web v1 (`1.0.0`)**. В него входят:

- регистрация, авторизация и refresh-session;
- роли и административная панель;
- тарифы, demo-подписка и лимиты WB-кабинетов;
- безопасное подключение WB-кабинетов;
- автоматическая синхронизация через Celery/Redis;
- заказы и продажи;
- товары и остатки;
- цены и скидки;
- реклама;
- воронка продаж;
- платное хранение;
- финансовая детализация и reconciliation;
- себестоимость с историей;
- ручные расходы;
- план выручки;
- обзор KPI, финансы, остатки, цены, реклама и unit-экономика.

Ozon, AI-аналитик и native mobile apps находятся за пределами WB Web v1 и не должны считаться доступными production-функциями до отдельного релиза.

## Wildberries access model

WB Insight — облачный партнёрский сервис. Production backend принимает только допустимые для cloud-flow seller credentials и проверяет их до сохранения.

Текущие требования:

- Base token — до подключения через Каталог решений;
- Service token — для сервиса, зарегистрированного/авторизованного в WB;
- Personal token не принимается;
- Test token не принимается в production;
- seller token должен быть **Только чтение**;
- обязательные категории: Контент, Аналитика, Цены и скидки, Статистика, Продвижение, Финансы;
- `exp`, `sid`, `acc`, `for` и permission mask читаются из JWT;
- перед сохранением выполняется live `/ping` в WB;
- запросы с Base и Service tokens подписываются `X-Client-Secret` партнёрского сервиса;
- `WB_SERVICE_ID` и `WB_SERVICE_SECRET` обязательны в production.

Подробно: [`docs/WB_ACCESS_TOKEN_REQUIREMENTS.md`](docs/WB_ACCESS_TOKEN_REQUIREMENTS.md).

## Архитектура

### Backend

- Python 3.12;
- FastAPI;
- SQLAlchemy 2 / asyncpg;
- PostgreSQL;
- Celery;
- Redis;
- Alembic;
- httpx.

### Frontend

- Vue 3;
- Pinia;
- Vue Router;
- Axios;
- Vite;
- nginx production runtime.

### Sync

Синхронизация account-scoped: каждая задача привязана к конкретному marketplace credential. Durable jobs используют lease/retry semantics. Marketplace-specific код отделён через `MarketplaceAdapter`; Wildberries реализован первым адаптером, Ozon будет подключаться к той же orchestration-схеме.

## Безопасность

- marketplace secrets хранятся только в зашифрованном виде;
- refresh token — HttpOnly cookie;
- production требует `JWT_SECRET_KEY` и `API_TOKEN_ENCRYPTION_KEY`;
- fake billing отключён в production;
- WB production access fail-closed без partner service credentials;
- audit middleware не логирует request body с секретами;
- CORS задаётся allowlist через `ALLOWED_ORIGINS`.

Browser access JWT пока хранится в `localStorage`; его перенос в in-memory session относится к release hardening и отслеживается в `docs/RELEASE_READINESS.md`.

## Health

- `GET /health/live` — liveness процесса + deployed version;
- `GET /health/ready` — readiness PostgreSQL + Redis + deployed version.

## Billing

Backend поддерживает Sber internet acquiring через server-to-server `register.do` и `getOrderStatusExtended.do`.

Критические свойства flow:

- одна платёжная попытка имеет `Idempotency-Key`;
- frontend получает `formUrl` и переходит на платёжную форму Сбера;
- redirect/callback сам по себе не активирует тариф;
- backend повторно проверяет статус у Сбера;
- подписка активируется только после подтверждённого `orderStatus=2` + `paymentState=DEPOSITED`;
- payment связан с подпиской и защищён от повторной активации;
- события провайдера сохраняются без merchant credentials и неизвестных чувствительных полей.

Acquiring выключен по умолчанию и включается только после выдачи merchant credentials. Подробно: [`docs/SBER_ACQUIRING.md`](docs/SBER_ACQUIRING.md).

Fake payments существуют только для локальной разработки и должны включаться явно через `ALLOW_FAKE_BILLING=true` при `APP_ENV != production`.

## Запуск разработки

Backend environment создаётся из `backend/default.env`. Схема БД управляется только Alembic:

```bash
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
pytest -q tests
uvicorn app:app --reload --host 0.0.0.0 --port 9000
```

Celery worker и scheduler запускаются отдельными процессами согласно текущей конфигурации `celery_app.py`.

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Production baseline

P25 добавляет воспроизводимый container deployment:

```bash
cp .env.production.example .env.production
# заполнить реальные production values

docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

Стек разделяет migration, API, Celery worker, Celery beat, frontend/nginx, PostgreSQL и Redis. HTTPS должен завершаться внешним reverse proxy/load balancer. Полный runbook: [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md).

## CI

Pull requests проверяются четырьмя контурами:

- backend tests/security;
- frontend build;
- чистый PostgreSQL → `alembic upgrade head` → `alembic check`;
- release integrity: canonical version, Docker image builds и Compose validation.

## Release readiness

Актуальный список блокеров и Definition of Done: [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md).

Ключевые внешние блокеры первого публичного релиза:

1. получить `WB_SERVICE_ID` + `WB_SERVICE_SECRET` и лимиты сервиса у Wildberries;
2. получить test/production merchant credentials Сбер acquiring и провести bank smoke;
3. подготовить production domain/TLS и юридические документы сервиса.

После P25 основные code/ops блоки до beta/RC:

1. monitoring/alerts и backup/restore;
2. legal pages + consent persistence;
3. browser session hardening и release smoke suite.

## Roadmap после WB Web v1

- Ozon Seller API через общий marketplace adapter;
- Wildberries Service token / OAuth 2.0 onboarding через Каталог решений;
- AI-аналитик и рекомендации;
- mobile clients — только после стабилизации web API и product-market fit.
