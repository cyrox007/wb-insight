from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.wb_paid_storage_service import replace_paid_storage_period
from settings import config


logger = setup_logger(__name__, "wb_api_processor.log")
PENDING_STATUSES = {"new", "pending", "queued", "started", "processing"}


def _parse_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"paid storage sync requires valid {field}") from exc


def _created_task_id(response: Any) -> str:
    data = response.get("data") if isinstance(response, dict) else None
    task_id = data.get("taskId") if isinstance(data, dict) else None
    if not task_id:
        raise RuntimeError("WB paid storage task creation returned no taskId")
    return str(task_id)


def _task_status(response: Any) -> str:
    data = response.get("data") if isinstance(response, dict) else None
    status = data.get("status") if isinstance(data, dict) else None
    if not status:
        raise RuntimeError("WB paid storage task status response has no status")
    return str(status).strip().lower()


async def _clear_task(
    session: AsyncSession,
    job: SyncJob,
    payload: dict[str, Any],
) -> None:
    payload["taskId"] = None
    payload["taskDateFrom"] = None
    payload["taskDateTo"] = None
    await persist_job_checkpoint(session, job, payload)


async def process_paid_storage(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    payload = dict(job.payload or {})
    overall_start = _parse_date(payload.get("dateFrom"), "dateFrom")
    overall_end = _parse_date(payload.get("dateTo"), "dateTo")
    current = _parse_date(
        payload.get("currentDateFrom") or payload.get("dateFrom"),
        "currentDateFrom",
    )
    if overall_end < overall_start:
        raise ValueError("paid storage dateTo must be on or after dateFrom")
    if current < overall_start:
        current = overall_start

    total_rows = 0
    completed_chunks = 0

    async with WBClient(token) as client:
        while current <= overall_end:
            chunk_end = min(current + timedelta(days=7), overall_end)
            task_id = payload.get("taskId")
            task_from = payload.get("taskDateFrom")
            task_to = payload.get("taskDateTo")

            if task_id and (
                str(task_from) != current.isoformat()
                or str(task_to) != chunk_end.isoformat()
            ):
                # Never attach an old generated report to a different date chunk.
                await _clear_task(session, job, payload)
                task_id = None

            if not task_id:
                created = await client.create_paid_storage_report(
                    {
                        "dateFrom": current.isoformat(),
                        "dateTo": chunk_end.isoformat(),
                    }
                )
                task_id = _created_task_id(created)
                payload["taskId"] = task_id
                payload["taskDateFrom"] = current.isoformat()
                payload["taskDateTo"] = chunk_end.isoformat()
                # Persist before polling. A killed worker resumes this exact WB task.
                await persist_job_checkpoint(session, job, payload)

            try:
                status = ""
                for _ in range(config.WB_STORAGE_STATUS_MAX_POLLS):
                    status = _task_status(
                        await client.get_paid_storage_report_status(str(task_id))
                    )
                    if status == "done":
                        break
                    if status not in PENDING_STATUSES:
                        await _clear_task(session, job, payload)
                        raise RuntimeError(
                            f"WB paid storage task ended with status '{status}'"
                        )
                else:
                    # Keep taskId so a retry continues the same generated report.
                    raise RuntimeError(
                        "WB paid storage task did not finish within polling budget"
                    )

                report = await client.download_paid_storage_report(str(task_id))
            except WBAPIError as exc:
                if exc.status_code == 404:
                    # Generated reports expire. Retry with a fresh task.
                    await _clear_task(session, job, payload)
                    raise RuntimeError(
                        "WB paid storage task expired before it could be downloaded"
                    ) from exc
                raise

            rows = report if isinstance(report, list) else []
            total_rows += await replace_paid_storage_period(
                session,
                user_id=job.user_id,
                token_id=token.id,
                task_id=str(task_id),
                start_date=current,
                end_date=chunk_end,
                data=rows,
            )

            completed_chunks += 1
            payload["completedThrough"] = chunk_end.isoformat()
            payload["currentDateFrom"] = (chunk_end + timedelta(days=1)).isoformat()
            payload["taskId"] = None
            payload["taskDateFrom"] = None
            payload["taskDateTo"] = None
            # This commit makes both the chunk replacement and its cursor durable.
            await persist_job_checkpoint(session, job, payload)
            current = chunk_end + timedelta(days=1)

    logger.info(
        "[PAID_STORAGE] success token_id=%s chunks=%s rows=%s period=%s..%s",
        token.id,
        completed_chunks,
        total_rows,
        overall_start,
        overall_end,
    )
