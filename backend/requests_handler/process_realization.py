import httpx

from services.wb_report_service import save_realization


async def process_realization(session, job, token: str):
    url = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            url,
            headers={"Authorization": token},
            params=job.payload
        )

    if response.status_code == 429:
        raise Exception("Rate limit")

    if response.status_code != 200:
        raise Exception(response.text)

    data = response.json()

    await save_realization(session, job.user_id, data)