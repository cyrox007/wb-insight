import httpx

from integrations.wildberries import endpoints

from core.logger import setup_logger
from models.tokens_model import APIToken
from utils.token_crypto import decrypt_token

logger = setup_logger(__name__, 'wb_client.log')

class WBClient:   
    def __init__(self, token: APIToken) -> None:
        self.token = decrypt_token(token.encrypted_token)
        self.client = httpx.AsyncClient(timeout=60)


    async def _request(self, method: str, url: str, params: dict | None = None, json_data: dict | None = None):
        response = await self.client.request(
            method=method,
            url=url,
            headers={"Authorization": self.token},
            params=params,
            json=json_data
        )

        if response.status_code == 429:
            logger.error("rate_limit")
            raise RuntimeError("rate_limit")
        
        if response.status_code == 204:
            # Нет данных за период - возвращаем пустой список
            logger.info("No content (204) - empty report")
            return []

        if response.status_code != 200:
            logger.error(f"WB error: {response.status_code} {response.text}")
            raise Exception(f"WB error: {response.status_code} {response.text}")
        
        return response.json()
        
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
        return await self._request(
            "GET",
            endpoints.STOCKS,
            params=payload
        )
    
    async def get_products(self, payload: dict = {}):
        return await self._request(
            "POST",
            endpoints.PRODUCTS,
            params=payload
        )