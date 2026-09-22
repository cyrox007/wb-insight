# Устаревший финансовый маршрут сохранён только как историческая ссылка.
# Wildberries отключил его после 15 июля 2026 года; загрузка использует finance-api ниже.
REALIZATION: str = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
REALIZATION_V2: str = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed"
FINANCE_REPORTS_LIST: str = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/list"
FINANCE_BALANCE: str = "https://finance-api.wildberries.ru/api/v1/account/balance"

# Остатки по складам
STOCKS: str = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
STOCKS_V2: str = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"

PRODUCTS: str = "https://content-api.wildberries.ru/content/v2/get/cards/list"

# Текущие цены и скидки. Маршрут используется только для чтения; изменение цен
# намеренно не выполняется этим сервисом из-за отдельного процесса загрузки
# и карантина изменений Wildberries.
PRICES_LIST: str = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"

# Реклама — API продвижения Wildberries
ADVERT_CAMPAIGNS: str = "https://advert-api.wildberries.ru/api/advert/v2/adverts"
ADVERT_STATS: str = "https://advert-api.wildberries.ru/adv/v3/fullstats"
