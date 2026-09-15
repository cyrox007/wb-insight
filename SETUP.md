# WB Insight — Setup / Operations

Этот документ описывает текущий способ запуска проекта. Схема PostgreSQL управляется **только Alembic**. Не создавайте таблицы вручную по старым SQL-снимкам.

## 1. Требования

- Python 3.12;
- Node.js/npm, совместимые с текущим `frontend/package-lock.json`;
- PostgreSQL 16 рекомендуется;
- Redis;
- Linux/container runtime для production.

## 2. Backend environment

Создайте `backend/.env` на основе `backend/default.env`.

Минимум для development:

```bash
APP_ENV=development
DEBUG=false

SERVER_HTTP_PROTOCOL=http://
SERVER_ADDR=localhost
SERVER_PORT=9000
ALLOWED_ORIGINS=http://localhost:5173

DB_HOST=localhost
DB_PORT=5432
DB_NAME=wb
DB_USER=postgres
DB_PASSWORD=change-me

JWT_SECRET_KEY=replace-with-random-key
API_TOKEN_ENCRYPTION_KEY=replace-with-generated-key

COOKIE_SECURE=false
COOKIE_SAMESITE=lax
REFRESH_COOKIE_NAME=refresh_token

REDIS_URL=redis://localhost:6379/0
ALLOW_FAKE_BILLING=false
```

Сгенерировать секрет приложения:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Сгенерировать Fernet key для marketplace credentials:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Wildberries partner credentials

Для production обязательны обе переменные:

```bash
WB_SERVICE_ID=<asid WB Insight>
WB_SERVICE_SECRET=<service secret WB Insight>
```

Backend намеренно не стартует в `APP_ENV=production`, если одной из них нет.

`X-Client-Secret` используется совместно с Base и Service seller tokens. Подробный контракт: `docs/WB_ACCESS_TOKEN_REQUIREMENTS.md`.

До готовности к Каталогу partner credentials и лимиты сервиса можно запросить у WB API через `business-solutions@rwb.ru`.

## 4. Установка backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 5. База данных

Создайте пустую PostgreSQL database и примените миграции:

```bash
cd backend
alembic upgrade head
alembic current
alembic check
```

`alembic check` должен завершиться без новых операций. Если metadata и migration history расходятся, release блокируется.

Не используйте ручной SQL для создания application tables.

## 6. Backend API

Development:

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 9000
```

Production должен использовать process manager/container runtime без `--reload`.

Проверки:

```bash
curl http://localhost:9000/health/live
curl http://localhost:9000/health/ready
```

`/health/ready` возвращает 200 только при доступных PostgreSQL и Redis.

## 7. Celery

Worker:

```bash
cd backend
celery -A celery_app.celery_app worker --loglevel=INFO
```

Beat scheduler:

```bash
cd backend
celery -A celery_app.celery_app beat --loglevel=INFO
```

Worker и beat — отдельные production processes. Нельзя запускать два beat-инстанса без distributed scheduler/leader election: это приведёт к дублированию периодических задач.

## 8. Backend tests

```bash
cd backend
pytest -q tests
```

Перед merge CI также поднимает чистый PostgreSQL, выполняет полный `alembic upgrade head` и `alembic check`.

## 9. Frontend

Создайте при необходимости `frontend/.env`:

```bash
VITE_API_BASE_URL=http://localhost:9000
```

Development:

```bash
cd frontend
npm ci
npm run dev
```

Release build:

```bash
npm run build
```

## 10. Production security requirements

Обязательно:

```bash
APP_ENV=production
DEBUG=false
COOKIE_SECURE=true
```

Также обязательны:

- сильные `JWT_SECRET_KEY` и `API_TOKEN_ENCRYPTION_KEY`;
- `WB_SERVICE_ID` и `WB_SERVICE_SECRET`;
- точный HTTPS frontend origin в `ALLOWED_ORIGINS`;
- PostgreSQL/Redis credentials из secret manager или deployment environment;
- TLS на внешнем endpoint;
- `ALLOW_FAKE_BILLING=false`.

Не помещайте production secrets в git, Docker image, frontend environment или CI logs.

## 11. Billing

Fake billing разрешён только для локальной разработки:

```bash
APP_ENV=development
ALLOW_FAKE_BILLING=true
```

Публичный production release запрещён до подключения реального acquiring provider. Текущий release plan — Sber acquiring; см. `docs/RELEASE_READINESS.md`.

## 12. Release startup order

1. PostgreSQL доступен.
2. Redis доступен.
3. Production secrets injected.
4. Выполнен backup перед migration для обновляемой среды.
5. `alembic upgrade head`.
6. Backend API стартовал, `/health/ready` = 200.
7. Celery worker стартовал.
8. Celery beat стартовал ровно в одном экземпляре.
9. Frontend release build опубликован.
10. Выполнен release smoke test.

## 13. Что ещё требуется до публичного релиза

Актуальный список блокеров, внешних зависимостей и Definition of Done находится в:

`docs/RELEASE_READINESS.md`.
