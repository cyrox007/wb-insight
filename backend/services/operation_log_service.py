from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Database
from core.logger import setup_logger
from models.operation_log_event import OperationLogEvent


logger = setup_logger(__name__, "operation_diagnostics.log")
_MAX_DEPTH = 6
_MAX_ITEMS = 80
_MAX_STRING = 2000
_SAFE_IDENTIFIER_KEYS = {
    "token_id",
    "credential_id",
    "payment_id",
    "operation_id",
    "request_id",
    "order_id",
    "user_id",
}
_SECRET_KEYS = {
    "authorization",
    "cookie",
    "set_cookie",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "webhook_secret",
    "encrypted_token",
    "api_key",
    "apikey",
    "jwt",
    "access_token",
    "refresh_token",
    "bearer_token",
    "card_number",
    "card_pan",
    "pan",
    "cvv",
    "cvc",
    "cryptogram",
    "credentials",
    "form_url",
    "formurl",
    "confirmation_url",
    "payment_url",
}
_ALLOWED_STATUSES = {"started", "success", "warning", "failed", "info"}
_ALLOWED_SEVERITIES = {"info", "warning", "error", "critical"}


def _normalized_key(value: str) -> str:
    return value.lower().strip().replace("-", "_").replace(" ", "_")


def _is_secret_key(key: str) -> bool:
    normalized = _normalized_key(key)
    if normalized in _SAFE_IDENTIFIER_KEYS:
        return False
    if normalized in _SECRET_KEYS:
        return True
    if normalized.endswith("_password") or normalized.endswith("_secret"):
        return True
    if normalized.endswith("_token") and not normalized.endswith("_token_id"):
        return True
    return False


def sanitize_operation_data(value: Any, *, _depth: int = 0) -> Any:
    """Очищает диагностические данные от секретов и ограничивает их размер."""

    if _depth >= _MAX_DEPTH:
        return "[ОБРЕЗАНО]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value if len(value) <= _MAX_STRING else value[:_MAX_STRING] + "…"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (raw_key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                result["_обрезано"] = True
                break
            key = str(raw_key)[:128]
            result[key] = (
                "[СКРЫТО]"
                if _is_secret_key(key)
                else sanitize_operation_data(item, _depth=_depth + 1)
            )
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        safe = [
            sanitize_operation_data(item, _depth=_depth + 1)
            for item in items[:_MAX_ITEMS]
        ]
        if len(items) > _MAX_ITEMS:
            safe.append("[ОБРЕЗАНО]")
        return safe
    return sanitize_operation_data(str(value), _depth=_depth + 1)


def normalize_operation_id(value: UUID | str | None = None) -> UUID:
    if isinstance(value, UUID):
        return value
    if value:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            pass
    return uuid4()


def _optional_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


async def record_operation_event(
    session: AsyncSession,
    *,
    operation_id: UUID | str,
    domain: str,
    operation: str,
    step: str,
    status: str,
    user_id: UUID | str | None = None,
    actor_user_id: UUID | str | None = None,
    parent_operation_id: UUID | str | None = None,
    severity: str = "info",
    subject_type: str | None = None,
    subject_id: str | UUID | None = None,
    provider: str | None = None,
    request_id: str | None = None,
    http_status: int | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
    message: str | None = None,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> OperationLogEvent:
    normalized_status = status if status in _ALLOWED_STATUSES else "info"
    normalized_severity = severity if severity in _ALLOWED_SEVERITIES else "info"
    event = OperationLogEvent(
        operation_id=normalize_operation_id(operation_id),
        parent_operation_id=_optional_uuid(parent_operation_id),
        user_id=_optional_uuid(user_id),
        actor_user_id=_optional_uuid(actor_user_id),
        domain=str(domain or "system")[:32],
        operation=str(operation or "unknown")[:64],
        step=str(step or "unknown")[:96],
        status=normalized_status,
        severity=normalized_severity,
        subject_type=str(subject_type)[:64] if subject_type else None,
        subject_id=str(subject_id)[:160] if subject_id is not None else None,
        provider=str(provider)[:64] if provider else None,
        request_id=str(request_id)[:64] if request_id else None,
        http_status=int(http_status) if http_status is not None else None,
        duration_ms=max(0, int(duration_ms)) if duration_ms is not None else None,
        error_code=str(error_code)[:96] if error_code else None,
        message=str(message)[:4000] if message else None,
        input_data=sanitize_operation_data(input_data or {}),
        output_data=sanitize_operation_data(output_data or {}),
        metrics=sanitize_operation_data(metrics or {}),
    )
    session.add(event)
    await session.flush()
    return event


async def persist_operation_event(**kwargs: Any) -> OperationLogEvent | None:
    """Пишет диагностическое событие независимо от бизнес-транзакции."""

    session = await Database.get_session()
    try:
        event = await record_operation_event(session, **kwargs)
        await session.commit()
        return event
    except Exception:
        await session.rollback()
        logger.exception(
            "Не удалось сохранить событие операционной диагностики: operation=%s step=%s",
            kwargs.get("operation"),
            kwargs.get("step"),
        )
        return None
    finally:
        await session.close()


def operation_event_payload(event: OperationLogEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "operation_id": str(event.operation_id),
        "parent_operation_id": str(event.parent_operation_id) if event.parent_operation_id else None,
        "user_id": str(event.user_id) if event.user_id else None,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "domain": event.domain,
        "operation": event.operation,
        "step": event.step,
        "status": event.status,
        "severity": event.severity,
        "subject_type": event.subject_type,
        "subject_id": event.subject_id,
        "provider": event.provider,
        "request_id": event.request_id,
        "http_status": event.http_status,
        "duration_ms": event.duration_ms,
        "error_code": event.error_code,
        "message": event.message,
        "input": event.input_data or {},
        "output": event.output_data or {},
        "metrics": event.metrics or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


async def get_operation_timeline(
    session: AsyncSession,
    operation_id: UUID,
) -> list[OperationLogEvent]:
    result = await session.execute(
        select(OperationLogEvent)
        .where(OperationLogEvent.operation_id == operation_id)
        .order_by(OperationLogEvent.created_at, OperationLogEvent.id)
    )
    return list(result.scalars().all())


async def list_operation_events(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    domain: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    request_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[OperationLogEvent]:
    statement = select(OperationLogEvent)
    if user_id is not None:
        statement = statement.where(OperationLogEvent.user_id == user_id)
    if domain:
        statement = statement.where(OperationLogEvent.domain == domain)
    if status:
        statement = statement.where(OperationLogEvent.status == status)
    if severity:
        statement = statement.where(OperationLogEvent.severity == severity)
    if request_id:
        statement = statement.where(OperationLogEvent.request_id == request_id)
    statement = statement.order_by(desc(OperationLogEvent.created_at), desc(OperationLogEvent.id))
    statement = statement.limit(max(1, min(limit, 500))).offset(max(0, offset))
    result = await session.execute(statement)
    return list(result.scalars().all())
