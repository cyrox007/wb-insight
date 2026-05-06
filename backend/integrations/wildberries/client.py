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