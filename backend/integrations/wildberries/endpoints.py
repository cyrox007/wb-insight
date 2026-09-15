# Legacy finance endpoint kept only as a historical reference. WB disabled it
# after 2026-07-15; production ingestion uses finance-api endpoints below.
REALIZATION: str = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
REALIZATION_V2: str = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed"
FINANCE_REPORTS_LIST: str = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/list"
FINANCE_BALANCE: str = "https://finance-api.wildberries.ru/api/v1/account/balance"

# Остатки по складам
STOCKS: str = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
STOCKS_V2: str = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"

PRODUCTS: str = "https://content-api.wildberries.ru/content/v2/get/cards/list"

# Текущие цены и скидки. Read-only endpoint; изменение цен намеренно не
# используется этим сервисом из-за отдельного upload/quarantine workflow WB.
PRICES_LIST: str = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"

# Реклама - Advert API
ADVERT_CAMPAIGNS: str = "https://advert-api.wildberries.ru/api/advert/v2/adverts"
ADVERT_STATS: str = "https://advert-api.wildberries.ru/adv/v3/fullstats"
