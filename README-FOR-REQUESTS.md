# 📦 Общая структура ответа (универсальный шаблон)

```json
{
  "status": "success" | "error",
  "data": { ... },        // только при status == "success"
  "error": {              // только при status == "error"
    "code": "string",
    "message": "string",
    "details": { ... }    // опционально: поля, причины, подсказки
  },
  "meta": {               // опционально: пагинация, время генерации и т.п.
    "timestamp": "2025-10-29T12:00:00Z",
    "request_id": "uuid4"
  }
}
```

---

## ✅ Пример успешного ответа

**Запрос**: `GET /api/v1/dashboard?account_id=abc&period=7`

**Ответ**:
```json
{
  "status": "success",
  "data": {
    "period": {
      "start": "2025-10-22",
      "end": "2025-10-28"
    },
    "kpi": {
      "revenue": 1250000.00,
      "profit": 312500.00,
      "margin": 25.0,
      "roas": 3.2,
      "orders_count": 1842,
      "conversion_rate": 4.7
    },
    "expenses": {
      "commission": 187500.00,
      "logistics": 93750.00,
      "advertising": 97656.25,
      "storage": 12500.00,
      "tax": 75000.00
    }
  },
  "meta": {
    "timestamp": "2025-10-29T12:00:00Z",
    "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
  }
}
```

---

## ❌ Пример ошибки

**Запрос**: `GET /api/v1/dashboard?account_id=xyz` (аккаунт не привязан)

**Ответ**:
```json
{
  "status": "error",
  "error": {
    "code": "WB_ACCOUNT_NOT_FOUND",
    "message": "WB-аккаунт не найден или не принадлежит вам",
    "details": {
      "account_id": "xyz"
    }
  },
  "meta": {
    "timestamp": "2025-10-29T12:00:00Z",
    "request_id": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv"
  }
}
```

---

## 📚 Стандартные коды ошибок (для документации)

| Код | Сценарий |
|-----|--------|
| `AUTH_REQUIRED` | Токен отсутствует или недействителен |
| `FORBIDDEN` | Нет доступа к ресурсу (например, чужой WB-аккаунт) |
| `VALIDATION_ERROR` | Ошибки валидации входных данных |
| `SUBSCRIPTION_EXPIRED` | Подписка истекла — доступ к данным закрыт |
| `WB_API_ERROR` | Ошибка при запросе к Wildberries API |
| `WB_ACCOUNT_NOT_FOUND` | WB-аккаунт не найден в системе |
| `RATE_LIMIT_EXCEEDED` | Превышен лимит запросов (редко — на клиенте) |

---

## 🧩 Примеры структур `data` по ключевым эндпоинтам

### 1. `/dashboard` — сводка
```ts
{
  kpi: {
    revenue: number,
    profit: number,
    margin: number,      // %
    roas: number,
    orders_count: number,
    conversion_rate: number // %
  },
  expenses: {
    commission: number,
    logistics: number,
    advertising: number,
    storage: number,
    tax: number
  }
}
```

### 2. `/products` — список товаров (Unit-экономика)
```ts
{
  items: [
    {
      nm_id: number,
      name: string,
      image_url: string,
      sales: number,
      revenue: number,
      profit: number,
      margin: number,
      cost_price: number,   // себестоимость (введена пользователем!)
      advertising_cost: number,
      roas: number,
      stock_days_left: number,
      abc_category: "A" | "B" | "C"
    }
  ]
}
```

### 3. `/recommendations` — рекомендации ИИ
```ts
{
  items: [
    {
      id: string,
      type: "low_stock" | "low_roas" | "high_margin" | "seasonal_opportunity",
      message: string,
      severity: "info" | "warning" | "critical",
      action_url: string, // ссылка на товар или настройки рекламы
      forecast_impact: number // ожидаемый прирост прибыли, ₽
    }
  ]
}
```

### 4. `/ai/chat` — запрос к AI-аналитику
```ts
{
  query: string,          // "Почему упал ROAS по артикулу 1234567?"
  answer: string,         // "ROAS упал на 40% из-за снижения CTR..."
  sources: [
    { type: "ad_stats", period: "2025-10-20/2025-10-27" },
    { type: "product_card", nm_id: 1234567 }
  ]
}
```

---

## 🔐 Безопасность и совместимость

- Все числа — **в рублях с 2 знаками после запятой** (`1234.56`)
- Все даты — **в ISO 8601 UTC** (`2025-10-29T12:00:00Z`)
- Все ID — **UUID4** (для внутренних сущностей) или **числа** (для nm_id)
- Никаких `null` — если поле не заполнено, его **нет в ответе** или значение по умолчанию (`0`, `""`)

