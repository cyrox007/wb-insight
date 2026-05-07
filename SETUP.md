# 📋 Настройка проекта WB Insight

Этот документ содержит полные требования к базе данных, переменным окружения и SQL-скрипт инициализации.

---

## 🔐 1. Файл конфигурации `.env`

Создайте файл `.env` в корне backend-приложения (`/workspace/backend/.env`) на основе следующего шаблона:

```bash
# =============================================================================
# ОБЩИЕ НАСТРОЙКИ
# =============================================================================
DEBUG=False
SERVER_HTTP_PROTOCOL=http://
SERVER_ADDR=localhost
SERVER_PORT=9000
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# =============================================================================
# БАЗА ДАННЫХ (PostgreSQL)
# =============================================================================
DB_HOST=localhost
DB_PORT=5432
DB_NAME=wb_insight
DB_USER=postgres
DB_PASSWORD=your_secure_password_here

# =============================================================================
# БЕЗОПАСНОСТЬ И ШИФРОВАНИЕ
# =============================================================================
# Ключ шифрования для токенов Wildberries (AES-256, 32 байта в base64)
# Генерация: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
API_TOKEN_ENCRYPTION_KEY=your-32-byte-encryption-key-here

# JWT Secret Key для генерации токенов доступа
# Генерация: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-jwt-secret-key-here

# =============================================================================
# REDIS (брокер сообщений для Celery и кэширование)
# =============================================================================
REDIS_URL=redis://localhost:6379/0

# =============================================================================
# WILDBERRIES API (базовые настройки)
# =============================================================================
# Эти значения задаются в коде, но могут быть переопределены
# WB_API_BASE_URL=https://statistics-api.wildberries.ru
# WB_ADVERT_API_BASE_URL=https://advert-api.wildberries.ru

# =============================================================================
# CELERY (фоновые задачи)
# =============================================================================
# Использует REDIS_URL по умолчанию
# CELERY_BROKER_URL=redis://localhost:6379/0
# CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 🔑 Генерация ключей безопасности

```bash
# Генерация ключа шифрования для токенов WB
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Генерация JWT секретного ключа
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🗄️ 2. Требования к базе данных

### Версия PostgreSQL
- **Минимальная версия**: PostgreSQL 13+
- **Рекомендуемая версия**: PostgreSQL 15+

### Расширения (опционально)
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Для полнотекстового поиска
```

### Кодировка
- **Кодировка**: UTF8
- **Collation**: ru_RU.UTF-8 (рекомендуется для русской локализации)

---

## 📜 3. SQL-скрипт инициализации базы данных

Полный скрипт создания всех таблиц:

```sql
-- =============================================================================
-- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ WB INSIGHT
-- =============================================================================

-- Создаём базу данных (если не существует)
-- CREATE DATABASE wb_insight 
--     WITH ENCODING 'UTF8' 
--     LC_COLLATE='ru_RU.UTF-8' 
--     LC_CTYPE='ru_RU.UTF-8' 
--     TEMPLATE=template0;

-- Подключаемся к базе данных
-- \c wb_insight;

-- Включаем расширение для UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ (users)
-- =============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(254) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('individual', 'self_employed', 'legal_entity')),
    inn VARCHAR(12),
    kpp VARCHAR(9),
    legal_address TEXT,
    tax_rate FLOAT DEFAULT 0.2,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Europe/Moscow',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_staff BOOLEAN NOT NULL DEFAULT FALSE,
    staff_id VARCHAR(50) UNIQUE,
    department VARCHAR(100),
    position VARCHAR(100)
);

-- Индексы для users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_entity_type ON users(entity_type);
CREATE INDEX idx_users_active_entity ON users(is_active, entity_type);
CREATE INDEX idx_users_legal_info ON users(entity_type, inn, kpp);
CREATE INDEX idx_users_auth ON users(email, phone, is_active);
CREATE INDEX idx_users_staff ON users(is_staff, department);
CREATE INDEX idx_users_staff_id ON users(staff_id);
CREATE UNIQUE INDEX idx_users_phone_email_unique ON users(phone, email);

-- =============================================================================
-- 2. РОЛИ ПОЛЬЗОВАТЕЛЕЙ (user_roles)
-- =============================================================================
CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('super_admin', 'admin', 'manager', 'support', 'analyst', 'user')),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by UUID
);

CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role);
CREATE UNIQUE INDEX uq_user_role ON user_roles(user_id, role);

