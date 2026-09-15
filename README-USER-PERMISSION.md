# Исторический документ: ранняя модель ролей и разрешений

Этот файл сохранён для совместимости со старыми ссылками. Он описывает раннюю концепцию permissions и не должен использоваться как доказательство текущего RBAC contract.

Актуальные источники:

- [`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md) — роли и административные сценарии;
- [`docs/SECURITY.md`](docs/SECURITY.md) — server-side authorization principles;
- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) — protected API groups;
- текущие backend role/permission models и handlers — фактическое enforcement.

Ключевой инвариант: доступ к admin/account данным проверяется backend-ом; frontend navigation и скрытие элементов не являются механизмом авторизации.
