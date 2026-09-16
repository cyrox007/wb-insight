# WB Insight — deployment через systemd

Канонический production baseline проекта — Docker Compose, но существующая установка на Ubuntu может продолжать работать через systemd при соблюдении того же runtime contract.

## Обязательные версии

- Python **3.12** для backend/worker/beat;
- Node.js `^20.19.0` или `>=22.12.0` для frontend build;
- PostgreSQL 16 рекомендуется;
- Redis 7 рекомендуется;
- nginx как внешний web/gateway слой;
- текущие зависимости строго из `backend/requirements.txt` и `frontend/package-lock.json`.

Не используйте Python 3.10 для актуальной release line. В частности, `numpy 2.4.x` и `pandas 3.x` требуют Python >=3.11, а проект стандартизирован на Python 3.12.

## Почему нельзя обновлять старый venv «на месте» или переименовывать новый после установки

`venv` привязан к интерпретатору, которым он создан. Если существующий `backend/venv/bin/python` показывает Python 3.10, установка Python 3.12 в систему не превращает этот venv в 3.12.

Кроме того, нельзя создать `venv.next`, установить в него пакеты, а затем переименовать каталог в `venv`: console scripts (`celery`, `uvicorn`, `alembic` и другие) содержат абсолютный путь к интерпретатору в shebang. После переименования systemd может получить `203/EXEC` / `No such file or directory`, даже если сам файл `backend/venv/bin/celery` существует.

Поэтому updater создаёт каждый venv сразу по его финальному неизменяемому пути `backend/venv.releases/<timestamp>` и переключает стабильный путь `backend/venv` через symlink.

## Проверка текущего host

```bash
cd /home/projects/wb
python3.12 --version
node --version
npm --version
backend/venv/bin/python --version || true
git status --short
git rev-parse HEAD
cat VERSION
```

Working tree перед deployment должен быть чистым.

## Канонический updater для существующей systemd-установки

В репозитории есть executable-скрипт:

```bash
ops/update_systemd.sh
```

Executable bit хранится в Git и проверяется CI. Не выполняйте локальный `chmod +x`: изменение mode tracked-файла делает working tree dirty и блокирует clean-tree guard updater-а. Если mode уже был изменён локально, восстановите его через `git restore -- ops/update_systemd.sh`, обновите `main` и только затем запускайте updater.

По умолчанию он ожидает проект в `/home/projects/wb` и сервисы:

- `wb-backend`;
- `wb-celery`;
- `wb-celery-beat`;
- nginx.

Запуск:

```bash
cd /home/projects/wb
./ops/update_systemd.sh
```

Для текущей systemd-установки WB Insight readiness по умолчанию проверяется на `http://127.0.0.1:9001/health/ready`. При другом пути/health endpoint:

```bash
PROJECT_DIR=/srv/wb-insight \
HEALTH_URL=http://127.0.0.1:9001/health/ready \
./ops/update_systemd.sh
```

Updater:

1. проверяет Python 3.12, Node и наличие systemd units до изменения runtime;
2. требует чистый `main`;
3. выполняет `git fetch` + `ff-only` вместо неявного merge;
4. создаёт свежий Python 3.12 venv сразу по финальному пути `backend/venv.releases/<timestamp>`;
5. полностью устанавливает backend requirements и проверяет `celery`, `uvicorn`, `alembic` и импорт моделей до переключения venv;
6. применяет Alembic migration новым environment;
7. использует `npm ci`, затем `npm run build`;
8. только после успешных install/build атомарно переключает стабильный symlink `backend/venv`;
9. перезапускает API/worker/beat и reload nginx;
10. проверяет systemd state и `/health/ready`.

## Восстановление после `203/EXEC` у Celery/Uvicorn

Если старый updater уже создал `venv.next.<timestamp>`, установил туда пакеты, а затем переименовал каталог в `venv`, console scripts могут сохранить старый shebang. Типичный симптом:

```text
Failed to execute /home/projects/wb/backend/venv/bin/celery: No such file or directory
status=203/EXEC
```

Проверка:

```bash
cd /home/projects/wb
ls -l backend/venv/bin/celery
head -n1 backend/venv/bin/celery
ls -ld backend/venv*
```

Не исправляйте shebang вручную через `sed`. Создайте venv сразу по финальному пути и переключите symlink:

```bash
cd /home/projects/wb/backend
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE="/home/projects/wb/backend/venv.releases/$STAMP"
mkdir -p /home/projects/wb/backend/venv.releases
python3.12 -m venv "$RELEASE"
"$RELEASE/bin/python" -m pip install --upgrade pip setuptools wheel
"$RELEASE/bin/python" -m pip install -r requirements.txt
"$RELEASE/bin/celery" --version
PYTHONPATH=. "$RELEASE/bin/python" -c 'import models; print("models import OK")'
"$RELEASE/bin/alembic" upgrade head
```

Если эти проверки успешны:

```bash
cd /home/projects/wb/backend
if [ -L venv ]; then
  ln -s "$RELEASE" .venv-link-new
  mv -Tf .venv-link-new venv
elif [ -e venv ]; then
  mv venv "venv.broken.$(date +%Y%m%d-%H%M%S)"
  ln -s "$RELEASE" venv
else
  ln -s "$RELEASE" venv
fi

systemctl restart wb-backend wb-celery wb-celery-beat
systemctl reload nginx
systemctl --no-pager --full status wb-backend wb-celery wb-celery-beat
curl -fsS http://127.0.0.1:9001/health/ready
```

Если service не стартует, сразу смотрите:

```bash
journalctl -u wb-backend -n 150 --no-pager
journalctl -u wb-celery -n 150 --no-pager
journalctl -u wb-celery-beat -n 150 --no-pager
```

## Установка Python 3.12

Сначала проверьте, предоставляет ли его текущий Ubuntu repository:

```bash
apt update
apt-cache policy python3.12 python3.12-venv
```

Если candidate доступен:

```bash
apt install -y python3.12 python3.12-venv python3.12-dev
```

Если host distribution не предоставляет Python 3.12 штатно, предпочтительный долгосрочный вариант — перейти на container deployment из `compose.production.yml` или обновить host OS до поддерживаемой версии. Добавление стороннего Python package repository является отдельным инфраструктурным решением и не должно выполняться updater-скриптом автоматически.

## Rollback

До migration фиксируйте previous commit и делайте backup БД. Обычный rollback — previous known-good application commit/image/venv. Для symlink-схемы previous release directory остаётся на диске; после анализа можно атомарно переключить `backend/venv` обратно на него и перезапустить сервисы.

После migration нельзя без анализа просто сделать `git reset --hard` и считать rollback завершённым: schema могла уже измениться. Используйте `PRODUCTION_DEPLOYMENT.md` и `OPERATIONS.md`.