-- =============================================================================
-- 3. ТАРИФНЫЕ ПЛАНЫ (tariff_plans)
-- =============================================================================
CREATE TABLE tariff_plans (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_rub NUMERIC(10,2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 4. ЛИМИТЫ ТАРИФОВ (tariff_limits)
-- =============================================================================
CREATE TABLE tariff_limits (
    tariff_id VARCHAR(50) NOT NULL REFERENCES tariff_plans(id) ON DELETE CASCADE,
    limit_type VARCHAR(50) NOT NULL,
    limit_value INTEGER NOT NULL,
    PRIMARY KEY (tariff_id, limit_type)
);

CREATE INDEX idx_tariff_limits_tariff ON tariff_limits(tariff_id);

-- =============================================================================
-- 5. ПОДПИСКИ (subscriptions)
-- =============================================================================
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tariff_id VARCHAR(50) NOT NULL REFERENCES tariff_plans(id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'expired', 'cancelled', 'demo')),
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    yookassa_payment_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_period ON subscriptions(current_period_start, current_period_end);

-- =============================================================================
-- 6. WB-КАБИНЕТЫ (wb_accounts)
-- =============================================================================
CREATE TABLE wb_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wb_seller_id UUID NOT NULL,
    wb_name VARCHAR(255) NOT NULL,
    wb_token_encrypted BYTEA NOT NULL,
    token_categories_mask INTEGER NOT NULL DEFAULT 0,
    is_readonly BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sync_at TIMESTAMPTZ
);

CREATE INDEX idx_wb_accounts_user ON wb_accounts(user_id);
CREATE INDEX idx_wb_accounts_seller ON wb_accounts(wb_seller_id);
CREATE UNIQUE INDEX idx_wb_accounts_unique ON wb_accounts(user_id, wb_seller_id);

-- =============================================================================
-- 7. ПРОФИЛИ СЕБЕСТОИМОСТИ (cost_profiles)
-- =============================================================================
CREATE TABLE cost_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wb_account_id UUID NOT NULL REFERENCES wb_accounts(id) ON DELETE CASCADE,
    nm_id BIGINT,
    cost_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_rate NUMERIC(5,2) DEFAULT 0,
    external_ad_cost NUMERIC(12,2) DEFAULT 0,
    valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cost_profiles_account ON cost_profiles(wb_account_id);
CREATE INDEX idx_cost_profiles_nm ON cost_profiles(nm_id);
CREATE INDEX idx_cost_profiles_valid ON cost_profiles(valid_from);

-- =============================================================================
-- 8. ЕЖЕДНЕВНАЯ АНАЛИТИКА WB (wb_analytics_daily)
-- =============================================================================
CREATE TABLE wb_analytics_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wb_account_id UUID NOT NULL REFERENCES wb_accounts(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    nm_id BIGINT NOT NULL,
    name VARCHAR(500),
    views INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    cart_adds INTEGER NOT NULL DEFAULT 0,
    orders INTEGER NOT NULL DEFAULT 0,
    delivered INTEGER NOT NULL DEFAULT 0,
    returns INTEGER NOT NULL DEFAULT 0,
    revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
    commission NUMERIC(12,2) NOT NULL DEFAULT 0,
    logistics NUMERIC(12,2) NOT NULL DEFAULT 0,
    storage NUMERIC(12,2) NOT NULL DEFAULT 0,
    penalties NUMERIC(12,2) NOT NULL DEFAULT 0,
    ad_cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    stocks INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(wb_account_id, date, nm_id)
);

CREATE INDEX idx_wb_analytics_account_date ON wb_analytics_daily(wb_account_id, date);
CREATE INDEX idx_wb_analytics_nm ON wb_analytics_daily(nm_id);
CREATE INDEX idx_wb_analytics_date ON wb_analytics_daily(date);

-- =============================================================================
-- 9. РЕКОМЕНДАЦИИ ИИ (recommendations)
-- =============================================================================
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wb_account_id UUID NOT NULL REFERENCES wb_accounts(id) ON DELETE CASCADE,
    nm_id BIGINT,
    type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    forecast_impact NUMERIC(14,2) DEFAULT 0,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_recommendations_account ON recommendations(wb_account_id);
CREATE INDEX idx_recommendations_read ON recommendations(is_read);
CREATE INDEX idx_recommendations_expires ON recommendations(expires_at);

