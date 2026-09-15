# Исторический документ: ранний API response contract

Этот файл сохранён для старых ссылок и **не является канонической API-документацией**. Фактические request/response schemas определяются текущим FastAPI/OpenAPI и backend code.

Актуальные источники:

- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) — группы API и правила совместимости;
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — границы frontend/backend;
- FastAPI/OpenAPI текущего deployed commit — точные schemas;
- backend tests — regression contract для критичных routes.

Существующий проект исторически использует `status/data/error` envelopes в ряде API, но новые изменения должны проверяться по фактической schema, а не по старому универсальному шаблону из этого файла.
