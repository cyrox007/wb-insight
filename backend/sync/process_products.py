from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_products_service import save_products


logger = setup_logger(__name__, "wb_api_processor.log")


async def process_products(session: AsyncSession, job: SyncJob, token: APIToken):
    logger.info("[ТОВАРЫ] запуск идентификатор_токена=%s", token.id)

    payload = job.payload or {
        "settings": {
            "sort": {"ascending": True},
            "cursor": {"limit": 100},
            "filter": {"withPhoto": -1},
        }
    }
    job.payload = payload
    page_number = 0

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={"checkpoint": payload},
    )

    try:
        total_loaded = 0
        async with WBClient(token) as client:
            while True:
                data = await client.get_products(payload)
                if not isinstance(data, dict):
                    raise WBAPIError(
                        "Wildberries вернул карточки товаров в неожиданном формате",
                        endpoint="content.cards_list",
                    )

                cards = data.get("cards", [])
                if not isinstance(cards, list):
                    raise WBAPIError(
                        "Wildberries вернул список карточек в неожиданном формате",
                        endpoint="content.cards_list",
                    )

                cursor_data = data.get("cursor") or {}
                cursor = payload.setdefault("settings", {}).setdefault("cursor", {})
                cursor_limit = int(cursor.get("limit") or 100)
                cursor_total = int(cursor_data.get("total") or 0)

                updated_at = cursor_data.get("updatedAt")
                nm_id = cursor_data.get("nmID")
                if cursor_total >= cursor_limit and (not updated_at or nm_id is None):
                    raise WBAPIError(
                        "Wildberries вернул неполный курсор списка товаров",
                        endpoint="content.cards_list",
                    )

                page_number += 1
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="source_page_validated",
                    status="success",
                    output_data={
                        "page": page_number,
                        "cards": len(cards),
                        "cursor_total": cursor_total,
                        "cursor_limit": cursor_limit,
                        "cursor_updated_at": updated_at,
                        "cursor_nm_id": nm_id,
                    },
                )
                await save_products(session, job.user_id, token.id, cards)
                total_loaded += len(cards)
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="rows_persisted",
                    status="success",
                    output_data={
                        "page": page_number,
                        "rows_submitted": len(cards),
                        "total_submitted": total_loaded,
                    },
                )

                # Сохраняем новейший курсор продолжения даже для последней страницы.
                # После аварийного завершения повтор продолжит с последней зафиксированной
                # страницы, а не начнёт загрузку сначала.
                if updated_at and nm_id is not None:
                    cursor["updatedAt"] = updated_at
                    cursor["nmID"] = nm_id
                    cursor.pop("data", None)

                await persist_job_checkpoint(session, job, payload)

                if cursor_total < cursor_limit:
                    break

        await trace_sync_stage(
            job=job,
            token=token,
            step="source_read_completed",
            status="success",
            output_data={"pages": page_number, "rows": total_loaded},
        )
        logger.info(
            "[ТОВАРЫ] завершено идентификатор_токена=%s товаров=%s",
            token.id,
            total_loaded,
        )
    except Exception as exc:
        logger.warning(
            "[ТОВАРЫ] ошибка идентификатор_токена=%s тип_ошибки=%s",
            token.id,
            type(exc).__name__,
        )
        raise