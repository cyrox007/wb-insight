# WB Insight — разработка

## Branch / PR workflow

Работа выполняется в отдельных ветках от `dev`.

Канонический поток:

1. `feature/*`, `fix/*`, `chore/*` создаются от актуального `dev`;
2. рабочие PR направляются в `dev`;
3. `dev` является интеграционной веткой и накапливает завершённые задачи текущей release-линии;
4. `main` не используется как рабочая интеграционная ветка;
5. promotion `dev -> main` выполняется отдельным release/release-candidate PR после consolidated exact-head CI и требуемого acceptance/evidence.

Прямой merge рабочих веток в `main` запрещён. Срочные hotfix для уже опубликованного production-релиза оформляются отдельно и после выпуска обязательно синхронизируются обратно в `dev`.

Основные checks:

- Backend security/tests;
- Frontend build/security audit;
- Database migrations;
- Release integrity.

## Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q tests
pip-audit -r requirements.txt --progress-spinner off
```

Новая backend capability должна иметь тесты на happy path и критичные failure/security cases.

## Frontend

```bash
cd frontend
npm ci
npm audit --omit=dev --audit-level=high
npm audit --audit-level=high
npm run build
```

Persistent browser storage для access JWT запрещён CI guard-ом.

## Миграции

После изменения SQLAlchemy metadata:

1. создать/проверить Alembic migration;
2. проверить upgrade на чистой PostgreSQL;
3. выполнить `alembic check`;
4. убедиться, что downgrade/rollback assumptions задокументированы;
5. не смешивать ручное создание таблиц и migration history.

Команды:

```bash
alembic upgrade head
alembic current
alembic check
```

## Бизнес-метрики

Изменение формулы требует regression test и обновления `DATA_AND_METRICS.md`. Если значение видимо пользователю, изменение фиксируется в CHANGELOG.

Нельзя переносить критичные формулы во frontend ради удобства UI.

## Marketplace integrations

External API code должен использовать общий transport/adapters layer там, где он предусмотрен. Требования:

- account scope;
- typed errors;
- bounded retries;
- уважение rate limits/Retry-After;
- checkpoint/restart safety;
- отсутствие секретов в logs.

## Security-sensitive changes

При изменении auth, billing, credentials, roles, legal consent или admin flows обязательно проверяются обходные/legacy endpoints. Наличие нового безопасного endpoint не считается исправлением, если старый endpoint позволяет обойти правило.

## Frontend UX

Каждый аналитический экран должен иметь осмысленные состояния:

- loading;
- syncing;
- empty;
- error;
- success.

Не используйте hardcoded/demo KPI как fallback для production data.

## Версии

Root `VERSION` — source of truth. Release change синхронизирует:

- `VERSION`;
- `frontend/package.json`;
- `CHANGELOG.md`;
- при milestone — `docs/VERSION_HISTORY.md`, `VERSIONING.md`, `RELEASE_READINESS.md`.

## Документация как часть Definition of Done

Изменение считается незавершённым, если публичный contract изменился, а соответствующий canonical doc остался старым. Навигация документов — `docs/README.md`.

## Release branches/stages

Текущая последовательность до v1:

`alpha` -> `beta` -> `rc` -> `stable`.

Stage gates определяются не количеством коммитов, а `RELEASE_ROADMAP.md` и `RELEASE_READINESS.md`.

## Что нельзя коммитить

- реальные `.env`;
- пароли/secret keys;
- WB seller secrets;
- bank merchant credentials;
- refresh/access sessions;
- production backup passphrase;
- персональные данные пользователей;
- production database dumps.

## Self-review перед PR

Перед ожиданием CI проверить:

- альтернативные/legacy API paths;
- tenant/account isolation;
- idempotency;
- timezone/date boundaries;
- empty/error states;
- migration drift;
- logs на наличие secrets;
- docs/version metadata.
