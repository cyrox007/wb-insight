from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from models.mail_delivery import CampaignStatus, MailCampaign, MailMessage, MailStatus
from services.mail_campaign_service import (
    CampaignStateConflict,
    launch_campaign,
    preview_campaign_audience,
    schedule_campaign,
)
from services.mail_service import queue_test_email
from utils.responce_helps import response_error, response_success


router = APIRouter(
    prefix="/control-panel/mail",
    tags=["Control Panel - Mail"],
    dependencies=[Depends(require_permission(Permission.MAIL_READ))],
)


def _campaign_item(item: MailCampaign) -> dict:
    return {
        "id": str(item.id),
        "name": item.name,
        "subject": item.subject,
        "body": item.body,
        "segment": item.segment or {},
        "status": item.status,
        "audience_count": item.audience_count,
        "queued_count": item.queued_count,
        "sent_count": item.sent_count,
        "failed_count": item.failed_count,
        "suppressed_count": item.suppressed_count,
        "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
        "launched_at": item.launched_at.isoformat() if item.launched_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _message_item(item: MailMessage) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id) if item.user_id else None,
        "recipient_email": item.recipient_email,
        "kind": item.kind,
        "status": item.status,
        "attempt_count": item.attempt_count,
        "max_attempts": item.max_attempts,
        "safe_error_code": item.safe_error_code,
        "provider_message_id": item.provider_message_id,
        "last_attempt_at": item.last_attempt_at.isoformat() if item.last_attempt_at else None,
        "sent_at": item.sent_at.isoformat() if item.sent_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _valid_campaign_statuses() -> set[str]:
    return {item.value for item in CampaignStatus}


def _valid_mail_statuses() -> set[str]:
    return {item.value for item in MailStatus}


def _require_campaign_delivery(response: Response):
    if lifecycle_config.MAIL_DELIVERY_ENABLED:
        return None
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return response_error(
        code="MAIL_DELIVERY_DISABLED",
        message="Отправка пользовательских рассылок отключена",
    )


