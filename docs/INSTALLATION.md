# WB Insight — установка и запуск

Канонические требования: [`SYSTEM_REQUIREMENTS.md`](SYSTEM_REQUIREMENTS.md). Переменные окружения: [`CONFIGURATION.md`](CONFIGURATION.md).

## 1. Получить репозиторий

```bash
git clone <repository-url>
cd wb-insight
```

Для воспроизводимой установки используйте версии зависимостей из `backend/requirements*.txt` и `frontend/package-lock.json`.

## 2. PostgreSQL и Redis

Для development можно использовать локальные сервисы или контейнеры. Требуются:

- PostgreSQL с отдельной database/user;
- Redis instance;
- сетевой доступ backend к обоим сервисам.

Схема application DB создаётся и обновляется **только Alembic**. Не импортируйте старые SQL snapshots как способ установки.

## 3. Backend environment

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Создайте `backend/.env` на основе `backend/default.env` и задайте development values. Минимально нужны DB, Redis, JWT secret и Fernet-compatible encryption key.

Секрет приложения:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Fernet key для marketplace credentials:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 4. Миграции

```bash
cd backend
alembic upgrade head
alembic current
alembic check
```

`alembic check` должен завершаться без незакоммиченных schema changes. Расхождение metadata и migration history — release blocker.

## 5. Backend API

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 9000
```

Проверка:

```bash
curl http://localhost:9000/health/live
curl http://localhost:9000/health/ready
```

`/health/live` проверяет процесс. `/health/ready` дополнительно требует доступные PostgreSQL и Redis.

FastAPI OpenAPI/Swagger доступен стандартным способом в development, если не отключён конфигурацией приложения.

## 6. Celery

В отдельном терминале:

```bash
cd backend
source .venv/bin/activate
celery -A celery_app.celery_app worker --loglevel=INFO
```

Beat scheduler:

```bash
cd backend
source .venv/bin/activate
celery -A celery_app.celery_app beat --loglevel=INFO
```

Для production должен существовать ровно один активный Beat instance, пока не внедрён distributed scheduler.

## 7. Frontend

```bash
cd frontend
npm ci
npm run dev
```

Для development можно указать:

```bash
VITE_API_BASE_URL=http://localhost:9000
```

Production build:

```bash
npm run build
```

Production frontend использует same-origin API gateway; `localhost:9000` не должен быть production default.

## 8. Тесты и security audit

Backend:

```bash
cd backend
pytest -q tests
pip-audit -r requirements.txt --progress-spinner off
```

Frontend:

```bash
cd frontend
npm ci
npm audit --omit=dev --audit-level=high
npm audit --audit-level=high
npm run build
```

## 9. Development Wildberries

Без настоящего seller credential UI/API можно разрабатывать частично, но реальные sync/dashboards требуют допустимый WB token. Production contract существенно строже development: см. [`WB_ACCESS_TOKEN_REQUIREMENTS.md`](WB_ACCESS_TOKEN_REQUIREMENTS.md).

Никогда не помещайте реальный WB token в git, screenshots, issue bodies или test fixtures.

## 10. Development billing

Fake billing допускается только локально и только при явном включении:

```bash
APP_ENV=development
ALLOW_FAKE_BILLING=true
```

Production должен иметь `ALLOW_FAKE_BILLING=false`. Реальный flow описан в [`SBER_ACQUIRING.md`](SBER_ACQUIRING.md).

## 11. Production через Docker Compose

```bash
cp .env.production.example .env.production
# заполнить production values через безопасный secret-management процесс

docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

Topology:

1. `postgres` и `redis`;
2. one-shot `migrate`;
3. `backend`;
4. `worker`;
5. `beat`;
6. `frontend`/nginx.

Frontend публикуется на `${PUBLIC_HTTP_PORT:-8080}`. TLS завершается внешним reverse proxy/load balancer.

Полный production runbook: [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md).

## 12. Порядок первого production запуска

1. Настроить domain/DNS/TLS.
2. Подготовить PostgreSQL и Redis.
3. Внести production secrets вне git.
4. Проверить WB partner credentials.
5. Настроить Sber only после merchant onboarding.
6. Выполнить `alembic upgrade head`.
7. Дождаться `/health/ready = 200`.
8. Запустить worker и один beat.
9. Проверить frontend/nginx gateway.
10. Настроить alerts/logging/backups.
11. Выполнить [`RELEASE_SMOKE.md`](RELEASE_SMOKE.md).

## 13. Обновление

Перед upgrade production DB:

- создать encrypted backup;
- зафиксировать текущий commit/version;
- применить новый image и migration;
- проверить health и smoke;
- при проблеме откатывать application image по runbook. Destructive DB downgrade не является стандартной rollback-стратегией.

## 14. Частые ошибки

См. [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md). Основные категории: PostgreSQL/Redis unavailable, Alembic drift, invalid WB credential/permissions, CORS/cookie mismatch, Celery not running, disabled acquiring и stale sync.
