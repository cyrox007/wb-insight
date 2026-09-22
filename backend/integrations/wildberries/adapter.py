from sqlalchemy.ext.asyncio import AsyncSession

from integrations.marketplace import MarketplaceAdapter
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken, Marketplace
from sync.process_advertising import process_advertising
from sync.process_finance_summary import process_finance_summary
from sync.process_operational import process_orders, process_sales
from sync.process_paid_storage import process_paid_storage
from sync.process_prices import process_prices
from sync.process_products import process_products
from sync.process_realization import process_realization
from sync.process_sales_funnel import process_sales_funnel
from sync.process_stock import process_stock


class WildberriesAdapter(MarketplaceAdapter):
    marketplace = Marketplace.WILDBERRIES

    handlers = {
        "realization": process_realization,
        "finance_summary": process_finance_summary,
        "stocks": process_stock,
        "products": process_products,
        "prices": process_prices,
        "orders": process_orders,
        "sales": process_sales,
        "advertising": process_advertising,
        "sales_funnel": process_sales_funnel,
        "paid_storage": process_paid_storage,
    }

    async def sync_entity(
        self,
        session: AsyncSession,
        job: SyncJob,
        token: APIToken,
    ) -> None:
        handler = self.handlers.get(job.entity)
        if handler is None:
            raise ValueError(
                f"Неизвестная сущность {self.marketplace.value}: {job.entity}"
            )

        await handler(session, job, token)
