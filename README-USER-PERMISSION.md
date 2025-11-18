# Архитектура системы прав
у нас трехуровневая система
```
Пользователи (users) ←→ Роли (roles) ←→ Разрешения (permissions)
     ↓                       ↓                  ↓
   КТО?                 КАКАЯ ДОЛЖНОСТЬ?   ЧТО МОЖЕТ ДЕЛАТЬ?

```
## Как связаны таблицы
```
users              user_roles          role_permissions          permissions
┌─────────┐        ┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ id      │───────→│ user_id     │     │ role             │────→│ id          │
│ email   │        │ role        │     │ permission_id    │     │ name        │
│ ...     │        └─────────────┘     └──────────────────┘     │ description │
└─────────┘                                                     └─────────────┘
```
## Что хранится в таблице permissions
``` python
# Примеры разрешений
permissions = [
    {"name": "user.create", "description": "Создавать пользователей"},
    {"name": "user.delete", "description": "Удалять пользователей"},
    {"name": "report.view", "description": "Просматривать отчеты"},
    {"name": "report.export", "description": "Экспортировать отчеты"},
    {"name": "payment.approve", "description": "Подтверждать платежи"},
    {"name": "system.settings", "description": "Изменять настройки системы"},
    {"name": "support.tickets", "description": "Работать с заявками поддержки"},
]
```
## Как назначаются права
### 1. Создаем разрешения
``` python
# В базе данных
permission1 = Permission(name="user.create", description="Создавать пользователей")
permission2 = Permission(name="report.view", description="Просматривать отчеты")
```
### 2. Связываем роли с разрешениями
``` python
# В role_permissions таблице:
# role="admin" → permission_id=1 (user.create)
# role="admin" → permission_id=2 (report.view) 
# role="manager" → permission_id=2 (report.view)
# role="user" → (нет разрешений)
```
### 3. Назначаем роли пользователям
``` python
# В user_roles таблице:
# user_id=123 → role="admin"
# user_id=456 → role="manager" 
```
## Практические примеры
### Пример 1: Администратор
``` python
# Роли: SUPER_ADMIN
# Разрешения через role_permissions:
# - user.create, user.delete, user.edit
# - report.view, report.export, report.manage
# - payment.approve, payment.manage
# - system.settings, system.backup
# - support.tickets, support.manage
```
### Пример 2: Менеджер отдела
``` python
# Роли: MANAGER
# Разрешения:
# - user.create (только в своем отделе)
# - report.view, report.export
# - payment.approve (до определенной суммы)
```
### Пример 3: Аналитик
``` python
# Роли: ANALYST  
# Разрешения:
# - report.view, report.export
# - data.analyze
```
## Преимущества такого подхода
### ✅ Гибкость на уровне разрешений
``` python
# Можно тонко настраивать что может каждая роль
def can_user_create_in_department(self, department):
    return (self.has_permission("user.create") and 
            self.department == department)
```
### ✅ Легко добавлять новые возможности
``` python 
# Добавили новую фичу "аудиторский лог"
permission = Permission(name="audit.view", description="Просмотр логов")

# Назначаем только нужным ролям
# role_permissions: admin → audit.view, manager → audit.view
```
### ✅ Динамическое управление правами
``` python
# Можно менять права ролей без переписывания кода
# Просто добавляем/убираем записи в role_permissions
```
### ✅ Аудитинг и отчетность
``` python 
# Можно посмотреть:
# - Какие разрешения есть у каждой роли
# - Кто имеет доступ к определенным функциям
# - История изменений прав
```
## Как это использовать в коде
### Методы проверки прав
``` python
class User:
    def has_permission(self, permission_name):
        """Проверить есть ли у пользователя конкретное разрешение"""
        for user_role in self.roles:
            # Проверяем через role_permissions
            if permission_name in user_role.permissions:
                return True
        return False

    def can_create_user(self):
        return self.has_permission("user.create")

    def can_export_reports(self):
        return self.has_permission("report.export")
```
### Декораторы для контроля доступа
``` python
def require_permission(permission_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.has_permission(permission_name):
                raise PermissionDenied("Недостаточно прав")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Использование
@require_permission("user.create")
def create_user():
    # Создание пользователя
    pass
```
### Динамическое меню интерфейса
``` python
# Показываем только то, что пользователь может делать
menu_items = []
if user.has_permission("report.view"):
    menu_items.append("Отчеты")
if user.has_permission("user.manage"):
    menu_items.append("Пользователи")
```
## Реальные сценарии
### Сценарий 1: Разные уровни доступа к отчетам
``` python
# Разрешения:
# - report.view.basic (базовые отчеты)
# - report.view.financial (финансовые)
# - report.view.sensitive (конфиденциальные)

# Роли:
# - MANAGER: report.view.basic, report.view.financial
# - ANALYST: report.view.basic, report.view.sensitive
# - USER: report.view.basic
```
### Сценарий 2: Гранулярный контроль платежей
``` python
# Разрешения:
# - payment.view (видеть платежи)
# - payment.approve.small (до 10,000 руб)
# - payment.approve.medium (до 100,000 руб) 
# - payment.approve.large (любая сумма)

# Роли:
# - MANAGER: payment.view, payment.approve.small
# - ADMIN: payment.view, payment.approve.large
```
## Итог
С таблицей permissions и role_permissions вы получаете:

🎯 Точный контроль - можно настроить кто что может делать до мельчайших деталей
🚀 Гибкость - легко добавлять новые функции и права
📊 Прозрачность - видно какие права у кого есть
🔧 Управляемость - правами можно управлять через админку без программиста
⚡ Масштабируемость - система растет вместе с бизнесом

Это профессиональный enterprise-уровень управления доступом!