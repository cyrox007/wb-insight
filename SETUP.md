# WB Insight — Setup

Этот файл сохранён как короткая точка входа для старых ссылок. Каноническая инструкция теперь находится в [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

Связанные документы:

- [`docs/SYSTEM_REQUIREMENTS.md`](docs/SYSTEM_REQUIREMENTS.md) — системные требования;
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — переменные окружения;
- [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md) — production deploy/upgrade/rollback;
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — monitoring, alerts, backup/restore;
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — диагностика проблем.

Минимальный development flow:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app:app --reload --host 0.0.0.0 --port 9000
```

В другом терминале:

```bash
cd frontend
npm ci
npm run dev
```

Для полноценной работы также нужны PostgreSQL, Redis и отдельные Celery worker/beat процессы. Схема БД управляется только Alembic.
