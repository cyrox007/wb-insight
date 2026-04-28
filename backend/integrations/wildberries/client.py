import httpx

from integrations.wildberries import endpoints

from core.logger import setup_logger
from models.tokens_model import APIToken
from utils.token_crypto import decrypt_token

logger = setup_logger(__name__, 'wb_client.log')

class WBClient:   
    def __init__(self, token: APIToken) -> None:
        self.token = token


    async def _request(self, method: str, url: str, params: dict | None = None):
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(
                method=method,
                url=url,
                headers={"Authorization": decrypt_token(self.token.encrypted_token)},
                params=params
            )

            if response.status_code == 429:
                logger.error("rate_limit")
                raise RuntimeError("rate_limit")

            if response.status_code != 200:
                logger.error(f"WB error: {response.status_code} {response.text}")
                raise Exception(f"WB error: {response.status_code} {response.text}")
            
            return response.json()
        
    # === endpoints ===

    async def get_realization(self, payload: dict = {}):
        return await self._request(
            "POST", 
            endpoints.REALIZATION, 
            params=payload
        )