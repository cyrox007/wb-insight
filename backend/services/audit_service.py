import hashlib
import hmac
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Database
from core.logger import setup_logger
from models.audit_event import AuditEvent
from models.users_model import UserRoleAssociation
from settings import config


logger = setup_logger(__name__, "security_audit.log")

_SECRET_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "credential",
    "api_key",
    "apikey",
    "jwt",
    "encrypted",
)
_MAX_DEPTH = 5
_MAX_ITEMS = 50
_MAX_STRING = 512


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in _SECRET_FRAGMENTS)


def sanitize_audit_metadata(value: Any, *, _depth: int = 0) -> Any:
    """Return bounded JSON-safe metadata with secret-looking values redacted."""
    if _depth >= _MAX_DEPTH:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        return value if len(value) <= _MAX_STRING else value[:_MAX_STRING] + "…"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (raw_key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                result["_truncated"] = True
                break
            key = str(raw_key)[:128]
            result[key] = "[REDACTED]" if _is_sensitive_key(key) else sanitize_audit_metadata(item, _depth=_depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        safe = [sanitize_audit_metadata(item, _depth=_depth + 1) for item in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            safe.append("[TRUNCATED]")
        return safe
    return sanitize_audit_metadata(str(value), _depth=_depth + 1)


def hash_client_evidence(value: str | None) -> str | None:
    if not value:
        return None
    key = str(config.LEGAL_EVIDENCE_HMAC_KEY or config.SECRET_KEY).encode("utf-8")
    return hmac.new(key, value.encode("utf-8", errors="replace"), hashlib.sha256).hexdigest()


def _normalize_actor_id(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


async def _actor_roles(session: AsyncSession, actor_user_id: UUID | None) -> list[str]:
    if actor_user_id is None:
        return []
    result = await session.execute(
        select(UserRoleAssociation.role).where(UserRoleAssociation.user_id == actor_user_id)
    )
    return sorted({str(role) for role in result.scalars().all() if role})


async def record_audit_event(
    session: AsyncSession,
    *,
    actor_user_id: UUID | str | None,
    actor_roles: list[str] | set[str] | tuple[str, ...] | None,
    action: str,
    target_type: str | None,
    target_id: str | None,
    result: str,
    error_code: str | None,
    request_id: str | None,
    source: str,
    method: str | None,
    path: str | None,
    client_ip: str | None,
    user_agent: str | None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    actor_id = _normalize_actor_id(actor_user_id)
    roles = sorted({str(role) for role in (actor_roles or []) if role})
    if actor_id is not None and not roles:
        roles = await _actor_roles(session, actor_id)

    event = AuditEvent(
        actor_user_id=actor_id,
        actor_roles=roles,
        action=str(action)[:128],
        target_type=str(target_type)[:64] if target_type else None,
        target_id=str(target_id)[:160] if target_id else None,
        result=str(result)[:16],
        error_code=str(error_code)[:96] if error_code else None,
        request_id=str(request_id)[:64] if request_id else None,
        source=str(source or "api")[:32],
        method=str(method).upper()[:8] if method else None,
        path=str(path)[:2048] if path else None,
        client_ip_hash=hash_client_evidence(client_ip),
        user_agent_hash=hash_client_evidence(user_agent),
        event_metadata=sanitize_audit_metadata(metadata or {}),
    )
    session.add(event)
    await session.flush()
    return event


async def persist_audit_event(**kwargs: Any) -> AuditEvent | None:
    """Persist an audit event independently from the business transaction.

    Failed/denied requests need to be durable too, therefore middleware audit
    writes cannot share a transaction that may be rolled back. If the audit DB
    write itself fails, the structured security log remains the last-resort
    incident trail and the user request is not converted into a second failure.
    """
    session = await Database.get_session()
    try:
        event = await record_audit_event(session, **kwargs)
        await session.commit()
        return event
    except Exception:
        await session.rollback()
        logger.exception(
            "Unable to persist durable audit event action=%s request_id=%s",
            kwargs.get("action"),
            kwargs.get("request_id"),
        )
        return None
    finally:
        await session.close()
