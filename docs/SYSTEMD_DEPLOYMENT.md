# WB Insight — deployment через systemd

Канонический production baseline проекта — Docker Compose, но существующая установка на Ubuntu может продолжать работать через systemd при соблюдении того же runtime-контракта.

## Обязательные версии

- Python **3.12** для backend, worker и beat;
- Node.js `^20.19.0` или `>=22.12.0` для сборки frontend;
- PostgreSQL 16 рекомендуется;
- Redis 7 рекомендуется;
- nginx как внешний web/gateway слой;
- `flock`, `pg_dump`, `pg_restore`, `psql`, `openssl`, `sha256sum` для транзакционного обновления и восстановления;
- зависимости строго из `backend/requirements.txt` и `frontend/package-lock.json`.

Не обновляйте старый Python `venv` на месте. Updater создаёт неизменяемый `venv.release.<timestamp>` по окончательному пути и переключает стабильный `backend/venv` через symlink. Перемещать release-venv после установки нельзя: launchers Python содержат абсолютный путь к интерпретатору.

## Обязательная подготовка rollback БД

Транзакционное обновление fail-closed: перед первой миграцией оно обязано создать зашифрованную резервную копию PostgreSQL. В runtime должны быть доступны:

```env
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=wb
DB_USER=wb
DB_PASSWORD=...
BACKUP_ENCRYPTION_PASSPHRASE_FILE=/etc/wb-insight/backup-passphrase
BACKUP_RETENTION_DAYS=14
```

Файл `BACKUP_ENCRYPTION_PASSPHRASE_FILE` должен существовать, читаться пользователем updater-а и храниться вне репозитория. По умолчанию update-backup сохраняется в `/var/backups/wb-insight/update`; путь можно изменить через `UPDATE_BACKUP_DIR`.

Если резервную копию создать нельзя, updater **не применяет миграции и не переключает release**.

## Канонический запуск

Используйте корневой entrypoint, а не ручной `git pull`:

```bash
cd /home/projects/wb
./update.sh
```

Для acceptance ветки `dev`:

```bash
cd /home/projects/wb
TARGET_BRANCH=dev ./update.sh
```

Для другого пути и health endpoint:

```bash
PROJECT_DIR=/srv/wb-insight \
HEALTH_URL=http://127.0.0.1:9000/health/ready \
TARGET_BRANCH=dev \
./update.sh
```

Быстрый preflight без установки зависимостей, миграций и переключения runtime:

```bash
TARGET_BRANCH=dev ./update.sh --preflight-only
```

## Транзакционная модель P116

Обновление выполняется как одна согласованная транзакция приложения:

1. `update.sh` получает эксклюзивный `flock`; второй параллельный запуск завершается до любых изменений;
2. фиксируются текущий и целевой Git commit;
3. проверяется только fast-forward путь от текущей версии к `origin/<TARGET_BRANCH>`;
4. последняя версия самого updater-а извлекается через `git show` во временный файл **без переключения рабочего дерева**;
5. целевой commit распаковывается через `git archive` во временный каталог кандидата;
6. в кандидате полностью создаётся новый Python 3.12 release-venv, устанавливаются backend dependencies, выполняются import/Celery/Alembic проверки;
7. frontend кандидата полностью проходит `npm ci` и `npm run build` до изменения БД и активного runtime;
8. проверяется конфигурация nginx;
9. только после готовности кандидата останавливаются `wb-backend`, `wb-celery`, `wb-celery-beat`, чтобы rollback БД не терял новые записи;
10. создаётся зашифрованный `pg_dump` и SHA-256 контрольная сумма;
11. миграции Alembic выполняются кодом и Python-средой кандидата;
12. рабочая ветка переключается на заранее проверенный целевой commit;
13. `backend/venv` переключается на новый immutable release-venv;
14. устанавливаются canonical systemd drop-ins и запускаются сервисы;
15. локальная проверка готовности backend должна пройти **до** публикации новой клиентской сборки;
16. frontend публикуется с собственным rollback-контуром;
17. выполняются повторная проверка systemd, Celery ping, nginx и `/health/ready`;
18. только после postcheck обновление считается завершённым.

Таким образом, `git fetch`, установка зависимостей и сборка frontend не меняют текущую обслуживаемую версию.

## Автоматический rollback

После входа в фазу переключения любая необработанная ошибка запускает coordinated rollback. Updater:

