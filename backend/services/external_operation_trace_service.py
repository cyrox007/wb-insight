from __future__ import annotations

from typing import Any

from services.operation_log_service import persist_current_operation_event


def _response_status(http_status: int | None) -> tuple[str, str]:
    if http_status is None:
        return "failed", "error"
    if http_status < 400:
        return "success", "info"
    if http_status < 500:
        return "warning", "warning"
    return "failed", "error"


async def trace_external_request(
    *,
    provider: str,
    endpoint: str,
    method: str,
    url: str,
    subject_type: str | None = None,
    subject_id: str | None = None,
    input_data: dict[str, Any] | None = None,
    attempt: int | None = None,
) -> None:
    await persist_current_operation_event(
        domain="external_api",
        operation=f"{provider}_request",
        step="request_sent",
        status="started",
        event_kind="external_http",
        component=provider,
        direction="outgoing",
        provider=provider,
        subject_type=subject_type,
        subject_id=subject_id,
        message=f"Отправлен запрос во внешний API {provider}: {endpoint}",
        input_data={
            "endpoint": endpoint,
            "method": method,
            "url": url,
            "attempt": attempt,
            **(input_data or {}),
        },
    )


async def trace_external_response(
    *,
    provider: str,
    endpoint: str,
    http_status: int | None,
    duration_ms: int,
    subject_type: str | None = None,
    subject_id: str | None = None,
    output_data: dict[str, Any] | None = None,
    error_code: str | None = None,
    message: str | None = None,
    attempt: int | None = None,
) -> None:
    status, severity = _response_status(http_status)
    await persist_current_operation_event(
        domain="external_api",
        operation=f"{provider}_request",
        step="response_received" if http_status is not None else "request_failed",
        status=status,
        severity=severity,
        event_kind="external_http",
        component=provider,
        direction="incoming",
        provider=provider,
        subject_type=subject_type,
        subject_id=subject_id,
        http_status=http_status,
        duration_ms=duration_ms,
        error_code=error_code,
        message=message or f"Получен ответ внешнего API {provider}: {endpoint}",
        output_data={
            "endpoint": endpoint,
            "attempt": attempt,
            **(output_data or {}),
        },
    )