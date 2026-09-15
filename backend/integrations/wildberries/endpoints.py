#BASE_URL = "https://statistics-api.wildberries.ru"

# Детализации к отчётам реализации за период 
REALIZATION: str = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
REALIZATION_V2: str = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed" # Требует: Методы доступны по Персональному или Сервисному токену для категории Финансы.

# Остатки по складам
STOCKS: str = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
STOCKS_V2: str = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses" # Метод доступен по типам токенов: Персональный, Сервисный для категории Аналитика

PRODUCTS: str = "https://content-api.wildberries.ru/content/v2/get/cards/list" # Метод доступен по токену с категорией Контент или Продвижение

# Текущие цены и скидки. Read-only endpoint; изменение цен намеренно не
# используется этим сервисом из-за отдельного upload/quarantine workflow WB.
PRICES_LIST: str = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"

#SALES = "/api/v1/supplier/sales"

# Реклама - Advert API (новая документация 2025)
# https://dev.wildberries.ru/docs/openapi/promotion/

# Список кампаний - GET /api/advert/v2/adverts
# Требует параметры: ids, statuses, payment_type (опционально)
# Отдает массив campaigns с полями: id, bid_type, nm_settings, settings, status, timestamps
ADVERT_CAMPAIGNS: str = "https://advert-api.wildberries.ru/api/advert/v2/adverts"

# Статистика по кампаниям - GET /adv/v3/fullstats
# https://dev.wildberries.ru/docs/openapi/promotion/#tag/Statistika/paths/~1adv~1v3~1fullstats/get
# Требует параметры: ids (список ID кампаний, макс. 50), beginDate, endDate
# Отдает массив stats с полями: advertId, days[], views, clicks, ctr, cpc, sum, atbs, orders, cr, shks, sum_price, boosterStats
ADVERT_STATS: str = "https://advert-api.wildberries.ru/adv/v3/fullstats"