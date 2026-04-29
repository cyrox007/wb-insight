#BASE_URL = "https://statistics-api.wildberries.ru"

# Детализации к отчётам реализации за период 
REALIZATION: str = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
REALIZATION_V2: str = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed" # Требует: Методы доступны по Персональному или Сервисному токену для категории Финансы.

# Остатки по складам
STOCKS: str = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
STOCKS_V2: str = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses" # Метод доступен по типам токенов: Персональный, Сервисный

PRODUCTS: str = "https://content-api.wildberries.ru/content/v2/get/cards/list" # Метод доступен по токену с категорией Контент или Продвижение
#SALES = "/api/v1/supplier/sales"