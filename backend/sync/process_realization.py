from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_finance_ingest_service import save_realization


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_realization(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[РЕАЛИЗАЦИЯ] запуск идентификатор_токена=%s", token.id)

    request_payload: dict[str, Any] = dict(job.payload or {})
    request_payload.setdefault("limit", 100000)
    request_payload.setdefault("rrdId", 0)
    total_loaded = 0
    page_number = 0

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={"checkpoint": request_payload},
    )

    try:
        async with WBClient(token) as client:
            while True:
                page = await client.get_realization(request_payload)
                if page == []:
                    await trace_sync_stage(
                        job=job,
                        token=token,
                        step="source_exhausted",
                        status="success",
                        output_data={"pages": page_number, "rows": total_loaded},
                    )
                    break
                if not isinstance(page, list):
                    raise WBAPIError(
                        "Wildberries вернул отчёт реализации в неожиданном формате",
                        endpoint="finance.sales_report_detailed",
                    )
                if not page:
                    break

                page_number += 1
                last_rrd_id = page[-1].get("rrdId")
                if not isinstance(last_rrd_id, int) or last_rrd_id <= 0:
                    raise WBAPIError(
                        "В отчёте реализации Wildberries отсутствует корректный rrdId продолжения",
                        endpoint="finance.sales_report_detailed",
                    )

                previous_rrd_id = int(request_payload.get("rrdId") or 0)
                if last_rrd_id <= previous_rrd_id:
                    raise WBAPIError(
                        "Курсор отчёта реализации Wildberries не продвинулся вперёд",
                        endpoint="finance.sales_report_detailed",
                    )

                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="source_page_validated",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows": len(page),
                        "previous_rrd_id": previous_rrd_id,
                        "last_rrd_id": last_rrd_id,
                    },
                )
                await save_realization(session, job.user_id, token.id, page)
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="rows_persisted",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows_submitted": len(page),
                        "conflict_policy": "duplicate_rrd_id_ignored",
                    },
                )

                request_payload["rrdId"] = last_rrd_id
                await persist_job_checkpoint(session, job, request_payload)
                total_loaded += len(page)

        logger.info(
            "[РЕАЛИЗАЦИЯ] завершено идентификатор_токена=%s строк=%s",
            token.id,
            total_loaded,
        )
    except Exception as exc:
        logger.warning(
            "[РЕАЛИЗАЦИЯ] ошибка идентификатор_токена=%s тип_ошибки=%s",
            token.id,
            type(exc).__name__,
        )
        raise