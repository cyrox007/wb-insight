# WB Insight — troubleshooting

## `pip install` падает на `numpy==2.4.6` / сервер использует Python 3.10

Актуальный backend стандартизирован на Python **3.12**. Если путь pip показывает `venv/lib/python3.10/...`, старый systemd venv несовместим с текущим dependency graph.

Не понижайте NumPy/Pandas вручную в production: это создаст окружение, отличающееся от CI/Docker и зафиксированного `requirements.txt`.

Если `git pull` уже прошёл, а установка зависимостей упала до Alembic/frontend/restart:

1. не перезапускайте API/Celery на незавершённом environment;
2. установите доступный на host Python 3.12 + `python3.12-venv`;
3. создайте новый venv через `python3.12 -m venv venv.next`;
4. установите `requirements.txt` в новый venv;
5. примените Alembic новым environment;
6. выполните `npm ci && npm run build`;
7. переключите `backend/venv` на новый venv;
8. только затем restart services и проверьте `/health/ready`.

Полный runbook: [`SYSTEMD_DEPLOYMENT.md`](SYSTEMD_DEPLOYMENT.md). Для последующих обновлений используйте `ops/update_systemd.sh`, который выполняет runtime preflight до переключения сервисов.

## Backend не стартует

Проверьте:

- активирован ли Python 3.12 environment;
- установлены ли `requirements-dev.txt`/`requirements.txt`;
- существует ли `backend/.env`;
- доступны ли PostgreSQL и Redis;
- заданы ли обязательные secrets для выбранного `APP_ENV`.

Production может намеренно fail-closed при неполной безопасной конфигурации.

## `/health/live` работает, `/health/ready` нет

Это означает, что процесс API жив, но одна из runtime-зависимостей не готова. В первую очередь проверьте PostgreSQL и Redis, затем connectivity/credentials.

## Alembic error или drift

```bash
cd backend
alembic current
alembic upgrade head
alembic check
```

Не создавайте недостающие application tables вручную. Если metadata требует новую migration, исправьте migration history в коде.

## Frontend не устанавливается через `npm ci`

`npm ci` требует полного соответствия `package.json` и `package-lock.json`. Не исправляйте это удалением lockfile в release branch. Обновите dependency declaration и воспроизводимо регенерируйте lockfile, затем повторите audits/build.

Проверьте Node version: проект требует `^20.19.0` или `>=22.12.0`; CI использует 22.12.0.

## Frontend открывается, API недоступен

Development: проверьте `VITE_API_BASE_URL` и CORS.

Production: frontend должен использовать same-origin nginx gateway. Проверьте routing `/auth`, `/dashboard`, `/billing`, `/legal`, `/control-panel`, `/health` и backend health.

## После reload пользователь вышел из системы

Проверьте:

- доступна ли refresh endpoint;
- передаётся ли HttpOnly cookie;
- `COOKIE_SECURE` соответствует HTTP/HTTPS среде;
- SameSite/domain/path cookie;
- не истекла/не отозвана ли refresh session.

Access token не должен храниться в localStorage как способ «исправить» reload.

## WB-кабинет не добавляется

Проверьте требования `WB_ACCESS_TOKEN_REQUIREMENTS.md`. Типичные причины:

- неподходящий тип подключения;
- истёкший срок;
- не хватает permissions;
- не включён Read Only;
- service binding не соответствует сервису;
- live validation WB не прошла;
- превышен лимит кабинетов тарифа.

## Sync завис/не обновляется

Проверьте:

- operations health;
- Celery worker;
- Celery Beat;
- Redis;
- failed/stale sync jobs;
- expiry подключения;
- 429/rate limits;
- внешние WB ошибки.

Не запускайте несколько Beat instances для «ускорения».

## Есть заказы, но Finance отличается

Operational orders/sales и finance realization — разные источники. Проверьте период и reconciliation detail. Расхождение не исправляется подменой finance значениями orders.

## Прибыль кажется неверной

Проверьте:

- historical COGS и дату действия;
- manual expenses;
- рекламные расходы;
- налоговый параметр;
- период;
- account scope;
- полноту finance/sales sync.

При воспроизводимом расхождении используйте процедуру из `DATA_AND_METRICS.md`.

## Inventory recommendation выглядит странно

Проверьте остатки и недавний спрос. Baseline рекомендация является модельной оценкой и может требовать дополнительного бизнес-контекста: lead time, будущих акций, сезонности и внешних поставок.

## Реклама пустая, остальная аналитика работает

Это может быть feature-specific permission issue. Не делайте вывод, что весь credential недействителен, пока backend не классифицировал ошибку как auth failure.

## Платёж завершён, тариф не активирован

Не ориентируйтесь только на страницу возврата банка. Backend активирует subscription после server-side status confirmation. Администратор должен проверить payment attempt/provider state/idempotency по `SBER_ACQUIRING.md`.

## Backup не создаётся

Проверьте PostgreSQL client utilities, DB environment, writable `BACKUP_DIR` и доступность passphrase file. Plaintext dump не должен оставаться после успешного шифрования.

## Restore script отказывается работать

Destructive restore специально требует `RESTORE_CONFIRM=YES`. Для проверки backup используйте isolated restore drill вместо снятия защиты production restore.

## CI неожиданно красный

Всегда проверяйте exact latest PR head. Основные контуры:

- backend tests/dependency audit;
- frontend npm audit/build/session guard;
- Alembic migrations/check;
- release integrity: versions, Docker, Compose, gateway, backup/restore.

Не merge-ить PR по зелёному старому commit после появления нового head.