1. останавливает API и фоновые обработчики;
2. если миграции уже могли изменить БД — восстанавливает зашифрованный dump через `ops/postgres_restore.sh`;
3. возвращает предыдущий опубликованный frontend;
4. возвращает Git на исходный commit;
5. возвращает предыдущий `backend/venv`;
6. восстанавливает systemd drop-ins из предыдущего commit;
7. запускает старые сервисы только если критические части rollback завершились успешно.

Если восстановление БД или runtime не удалось, updater **не пытается скрыть аварию запуском потенциально несовместимой версии**: сервисы остаются остановленными, а оператор получает сообщение о ручном вмешательстве.

Доказательство попытки rollback записывается без секретов в:

```text
/var/tmp/wb-insight-update/rollback-<timestamp>.txt
```

Путь можно изменить через `UPDATE_STATE_DIR`.

Автоматический `alembic downgrade` намеренно не используется: rollback схемы выполняется восстановлением согласованной резервной копии.

## Защита от параллельного обновления

Корневой `update.sh` удерживает lock-файл весь жизненный цикл процесса:

```text
/tmp/wb-insight-update.lock
```

Путь можно изменить через `UPDATE_LOCK_FILE`. Второй updater не ждёт первый процесс и не начинает собственную миграцию — он завершается с понятной ошибкой.

## Безопасная публикация frontend

`ops/publish_frontend.sh` сначала копирует готовую сборку во staging-каталог. Если существует текущий nginx root, он перемещается в `wb-prev-*`, и **сразу после этого** фиксируется состояние `OLD_MOVED=true`. Поэтому ошибка между переносом старой версии и установкой новой больше не оставляет nginx без активного frontend: trap возвращает предыдущий каталог.

При вызове из updater-а скрипт принимает:

- `FRONTEND_BUILD_DIR` — готовый `dist` кандидата;
- `FRONTEND_PUBLISH_STATE_FILE` — безопасный файл состояния для coordinated rollback;
- `FRONTEND_DEPLOY_DIR` — явный nginx root, если autodetect не подходит.

Без `FRONTEND_DEPLOY_DIR` root определяется из `nginx -T` по upstream `127.0.0.1:9001`.

## Проверка отказоустойчивости

В коде есть fault-injection точки, которые отключены по умолчанию. Использовать их разрешено только на acceptance/staging host:

```bash
WB_UPDATE_ENABLE_FAULT_INJECTION=1 \
WB_UPDATE_FAIL_PHASE=migrations \
TARGET_BRANCH=dev \
./update.sh
```

Поддерживаемые точки: `candidate`, `backup`, `migrations`, `runtime`, `frontend`.

После искусственного сбоя необходимо проверить:

```bash
git rev-parse HEAD
systemctl is-active wb-backend wb-celery wb-celery-beat
curl -fsS http://127.0.0.1:9001/health/ready
ls -la /var/tmp/wb-insight-update/
```

CI запускает `ops/updater_transaction_contract.py`, который закрепляет обязательный порядок сборки, backup, migration, activation и rollback, а также закрытие опасного окна публикации frontend.

## Публичный nginx

Публичный hostname должен:

- перенаправлять HTTP на HTTPS;
- проксировать API same-origin под `/api`;
- отдавать `index.html` с `no-store/no-cache`;
- кешировать hashed `/assets/*` как immutable;
- возвращать настоящий `404` для отсутствующего asset вместо SPA fallback.

Если браузер показывает CORS для `/api/auth/refresh` или MIME `text/html` для `/assets/*.css|js`, сначала исправьте nginx/TLS boundary.

## Диагностика после неуспешного обновления

Проверьте:

```bash
cd /home/projects/wb
git status --short
git rev-parse HEAD
readlink -f backend/venv || true
systemctl --no-pager --full status wb-backend wb-celery wb-celery-beat
journalctl -u wb-backend -n 150 --no-pager
journalctl -u wb-celery -n 150 --no-pager
journalctl -u wb-celery-beat -n 150 --no-pager
ls -lah /var/backups/wb-insight/update/
ls -lah /var/tmp/wb-insight-update/
```

Не выполняйте ручной `alembic downgrade` и не удаляйте update-backup до выяснения причины ошибки.

## Acceptance после deployment

Production-like acceptance по-прежнему требует exact head целевой ветки. Для `dev`:

```bash
TARGET_BRANCH=dev ./update.sh
```

После успешного deployment collector запускается с `--target-branch dev` и проверяет clean tree, exact `origin/dev`, immutable release-venv, systemd services, Celery, Alembic head, nginx, локальную и публичную readiness и соответствие опубликованных frontend assets.
