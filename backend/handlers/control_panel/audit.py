from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from models.audit_event import AuditEvent
from models.users_model import User
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/control-panel/audit", tags=["Control Panel - Audit"])


def _payload(event: AuditEvent, actor_email: str | None = None) -> dict:
    return {
        "id": str(event.id),
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "actor_email": actor_email,
        "actor_roles": list(event.actor_roles or []),
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "result": event.result,
        "error_code": event.error_code,
        "request_id": event.request_id,
        "source": event.source,
        "method": event.method,
        "path": event.path,
        "client_ip_hash": event.client_ip_hash,
        "user_agent_hash": event.user_agent_hash,
        "metadata": event.event_metadata or {},
    }


@router.get("/")
async def audit_list(
    actor_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None, max_length=128),
    target_type: str | None = Query(default=None, max_length=64),
    target_id: str | None = Query(default=None, max_length=160),
    event_result: str | None = Query(default=None, alias="result", max_length=16),
    request_id: str | None = Query(default=None, max_length=64),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
):
    conditions = []
    if actor_id:
        conditions.append(AuditEvent.actor_user_id == actor_id)
    if action:
        conditions.append(AuditEvent.action.ilike(f"{action.strip()}%"))
    if target_type:
        conditions.append(AuditEvent.target_type == target_type.strip())
    if target_id:
        conditions.append(AuditEvent.target_id == target_id.strip())
    if event_result:
        conditions.append(AuditEvent.result == event_result.strip())
    if request_id:
        conditions.append(AuditEvent.request_id == request_id.strip())
    if date_from:
        conditions.append(AuditEvent.created_at >= date_from)
    if date_to:
        conditions.append(AuditEvent.created_at <= date_to)

    total = int(
        (
            await db_session.execute(
                select(func.count(AuditEvent.id)).where(*conditions)
            )
        ).scalar_one()
    )
    result = await db_session.execute(
        select(AuditEvent, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(*conditions)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    events = [_payload(event, email) for event, email in result.all()]
    return response_success(
        events=events,
        pagination={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/{event_id}")
async def audit_detail(
    event_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    result = await db_session.execute(
        select(AuditEvent, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.id == event_id)
    )
    row = result.one_or_none()
    if row is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="AUDIT_EVENT_NOT_FOUND", message="Событие аудита не найдено")
    event, email = row
    return response_success(event=_payload(event, email))
