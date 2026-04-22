import httpx

from services.wb_stock_service import save_stocks

WB_API_URL = "https://statistics-api.wildberries.ru"


async def process_stocks(session, job, token: str):
    url = f"{WB_API_URL}/api/v1/supplier/stocks"

    headers = {
        "Authorization": token
    }

    params = job.payload

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers, params=params)

    if response.status_code == 429:
        raise Exception("rate_limit")  # триггер retry

    if response.status_code != 200:
        raise Exception(f"WB error: {response.text}")

    data = response.json()

    await save_stocks(session, job.user_id, job.token_id, data)
