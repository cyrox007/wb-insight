from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from sync.process_advertising import process_advertising
from sync.process_operational import process_orders, process_sales
from sync.process_paid_storage import process_paid_storage
from sync.process_products import process_products
from sync.process_realization import process_realization
from sync.process_sales_funnel import process_sales_funnel
from sync.process_stock import process_stock


HANDLERS = {
    "realization": process_realization,
    "stocks": process_stock,
    "products": process_products,
    "orders": process_orders,
    "sales": process_sales,
    "advertising": process_advertising,
    "sales_funnel": process_sales_funnel,
    "paid_storage": process_paid_storage,
}


async def call_wb_api(session: AsyncSession, job: SyncJob, token: APIToken):
    handler = HANDLERS.get(job.entity)

    if not handler:
        raise ValueError(f"Unknown entity: {job.entity}")

    await handler(session, job, token)
