import httpx
import asyncio
import time

from integrations.wildberries import endpoints

from core.logger import setup_logger
from models.tokens_model import APIToken
from utils.token_crypto import decrypt_token

logger = setup_logger(__name__, 'wb_client.log')

class UserRateLimiter:
    """
    Ограничитель запросов на уровне пользователя (токена).
    Гарантирует, что между запросами одного юзера пройдет минимум `min_interval` секунд.
    Потокобезопасен в рамках asyncio event loop.
    """
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def wait(self, key: str):
        lock = self._get_lock(key)

        # Используем lock, чтобы проверка времени и обновление были атомарными
        async with lock:
            now = time.time()
            last_time = self._last_request.get(key, 0.0)

            elapsed = now - last_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                logger.debug(f"Rate limit throttling for {key}: waiting {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

            # Обновляем время выполнения запроса сразу перед тем, как выйти из локка
            self._last_request[key] = time.time()


# Глобальный экземпляр лимитера для всех клиентов
_rate_limiter = UserRateLimiter(min_interval=60.0)

class WBClient:   
    def __init__(self, token: APIToken) -> None:
        self._encrypted_token = token.encrypted_token
        self._user_id = str(token.user_id)
        self.client = httpx.AsyncClient(timeout=60)
        # Ключ для лимитера — зашифрованный токен (уникален для каждого пользователя)
        self._rate_limit_key = self._encrypted_token

    def _get_token(self) -> str:
        """Расшифровывает токен только на момент использования."""
        return decrypt_token(self._encrypted_token, self._user_id)

    async def _request(self, method: str, url: str, params: dict | None = None, json_data: dict | None = None):
        # 1. Ждем, пока пройдет необходимое время с последнего запроса этого юзера
        # Это предотвращает отправку нескольких запросов одновременно от одного пользователя
        await _rate_limiter.wait(self._rate_limit_key)

        # 2. Расшифровываем токен только на время запроса
        token = self._get_token()
        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers={"Authorization": token},
                params=params,
                json=json_data
            )
        finally:
            # Сразу удаляем токен из памяти после использования
            del token

        if response.status_code == 429:
            logger.warning("Received 429 Rate Limit despite throttling. Consider increasing min_interval or implementing retry with backoff.")
            raise RuntimeError("rate_limit")

        if response.status_code == 204:
            # Нет данных за период - возвращаем пустой список
            logger.info("No content (204) - empty report")
            return []

        if response.status_code in [401, 403]:
            logger.error(f"WB Authorization error: {response.status_code} {response.text}")
            raise Exception(f"Unauthorized: WB error {response.status_code}. Токен недействителен или истек срок действия.")

        if response.status_code != 200:
            logger.error(f"WB error: {response.status_code} {response.text}")
            raise Exception(f"WB error: {response.status_code} {response.text}")

        try:
            return response.json()
        except Exception:
            logger.error(f"Invalid JSON response: {response.text}")
            raise
        
    # === endpoints ===

    async def get_realization(self, payload: dict = {}):
        # Новый API требует POST запрос с телом в camelCase
        # Конвертируем snake_case параметры в camelCase для нового API
        request_body = {
            "dateFrom": payload.get("date_from", ""),
            "dateTo": payload.get("date_to", "")
        }

        # fields можно указать если нужны только определенные поля
        if "fields" in payload:
            request_body["fields"] = payload["fields"]

        return await self._request(
            "POST",
            endpoints.REALIZATION_V2,
            json_data=request_body
        )
    
    async def get_stock(self, payload: dict = {}):
        payload = payload or {
            "limit": 250000,
            "offset": 0
        }
        return await self._request(
            "POST",
            endpoints.STOCKS_V2,
            json_data=payload
        )
    
    async def get_products(self, payload: dict = {}):
        return await self._request(
            "POST",
            endpoints.PRODUCTS,
            json_data=payload
        )

    async def get_advert_campaigns(self, payload: dict = {}):
        """
        Получить список рекламных кампаний
        
        API endpoint: GET /api/advert/v2/adverts
        https://dev.wildberries.ru/docs/openapi/promotion/#tag/Kampanii/paths/~1api~1advert~1v2~1adverts/get
        
        Параметры:
        - ids: string - ID кампаний через запятую (макс. 50), например "12345,23456"
        - statuses: string - Статусы кампаний через запятую (-1,4,7,8,9,11)
          -1 — удалена, 4 — готова к запуску, 7 — завершена, 8 — отменена, 9 — активна, 11 — на паузе
        - payment_type: string - Тип оплаты (cpm или cpc), опционально
        
        Возвращает:
        {
          "adverts": [
            {
              "id": 567456457,              # ID кампании (advertId)
              "bid_type": "manual",         # unified | manual
              "nm_settings": [...],         # Настройки товаров
              "settings": {                 # Настройки кампании
                "name": "...",              # Название кампании
                "payment_type": "cpc",      # cpm | cpc
                "placements": {...}         # Места размещения
              },
              "status": 9,                  # -1,4,7,8,9,11
              "timestamps": {...}           # Временные метки
            }
          ]
        }
        """
        return await self._request(
            "GET",
            endpoints.ADVERT_CAMPAIGNS,
            params=payload
        )

    async def get_advert_stats(self, payload: dict = {}):
        """
        Получить полную статистику по рекламным кампаниям
        
        API endpoint: GET /adv/v3/fullstats
        https://dev.wildberries.ru/docs/openapi/promotion/#tag/Statistika/paths/~1adv~1v3~1fullstats/get
        
        Параметры (передаются как query params, НЕ как JSON body!):
        - ids: string (REQUIRED) - ID кампаний через запятую (макс. 50), например "22161678,28449281"
        - beginDate: string (REQUIRED) - Дата начала периода в формате YYYY-MM-DD
        - endDate: string (REQUIRED) - Дата окончания периода в формате YYYY-MM-DD
        
        Возвращает:
        [
          {
            "advertId": 22161678,           # ID кампании
            "views": 1000,                  # Просмотры
            "clicks": 50,                   # Клики
            "ctr": 5.0,                     # CTR (%)
            "cpc": 1.5,                     # CPC (цена за клик, ₽)
            "sum": 75.0,                    # Затраты (₽)
            "atbs": 10,                     # Добавлено в корзину
            "orders": 5,                    # Заказы
            "cr": 10.0,                     # CR (%)
            "shks": 5,                      # Количество штук в заказах
            "sum_price": 15000.0,           # Сумма заказов (₽)
            "days": [                       # Статистика по дням
              {
                "date": "2025-07-06",
                "views": 100,
                "clicks": 5,
                ...
              }
            ],
            "boosterStats": [               # Статистика по средней позиции
              {
                "avgPosition": 75.0
              }
            ]
          }
        ]
        
        Примечание: API требует сначала получить список кампаний через get_advert_campaigns(),
        извлечь их ID и передать в этом методе.
        """
        # API v3 fullstats использует GET запрос с query параметрами, а не POST с JSON
        return await self._request(
            "GET",
            endpoints.ADVERT_STATS,
            params=payload
        )