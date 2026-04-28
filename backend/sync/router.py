from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from sync.process_realization import process_realization
from sync.process_stock import process_stock
#from sync.process_orders import process_orders
#from sync.process_sales import process_sales

HANDLERS = {
    "realization": process_realization,
    "stocks": process_stock,
#    "sales": process_sales,
#    "orders": process_orders,
}

async def call_wb_api(session: AsyncSession, job: SyncJob, token: APIToken):
    handler = HANDLERS.get(job.entity)

    if not handler:
        raise ValueError(f"Unknown entity: {job.entity}")

    await handler(session, job, token)