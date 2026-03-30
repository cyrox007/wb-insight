# Миграция на структуру WB API v2

## Обзор изменений

Обновлены схемы данных и эмуляция для соответствия реальному API Wildberries 
(эндпоинт `/content/v2/get/cards/list`).

## Новые схемы (schemas/products.py)

### Основные схемы WB API:

1. **WbCardSchema** - Карточка товара в формате WB API
   - `nmID` - Артикул WB
   - `vendorCode` - Артикул продавца
   - `prices` - Цены в копейках (price, discountedPrice, clubPrice)
   - `sizes` - Варианты товара (размеры/цвета)
   - `photos` - Фотографии
   - `characteristics` - Характеристики
   - `moderationStatus` - Статус модерации

2. **WbPriceSchema** - Цены в копейках
   - Свойства для конвертации в рубли: `price_rub`, `discounted_price_rub`

3. **WbSizeSchema** - Вариант товара
   - `sku`, `barcode`, `size`, `techSize`, `color`, `colorName`

4. **WbPhotoSchema** - Фотография
   - `url`, `isMain`, `order`

5. **WbCharacteristicSchema** - Характеристика
   - `name`, `value`, `unit`

6. **WbCardsListResponseSchema** - Ответ API со списком карточек
   - `cards`, `total`, `limit`, `offset`

7. **ModerationStatusEnum** - Перечисление статусов модерации

### Схемы для остатков:

- **WbStocksItemSchema** - Остаток на складе (WB API формат)
- **WbStocksResponseSchema** - Ответ API по остаткам

## Обновленная эмуляция (services/wb_product_emulation.py)

### Новые функции:

```python
def generate_wb_card(...) -> WbCardSchema:
    """Генерация одной карточки в формате WB API"""
    
async def emulate_wb_cards_sync(...) -> WbCardsListResponseSchema:
    """Эмуляция получения списка карточек из WB API"""
```

### Особенности эмуляции:

- Цены генерируются в **копейках** (как в реальном API)
- Создаются варианты товаров с размерами и цветами
- Генерируются URL фотографий в формате WB
- Добавляются характеристики товара
- Статусы модерации распределяются реалистично

## Пример использования

```python
from services.wb_product_emulation import emulate_wb_cards_sync

# Получение эмулированных данных
response = await emulate_wb_cards_sync(
    session=session,
    user_id=user_id,
    products_count=50
)

# Доступ к данным
for card in response.cards:
    print(f"Товар: {card.name}")
    print(f"Цена: {card.prices.price_rub} руб.")
    print(f"Размеров: {len(card.sizes)}")
    print(f"Фото: {len(card.photos)}")
```

## JSON ответ (пример)

```json
{
  "nmID": 12345678,
  "vendorCode": "ART-1234",
  "name": "Платье женское вечернее Красный",
  "brand": "Модный Бренд",
  "category": "Одежда",
  "prices": {
    "price": 500000,
    "discountedPrice": 350000,
    "clubPrice": 332500
  },
  "discount": 30,
  "sizes": [
    {
      "sku": 4600000000000,
      "barcode": "4600000000000",
      "size": "42",
      "techSize": "42",
      "color": "Красный",
      "colorName": "red"
    }
  ],
  "photos": [
    {
      "url": "https://basket-1.wb.ru/vol100/part1/12345678/images/0.jpg",
      "isMain": true,
      "order": 0
    }
  ],
  "moderationStatus": "approved"
}
```

## Преимущества новой структуры

1. **Соответствие WB API** - Легко перейти на реальные запросы
2. **Типизация** - Полная типизация всех полей
3. **Валидация** - Pydantic валидирует данные при создании
4. **Конвертация цен** - Автоматическая конвертация копеек в рубли
5. **Расширяемость** - Легко добавить новые поля из API

## Следующие шаги

Когда появится токен WB:

1. Создать сервис для реальных запросов к WB API
2. Использовать те же схемы для парсинга ответов
3. Сохранять данные в БД через существующие модели
4. Контроллеры останутся без изменений

