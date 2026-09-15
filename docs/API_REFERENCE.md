# WB Insight — обзор API

Каноническое machine-readable описание HTTP API формируется FastAPI/OpenAPI. Этот документ показывает назначение основных групп маршрутов.

## Группы маршрутов

- `/auth` — регистрация и вход;
- session endpoints — refresh/logout;
- `/legal` — публичные документы и требования согласий;
- `/dashboard` — пользовательская аналитика и настройки продавца;
- `/billing` — жизненный цикл оплаты и подписки;
- `/control-panel` — административные функции;
- `/health` — liveness/readiness.

Аналитический API покрывает Overview, Unit Economy, Finance/Reconciliation, Inventory, Prices, Ads, profile/connections, себестоимость и расходы.

## Общие правила

- protected routes проверяют авторизацию и account scope на backend;
- даты dashboard filters передаются в согласованном формате `YYYY-MM-DD`;
- timestamps должны иметь однозначную timezone semantics;
- ошибки внешних систем преобразуются в безопасный внутренний contract;
- операции, способные создать дубликат бизнес-сущности, проектируются с idempotent semantics;
- изменение существующего response contract требует проверки frontend consumers и regression tests.

## Development

При включённой стандартной FastAPI документации используйте OpenAPI/Swagger приложения для точных request/response schemas текущего commit. Код и generated schema имеют приоритет над устаревшими примерами.

## Связанные документы

- `ARCHITECTURE.md` — границы frontend/backend и потоки данных;
- `DATA_AND_METRICS.md` — смысл аналитических показателей;
- `WB_ACCESS_TOKEN_REQUIREMENTS.md` — интеграция Wildberries;
- `SBER_ACQUIRING.md` — acquiring;
- `LEGAL_CONSENT.md` — legal consent contract.
