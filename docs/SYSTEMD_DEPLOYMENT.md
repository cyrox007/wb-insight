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

## Почему нельзя обновлять старый venv «на месте»

`venv` привязан к интерпретатору, которым он создан. Если существующий `backend/venv/bin/python` показывает Python 3.10, установка Python 3.12 в систему не превращает этот venv в 3.12.

Нужно создать новый venv через `python3.12 -m venv ...`, установить зависимости и только после успешной установки переключить systemd на новый environment/путь.

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

В репозитории есть:

```bash
ops/update_systemd.sh
```

По умолчанию он ожидает проект в `/home/projects/wb` и сервисы:

- `wb-backend`;
- `wb-celery`;
- `wb-celery-beat`;
- nginx.

Запуск:

```bash
cd /home/projects/wb
chmod +x ops/update_systemd.sh
./ops/update_systemd.sh
```

При другом пути/health endpoint:

```bash
PROJECT_DIR=/srv/wb-insight \
HEALTH_URL=http://127.0.0.1:9000/health/ready \
./ops/update_systemd.sh
```

Updater:

1. проверяет Python 3.12 и Node до изменения runtime;
2. требует чистый `main`;
3. выполняет `git fetch` + `ff-only` вместо неявного merge;
4. создаёт свежий Python 3.12 venv рядом со старым;
5. полностью устанавливает backend requirements до переключения venv;
6. применяет Alembic migration новым environment;
7. использует `npm ci`, затем `npm run build`;
8. только после успешных install/build переключает `backend/venv`;
9. перезапускает API/worker/beat и reload nginx;
10. проверяет systemd state и `/health/ready`;
11. сохраняет предыдущий venv как `venv.previous.<timestamp>` для диагностики.

## Восстановление после ошибки `numpy==2.4.6` на Python 3.10

Если `git pull` уже прошёл, но dependency install завершился ошибкой до Alembic/frontend/restart, исходники на диске новые, а процессы обычно продолжают выполнять старый загруженный код.

Не перезапускайте сервисы, пока новый Python environment не готов.

Проверьте:

```bash
cd /home/projects/wb
backend/venv/bin/python --version
git rev-parse HEAD
systemctl is-active wb-backend wb-celery wb-celery-beat
```

После установки Python 3.12 создайте новый environment:

```bash
cd /home/projects/wb/backend
python3.12 -m venv venv.next
venv.next/bin/python -m pip install --upgrade pip setuptools wheel
venv.next/bin/python -m pip install -r requirements.txt
venv.next/bin/python -c 'import numpy,pandas; print(numpy.__version__, pandas.__version__)'
venv.next/bin/alembic upgrade head
```

Frontend:

```bash
cd /home/projects/wb/frontend
npm ci
npm run build
```

После успешных шагов переключите venv:

```bash
cd /home/projects/wb/backend
mv venv "venv.python310.backup.$(date +%Y%m%d-%H%M%S)"
mv venv.next venv
```

И только затем:

```bash
systemctl restart wb-backend wb-celery wb-celery-beat
systemctl reload nginx
systemctl --no-pager --full status wb-backend wb-celery wb-celery-beat
curl -fsS http://127.0.0.1:9000/health/ready
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

До migration фиксируйте previous commit и делайте backup БД. Обычный rollback — previous known-good application commit/image/venv. Автоматический `alembic downgrade` не является стандартным rollback механизмом.

После migration нельзя без анализа просто сделать `git reset --hard` и считать rollback завершённым: schema могла уже измениться. Используйте `PRODUCTION_DEPLOYMENT.md` и `OPERATIONS.md`.