-- =============================================================================
-- 10. ИСТОРИЯ AI-ЧАТА (ai_chat_history)
-- =============================================================================
CREATE TABLE ai_chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wb_account_id UUID REFERENCES wb_accounts(id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_chat_user ON ai_chat_history(user_id);
CREATE INDEX idx_ai_chat_account ON ai_chat_history(wb_account_id);
CREATE INDEX idx_ai_chat_created ON ai_chat_history(created_at);

-- =============================================================================
-- 11. ЗАДАЧИ СИНХРОНИЗАЦИИ (sync_jobs)
-- =============================================================================
CREATE TABLE sync_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wb_account_id UUID NOT NULL REFERENCES wb_accounts(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'success', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    data_fetched JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sync_jobs_account ON sync_jobs(wb_account_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);
CREATE INDEX idx_sync_jobs_created ON sync_jobs(created_at);

-- =============================================================================
-- 12. API ТОКЕНЫ (api_tokens)
-- =============================================================================
CREATE TABLE api_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    marketplace VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX idx_api_tokens_hash ON api_tokens(token_hash);

-- =============================================================================
-- 13. ЗАМЕТКИ ПОЛЬЗОВАТЕЛЯ (notes) - НОВЫЙ МОДУЛЬ
-- =============================================================================
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    content_encrypted BYTEA,  -- Зашифрованный текст заметки
    content_type VARCHAR(20) NOT NULL DEFAULT 'text',  -- text, voice, mixed
    
    -- Медиа-вложения (храним метаданные, файлы - в S3/file storage)
    media_attachments JSONB DEFAULT '[]'::jsonb,  -- [{type: 'image'|'audio'|'video', url: '...', size: bytes, duration: sec}]
    
    -- Голосовые сообщения
    voice_messages JSONB DEFAULT '[]'::jsonb,  -- [{url: '...', duration: sec, transcript: '...', created_at: '...'}]
    
    -- Метаданные
    tags VARCHAR(255)[],  -- Массив тегов для поиска
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    is_shared BOOLEAN NOT NULL DEFAULT FALSE,  -- Флаг "поделиться через мессенджер"
    share_link_token VARCHAR(100) UNIQUE,  -- Токен для общего доступа
    share_expires_at TIMESTAMPTZ,  -- Срок действия ссылки
    
    -- Привязка к контексту WB (опционально)
    wb_account_id UUID REFERENCES wb_accounts(id) ON DELETE SET NULL,
    nm_id BIGINT,  -- Артикул WB (если заметка привязана к товару)
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notes_user ON notes(user_id);
CREATE INDEX idx_notes_favorite ON notes(is_favorite);
CREATE INDEX idx_notes_shared ON notes(is_shared);
CREATE INDEX idx_notes_share_token ON notes(share_link_token);
CREATE INDEX idx_notes_tags ON notes USING GIN(tags);
CREATE INDEX idx_notes_wb_context ON notes(wb_account_id, nm_id);
CREATE INDEX idx_notes_created ON notes(created_at);
CREATE INDEX idx_notes_updated ON notes(updated_at);

-- =============================================================================
-- 14. ИСТОРИЯ ПОДЕЛЕННЫХ ЗАМЕТОК (note_share_log)
-- =============================================================================
CREATE TABLE note_share_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    shared_via VARCHAR(50) NOT NULL,  -- telegram, whatsapp, email, link
    recipient_identifier VARCHAR(255),  -- ID получателя или email/phone
    shared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accessed_at TIMESTAMPTZ,
    access_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_note_share_log_note ON note_share_log(note_id);
CREATE INDEX idx_note_share_log_shared ON note_share_log(shared_at);

-- =============================================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ: ТАРИФНЫЕ ПЛАНЫ
-- =============================================================================
INSERT INTO tariff_plans (id, name, description, price_rub, is_active) VALUES
('demo', 'Демо', '7 дней бесплатно, без карты', 0.00, TRUE),
('starter', 'Старт (для ИП)', '1 магазин, 1000 артикулов, обновление 4×/день', 2990.00, TRUE),
('pro', 'Про', '3 магазина, 10000 артикулов, обновление ежечасно, 200 ИИ-запросов', 6990.00, TRUE),
('enterprise', 'Бизнес', 'Безлимит магазинов, API-доступ, персональный менеджер', 0.00, TRUE);

-- ЛИМИТЫ ДЛЯ ТАРИФА DEMO
INSERT INTO tariff_limits (tariff_id, limit_type, limit_value) VALUES
('demo', 'wb_accounts', 1),
('demo', 'nm_ids', 100),
('demo', 'sync_frequency_hours', 24),
('demo', 'ai_queries_per_month', 5),
('demo', 'retention_days', 7);

-- ЛИМИТЫ ДЛЯ ТАРИФА STARTER
INSERT INTO tariff_limits (tariff_id, limit_type, limit_value) VALUES
('starter', 'wb_accounts', 1),
('starter', 'nm_ids', 1000),
('starter', 'sync_frequency_hours', 6),
('starter', 'ai_queries_per_month', 20),
('starter', 'retention_days', 30);

-- ЛИМИТЫ ДЛЯ ТАРИФА PRO
INSERT INTO tariff_limits (tariff_id, limit_type, limit_value) VALUES
('pro', 'wb_accounts', 3),
('pro', 'nm_ids', 10000),
('pro', 'sync_frequency_hours', 1),
('pro', 'ai_queries_per_month', 200),
('pro', 'retention_days', 90);

-- ЛИМИТЫ ДЛЯ ТАРИФА ENTERPRISE
INSERT INTO tariff_limits (tariff_id, limit_type, limit_value) VALUES
('enterprise', 'wb_accounts', 999),
('enterprise', 'nm_ids', 100000),
('enterprise', 'sync_frequency_hours', 1),
('enterprise', 'ai_queries_per_month', 5000),
('enterprise', 'retention_days', 730);

-- =============================================================================
-- КОНЕЦ СКРИПТА ИНИЦИАЛИЗАЦИИ
-- =============================================================================
```

---

## 📦 4. Модель данных для модуля Notes

### Описание полей таблицы `notes`

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | UUID | Уникальный ID заметки |
| `user_id` | UUID (FK) | Владелец заметки |
| `title` | VARCHAR(500) | Заголовок заметки (nullable) |
| `content_encrypted` | BYTEA | **Зашифрованный** текст заметки (AES-256-GCM) |
| `content_type` | VARCHAR(20) | Тип контента: `text`, `voice`, `mixed` |
| `media_attachments` | JSONB | Массив медиа-вложений: `[{"type": "image\|audio\|video", "url": "...", "size": bytes, "duration": sec}]` |
| `voice_messages` | JSONB | Массив голосовых сообщений: `[{"url": "...", "duration": sec, "transcript": "...", "created_at": "..."}]` |
| `tags` | VARCHAR[] | Массив тегов для быстрого поиска |
| `is_favorite` | BOOLEAN | Избранное |
| `is_shared` | BOOLEAN | Флаг "поделиться" |
| `share_link_token` | VARCHAR(100) | Уникальный токен для общей ссылки |
| `share_expires_at` | TIMESTAMPTZ | Срок действия ссылки |
| `wb_account_id` | UUID (FK) | Привязка к WB-кабинету (опционально) |
| `nm_id` | BIGINT | Привязка к артикулу WB (опционально) |
| `created_at` | TIMESTAMPTZ | Дата создания |
| `updated_at` | TIMESTAMPTZ | Дата обновления |

### Пример структуры JSONB для медиа-вложений

```json
{
  "media_attachments": [
    {
      "type": "image",
      "url": "https://storage.wbinsight.com/notes/user-id/note-id/image-1.jpg",
      "size": 245678,
      "mime_type": "image/jpeg",
      "uploaded_at": "2025-01-15T10:30:00Z"
    },
    {
      "type": "audio",
      "url": "https://storage.wbinsight.com/notes/user-id/note-id/voice-1.ogg",
      "size": 123456,
      "duration": 45.5,
      "mime_type": "audio/ogg",
      "uploaded_at": "2025-01-15T10:31:00Z"
    }
  ],
  "voice_messages": [
    {
      "url": "https://storage.wbinsight.com/notes/user-id/note-id/voice-2.ogg",
      "duration": 30.2,
      "transcript": "Не забыть заказать товар артикул 1234567",
      "created_at": "2025-01-15T10:32:00Z"
    }
  ]
}
```

---

## 🚀 5. Применение миграций

### Вариант 1: Через Alembic (рекомендуется)

```bash
cd /workspace/backend

# Применить все миграции
alembic upgrade head

# Проверить статус миграций
alembic current
```

### Вариант 2: Прямое выполнение SQL

```bash
# Подключиться к PostgreSQL
psql -h localhost -U postgres -d wb_insight -f init_db.sql
```

---

## ✅ 6. Проверка установки

```bash
# Проверка подключения к БД
python -c "from settings import config; from core.database import Database; import asyncio; asyncio.run(Database.health_check())"

# Проверка наличия таблиц
psql -h localhost -U postgres -d wb_insight -c "\dt"
```

---

## 📝 7. Дополнительные требования

### Файловое хранилище
Для хранения медиа-файлов заметок требуется:
- **S3-совместимое хранилище** (MinIO, AWS S3, Yandex Object Storage)
- Или локальное хранилище в `/workspace/backend/storage/notes/`

### Переменные окружения для файлового хранилища (добавить в `.env`):

```bash
# Хранилище файлов (S3 или локальное)
STORAGE_TYPE=local  # local | s3
STORAGE_PATH=/workspace/backend/storage/notes

# Для S3 (если используется)
S3_ENDPOINT=https://storage.yandexcloud.net
S3_BUCKET=wb-insight-notes
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_REGION=ru-central1
```

---

## 🔒 Безопасность модуля Notes

1. **Шифрование контента**: Текст заметок шифруется перед сохранением в БД
2. **Доступ к медиа**: URL медиа-файлов генерируются с временными подписями
3. **Общий доступ**: Ссылки на заметки имеют срок действия и могут быть отозваны
4. **Аудит**: Все действия по partage записываются в `note_share_log`