@router.get("/campaigns")
async def campaign_list(
    response: Response,
    campaign_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
):
    if campaign_status and campaign_status not in _valid_campaign_statuses():
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_CAMPAIGN_STATUS_INVALID", message="Неизвестный статус рассылки")
    query = select(MailCampaign)
    count_query = select(func.count(MailCampaign.id))
    if campaign_status:
        query = query.where(MailCampaign.status == campaign_status)
        count_query = count_query.where(MailCampaign.status == campaign_status)
    result = await db_session.execute(
        query.order_by(MailCampaign.created_at.desc()).offset(offset).limit(limit)
    )
    total = await db_session.scalar(count_query)
    return response_success(
        campaigns=[_campaign_item(item) for item in result.scalars().all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.post("/campaigns", dependencies=[Depends(require_permission(Permission.MAIL_WRITE))])
async def campaign_create(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    body = await request.json()
    name = str(body.get("name") or "").strip()
    subject = str(body.get("subject") or "").strip()
    content = str(body.get("body") or "").strip()
    segment = body.get("segment") if isinstance(body.get("segment"), dict) else {"verified_only": True, "active": True}
    if not name or not subject or not content:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_CAMPAIGN_INVALID", message="Название, тема и текст письма обязательны")
    if len(subject) > 255 or len(content) > 100_000:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_CAMPAIGN_INVALID", message="Письмо превышает допустимый размер")
    campaign = MailCampaign(
        name=name[:180],
        subject=subject,
        body=content,
        segment=segment,
        status=CampaignStatus.DRAFT.value,
        created_by=request.state.user_id,
    )
    db_session.add(campaign)
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.get("/campaigns/{campaign_id}")
async def campaign_detail(campaign_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    campaign = await db_session.get(MailCampaign, campaign_id)
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    return response_success(campaign=_campaign_item(campaign))


@router.post("/campaigns/{campaign_id}/preview")
async def campaign_preview(campaign_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    campaign = await db_session.get(MailCampaign, campaign_id)
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    preview = await preview_campaign_audience(db_session, campaign.segment or {})
    return response_success(**preview)


@router.post("/campaigns/{campaign_id}/test-send", dependencies=[Depends(require_permission(Permission.MAIL_WRITE))])
async def campaign_test_send(
    campaign_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    disabled = _require_campaign_delivery(response)
    if disabled is not None:
        return disabled
    campaign = await db_session.get(MailCampaign, campaign_id)
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    if not email or "@" not in email or len(email) > 320:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_TEST_EMAIL_INVALID", message="Укажите корректный email")
    message = await queue_test_email(
        db_session,
        recipient_email=email,
        subject=f"[TEST] {campaign.subject}",
        body=campaign.body,
        actor_id=request.state.user_id,
    )
    return response_success(message_id=str(message.id), status=message.status)


@router.post("/campaigns/{campaign_id}/schedule", dependencies=[Depends(require_permission(Permission.MAIL_WRITE))])
async def campaign_schedule(
    campaign_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    campaign_result = await db_session.execute(
        select(MailCampaign).where(MailCampaign.id == campaign_id).with_for_update()
    )
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    body = await request.json()
    raw_scheduled_at = str(body.get("scheduled_at") or "").strip()
    try:
        scheduled_at = datetime.fromisoformat(raw_scheduled_at.replace("Z", "+00:00"))
        schedule_campaign(campaign, scheduled_at)
    except ValueError:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="MAIL_CAMPAIGN_SCHEDULE_INVALID",
            message="Укажите будущую дату и время с часовым поясом",
        )
    except CampaignStateConflict:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="MAIL_CAMPAIGN_NOT_SCHEDULABLE",
            message="Эту рассылку уже нельзя планировать",
        )
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.post("/campaigns/{campaign_id}/launch", dependencies=[Depends(require_permission(Permission.MAIL_WRITE))])
async def campaign_launch(campaign_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    disabled = _require_campaign_delivery(response)
    if disabled is not None:
        return disabled
    campaign_result = await db_session.execute(
        select(MailCampaign).where(MailCampaign.id == campaign_id).with_for_update()
    )
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    try:
        await launch_campaign(db_session, campaign)
    except CampaignStateConflict:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="MAIL_CAMPAIGN_ALREADY_LAUNCHED", message="Рассылка уже была запущена")
    return response_success(campaign=_campaign_item(campaign))


@router.post("/campaigns/{campaign_id}/cancel", dependencies=[Depends(require_permission(Permission.MAIL_WRITE))])
async def campaign_cancel(campaign_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    campaign_result = await db_session.execute(
        select(MailCampaign).where(MailCampaign.id == campaign_id).with_for_update()
    )
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    if campaign.status in {CampaignStatus.COMPLETED.value, CampaignStatus.CANCELLED.value}:
        return response_success(campaign=_campaign_item(campaign))
    messages = await db_session.execute(
        select(MailMessage).where(
            MailMessage.campaign_id == campaign.id,
            MailMessage.status == MailStatus.QUEUED.value,
        )
    )
    for message in messages.scalars().all():
        message.status = MailStatus.CANCELLED.value
    campaign.status = CampaignStatus.CANCELLED.value
    campaign.scheduled_at = None
    campaign.completed_at = datetime.now(timezone.utc)
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.get("/campaigns/{campaign_id}/messages")
async def campaign_messages(
    campaign_id: UUID,
    response: Response,
    mail_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
):
    if mail_status and mail_status not in _valid_mail_statuses():
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_STATUS_INVALID", message="Неизвестный статус доставки")
    query = select(MailMessage).where(MailMessage.campaign_id == campaign_id)
    count_query = select(func.count(MailMessage.id)).where(MailMessage.campaign_id == campaign_id)
    if mail_status:
        query = query.where(MailMessage.status == mail_status)
        count_query = count_query.where(MailMessage.status == mail_status)
    result = await db_session.execute(query.order_by(MailMessage.created_at.desc()).offset(offset).limit(limit))
    total = await db_session.scalar(count_query)
    return response_success(
        messages=[_message_item(item) for item in result.scalars().all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )
