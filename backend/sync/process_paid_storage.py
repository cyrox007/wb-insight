from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.client import WBAPIError, WBClient
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.sync_job_service import persist_job_checkpoint
from services.sync_operation_trace_service import trace_sync_stage
from services.wb_paid_storage_service import replace_paid_storage_period
from settings import config


logger = setup_logger(__name__, "wb_api_processor.log")
PENDING_STATUSES = {"new", "pending", "queued", "started", "processing"}


def _parse_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Для синхронизации платного хранения требуется корректное поле {field}"
        ) from exc


def _created_task_id(response: Any) -> str:
    data = response.get("data") if isinstance(response, dict) else None
    task_id = data.get("taskId") if isinstance(data, dict) else None
    if not task_id:
        raise RuntimeError(
            "Wildberries не вернул taskId при создании отчёта платного хранения"
        )
    return str(task_id)


def _task_status(response: Any) -> str:
    data = response.get("data") if isinstance(response, dict) else None
    status = data.get("status") if isinstance(data, dict) else None
    if not status:
        raise RuntimeError(
            "Wildberries не вернул статус задачи отчёта платного хранения"
        )
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
        raise ValueError("dateTo платного хранения не может быть раньше dateFrom")
    if current < overall_start:
        current = overall_start

    total_rows = 0
    completed_chunks = 0
    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_started",
        status="started",
        input_data={
            "period_from": overall_start,
            "period_to": overall_end,
            "resume_from": current,
            "existing_task_id": payload.get("taskId"),
        },
    )

    async with WBClient(token) as client:
        while current <= overall_end:
            chunk_end = min(current + timedelta(days=7), overall_end)
            task_id = payload.get("taskId")
            task_from = payload.get("taskDateFrom")
            task_to = payload.get("taskDateTo")

            await trace_sync_stage(
                job=job,
                token=token,
                step="storage_chunk_started",
                status="started",
                input_data={
                    "chunk_from": current,
                    "chunk_to": chunk_end,
                    "resume_task_id": task_id,
                },
            )

            if task_id and (
                str(task_from) != current.isoformat()
                or str(task_to) != chunk_end.isoformat()
            ):
                # Не связываем старый сформированный отчёт с другим интервалом дат.
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="stale_storage_task_discarded",
                    status="warning",
                    severity="warning",
                    output_data={
                        "task_id": task_id,
                        "task_date_from": task_from,
                        "task_date_to": task_to,
                        "expected_from": current,
                        "expected_to": chunk_end,
                    },
                )
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
                await trace_sync_stage(
                    job=job,
                    token=token,
                    step="storage_task_created",
                    status="success",
                    output_data={
                        "task_id": task_id,
                        "chunk_from": current,
                        "chunk_to": chunk_end,
                    },
                )
                # Фиксируем taskId до опроса. После остановки worker продолжит эту же задачу WB.
                await persist_job_checkpoint(session, job, payload)

            try:
                task_status = ""
                for poll_number in range(1, config.WB_STORAGE_STATUS_MAX_POLLS + 1):
                    task_status = _task_status(
                        await client.get_paid_storage_report_status(str(task_id))
                    )
                    await trace_sync_stage(
                        job=job,
                        token=token,
                        step="storage_task_status_received",
                        status="success" if task_status == "done" else "info",
                        output_data={
                            "task_id": task_id,
                            "poll": poll_number,
                            "task_status": task_status,
                        },
                    )
                    if task_status == "done":
                        break
                    if task_status not in PENDING_STATUSES:
                        await _clear_task(session, job, payload)
                        raise RuntimeError(
                            f"Задача платного хранения WB завершилась со статусом '{task_status}'"
                        )
                else:
                    # Сохраняем taskId, чтобы повтор продолжил тот же сформированный отчёт.
                    raise RuntimeError(
                        "Задача платного хранения WB не завершилась за допустимое число проверок"
                    )

                report = await client.download_paid_storage_report(str(task_id))
            except WBAPIError as exc:
                if exc.status_code == 404:
                    # Сформированные отчёты имеют срок жизни. Повтор создаст новую задачу.
                    await _clear_task(session, job, payload)
                    raise RuntimeError(
                        "Задача платного хранения WB истекла до скачивания отчёта"
                    ) from exc
                raise

            rows = report if isinstance(report, list) else []
            await trace_sync_stage(
                job=job,
                token=token,
                step="storage_report_downloaded",
                status="success",
                output_data={
                    "task_id": task_id,
                    "rows_received": len(rows),
                },
            )
            saved = await replace_paid_storage_period(
                session,
                user_id=job.user_id,
                token_id=token.id,
                task_id=str(task_id),
                start_date=current,
                end_date=chunk_end,
                data=rows,
            )
            total_rows += saved
            await trace_sync_stage(
                job=job,
                token=token,
                step="rows_persisted",
                status="success",
                output_data={
                    "task_id": task_id,
                    "rows_received": len(rows),
                    "rows_saved": saved,
                    "period_from": current,
                    "period_to": chunk_end,
                },
            )

            completed_chunks += 1
            payload["completedThrough"] = chunk_end.isoformat()
            payload["currentDateFrom"] = (chunk_end + timedelta(days=1)).isoformat()
            payload["taskId"] = None
            payload["taskDateFrom"] = None
            payload["taskDateTo"] = None
            # Одна фиксация делает долговечными замену интервала и курсор продолжения.
            await persist_job_checkpoint(session, job, payload)
            await trace_sync_stage(
                job=job,
                token=token,
                step="storage_chunk_completed",
                status="success",
                output_data={
                    "completed_through": chunk_end,
                    "next_from": payload["currentDateFrom"],
                    "completed_chunks": completed_chunks,
                },
            )
            current = chunk_end + timedelta(days=1)

    await trace_sync_stage(
        job=job,
        token=token,
        step="source_read_completed",
        status="success",
        output_data={
            "chunks": completed_chunks,
            "rows_saved": total_rows,
            "period_from": overall_start,
            "period_to": overall_end,
        },
    )
    logger.info(
        "[ПЛАТНОЕ_ХРАНЕНИЕ] завершено идентификатор_токена=%s интервалов=%s строк=%s период=%s..%s",
        token.id,
        completed_chunks,
        total_rows,
        overall_start,
        overall_end,
    )