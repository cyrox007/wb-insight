from __future__ import annotations

from typing import Any

from core.operation_context import get_operation_context
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from services.operation_log_service import persist_current_operation_event


async def trace_sync_stage(
    *,
    job: SyncJob,
    token: APIToken,
    step: str,
    status: str = "info",
    severity: str = "info",
    error_code: str | None = None,
    message: str | None = None,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    """Добавляет семантический этап загрузки данных в текущую цепочку задачи."""

    if get_operation_context() is None:
        return
    await persist_current_operation_event(
        domain="sync",
        operation="marketplace_sync",
        step=step,
        status=status,
        severity=severity,
        event_kind="sync_stage",
        component=f"sync.{job.entity}",
        direction="internal",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider=getattr(token.marketplace, "value", str(token.marketplace)),
        error_code=error_code,
        message=message or f"Этап синхронизации '{job.entity}': {step}",
        input_data={
            "job_id": job.id,
            "token_id": token.id,
            "entity": job.entity,
            **(input_data or {}),
        },
        output_data=output_data or {},
        metrics=metrics or {},
    )