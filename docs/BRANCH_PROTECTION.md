# WB Insight — защита веток `dev` и `main`

Дата актуализации: **15 октября 2026 года**.

Документ описывает технический контракт защиты основных веток. До фактического успешного применения и проверки правил ветки нельзя считать защищёнными.

## Почему это обязательно

Аудит от 5 октября 2026 года показал `protected=false` для `dev` и `main`. Зелёный CI сам по себе не запрещает прямую запись, force-push или обход pull request.

В репозитории предусмотрены два уровня защиты:

1. workflow `.github/workflows/branch-policy.yml` всегда запускается для pull request в `dev`/`main` и проверяет допустимое направление слияния;
2. `ops/apply_branch_protection.py` применяет серверные правила GitHub Branch Protection и затем считывает их обратно для проверки.

## Контракт `dev`

Для `dev` требуется:

- изменение только через pull request;
- минимум одно одобрение;
- сброс устаревших одобрений после нового push;
- обязательный check `branch-policy` на актуальном head;
- применение правил к администраторам;
- запрет force-push;
- запрет удаления ветки;
- обязательное разрешение review-обсуждений.

Рабочие feature/fix/chore ветки направляются в `dev`.

## Контракт `main`

`main` принимает только повышение из `dev`. Workflow `branch-policy` отклоняет pull request в `main` из любой другой ветки.

Кроме общих ограничений `main` требует набор release-check contexts:

- `branch-policy`;
- `build` — Frontend build;
- `security-tests` — Backend security;
- `alembic-upgrade` — Database migrations;
- `backup-restore`, `docker-build`, `acceptance-tools`, `version` — Release integrity;
- `validate` — Systemd updater;
- `smoke-contract` — Release smoke contract.

Release PR обязан менять `VERSION`; `VERSION` входит в path contract основных release workflow, поэтому все шесть workflow запускаются для повышения версии в `main`.

## Применение

Нужен отдельный GitHub token владельца/администратора репозитория с правом **Administration: write**. Token нельзя сохранять в репозитории, shell history, документации или CI-artifacts.

Рекомендуемый интерактивный запуск:

```bash
read -rsp 'GitHub admin token: ' GH_ADMIN_TOKEN
export GH_ADMIN_TOKEN
printf '\n'
python3 ops/apply_branch_protection.py --apply
unset GH_ADMIN_TOKEN
```

Скрипт после `PUT` автоматически выполняет `GET` и завершится ошибкой, если фактическая политика отличается от ожидаемой.

Для отдельной проверки уже применённых правил:

```bash
read -rsp 'GitHub admin token: ' GH_ADMIN_TOKEN
export GH_ADMIN_TOKEN
printf '\n'
python3 ops/apply_branch_protection.py --verify
unset GH_ADMIN_TOKEN
```

Можно указать другой репозиторий:

```bash
python3 ops/apply_branch_protection.py --repository owner/repository --verify
```

## Безопасность

- token читается только из `GH_ADMIN_TOKEN` (fallback — `GITHUB_TOKEN`);
- значение token никогда не печатается;
- ошибки GitHub API нормализуются и не выводят response body;
- секрет не сохраняется в файлы;
- self-test `ops/acceptance/branch_protection_selftest.py` работает без сети и без token.

## Что проверять после применения

После успешной команды нужно дополнительно убедиться через GitHub UI/API, что:

- `dev` и `main` отображаются как protected;
- прямой push отклоняется;
- force-push и удаление недоступны;
- pull request в `dev` требует `branch-policy`;
- pull request `dev -> main` требует весь release-набор;
- pull request в `main` не из `dev` падает на `branch-policy`.

Фактическое применение правил является административным действием GitHub и не может быть заменено наличием этого скрипта в репозитории.
