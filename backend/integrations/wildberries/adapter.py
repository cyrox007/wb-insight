import time

from sqlalchemy.ext.asyncio import AsyncSession

from integrations.marketplace import MarketplaceAdapter
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken, Marketplace
from services.sync_operation_trace_service import trace_sync_stage
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
            await trace_sync_stage(
                job=job,
                token=token,
                step="handler_not_found",
                status="failed",
                severity="error",
                error_code="SYNC_HANDLER_NOT_FOUND",
                output_data={"available_entities": sorted(self.handlers)},
            )
            raise ValueError(
                f"Неизвестная сущность {self.marketplace.value}: {job.entity}"
            )

        await trace_sync_stage(
            job=job,
            token=token,
            step="handler_selected",
            status="success",
            output_data={"handler": handler.__name__},
        )
        started = time.perf_counter()
        try:
            await handler(session, job, token)
        except Exception as exc:
            await trace_sync_stage(
                job=job,
                token=token,
                step="handler_failed",
                status="failed",
                severity="error",
                error_code=type(exc).__name__,
                message=f"Обработчик синхронизации '{job.entity}' завершился ошибкой",
                metrics={
                    "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
                },
            )
            raise

        await trace_sync_stage(
            job=job,
            token=token,
            step="handler_completed",
            status="success",
            metrics={
                "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
            },
        )