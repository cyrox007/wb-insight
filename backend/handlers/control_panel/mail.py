from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from models.mail_delivery import CampaignStatus, MailCampaign, MailKind, MailMessage, MailStatus, MailSuppression
from models.subscription_model import Subscription
from models.tariffs_model import TariffPlan
from models.users_model import User, UserRoleAssociation
from services.mail_service import queue_test_email
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/control-panel/mail", tags=["Control Panel - Mail"])


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


def _apply_segment(query, segment: dict):
    verified_only = segment.get("verified_only", True) is not False
    if verified_only:
        query = query.where(User.email_verified_at.is_not(None))
    if isinstance(segment.get("active"), bool):
        query = query.where(User.is_active.is_(segment["active"]))

    roles = [str(v) for v in (segment.get("roles") or []) if v]
    if roles:
        query = query.join(UserRoleAssociation, UserRoleAssociation.user_id == User.id).where(
            UserRoleAssociation.role.in_(roles)
        )

    tariff_codes = [str(v) for v in (segment.get("tariff_codes") or []) if v]
    subscription_statuses = [str(v) for v in (segment.get("subscription_statuses") or []) if v]
    if tariff_codes or subscription_statuses:
        query = query.join(Subscription, Subscription.user_id == User.id).join(
            TariffPlan, TariffPlan.id == Subscription.tariff_id
        )
        if tariff_codes:
            query = query.where(TariffPlan.code.in_(tariff_codes))
        if subscription_statuses:
            query = query.where(Subscription.status.in_(subscription_statuses))
    return query


async def _audience(db: AsyncSession, segment: dict) -> list[User]:
    query = _apply_segment(select(User).distinct(), segment).order_by(User.created_at.asc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def _suppressed_audience_keys(
    db: AsyncSession,
    users: list[User],
) -> tuple[set[UUID], set[str]]:
    if not users:
        return set(), set()
    user_ids = [user.id for user in users]
    emails = [user.email.strip().lower() for user in users]
    result = await db.execute(
        select(MailSuppression.user_id, MailSuppression.email).where(
            MailSuppression.active.is_(True),
            or_(
                MailSuppression.user_id.in_(user_ids),
                MailSuppression.email.in_(emails),
            ),
        )
    )
    suppressed_user_ids: set[UUID] = set()
    suppressed_emails: set[str] = set()
    for user_id, email in result.all():
        if user_id is not None:
            suppressed_user_ids.add(user_id)
        if email:
            suppressed_emails.add(str(email).strip().lower())
    return suppressed_user_ids, suppressed_emails


def _user_is_suppressed(
    user: User,
    suppressed_user_ids: set[UUID],
    suppressed_emails: set[str],
) -> bool:
    return user.id in suppressed_user_ids or user.email.strip().lower() in suppressed_emails


@router.get("/campaigns")
async def campaign_list(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
):
    result = await db_session.execute(
        select(MailCampaign).order_by(MailCampaign.created_at.desc()).offset(offset).limit(limit)
    )
    total = await db_session.scalar(select(func.count(MailCampaign.id)))
    return response_success(campaigns=[_campaign_item(item) for item in result.scalars().all()], total=int(total or 0))


@router.post("/campaigns")
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
    users = await _audience(db_session, campaign.segment or {})
    suppressed_user_ids, suppressed_emails = await _suppressed_audience_keys(db_session, users)
    suppressed = sum(
        1 for user in users if _user_is_suppressed(user, suppressed_user_ids, suppressed_emails)
    )
    return response_success(
        audience_count=len(users),
        deliverable_count=max(len(users) - suppressed, 0),
        suppressed_count=suppressed,
        sample=[{"id": str(user.id), "email": user.email} for user in users[:5]],
    )


@router.post("/campaigns/{campaign_id}/test-send")
async def campaign_test_send(
    campaign_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
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


@router.post("/campaigns/{campaign_id}/launch")
async def campaign_launch(campaign_id: UUID, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    campaign_result = await db_session.execute(
        select(MailCampaign).where(MailCampaign.id == campaign_id).with_for_update()
    )
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    if campaign.status != CampaignStatus.DRAFT.value:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="MAIL_CAMPAIGN_ALREADY_LAUNCHED", message="Рассылка уже была запущена")

    users = await _audience(db_session, campaign.segment or {})
    suppressed_user_ids, suppressed_emails = await _suppressed_audience_keys(db_session, users)
    now = datetime.now(timezone.utc)
    queued = suppressed = 0
    for user in users:
        email = user.email.strip().lower()
        is_suppressed = _user_is_suppressed(user, suppressed_user_ids, suppressed_emails)
        db_session.add(
            MailMessage(
                user_id=user.id,
                campaign_id=campaign.id,
                recipient_email=email,
                kind=MailKind.CAMPAIGN.value,
                subject=campaign.subject,
                body=campaign.body,
                status=MailStatus.SUPPRESSED.value if is_suppressed else MailStatus.QUEUED.value,
                max_attempts=lifecycle_config.MAIL_MAX_ATTEMPTS,
                idempotency_key=f"campaign:{campaign.id}:{user.id}",
                safe_error_code="suppressed" if is_suppressed else None,
            )
        )
        if is_suppressed:
            suppressed += 1
        else:
            queued += 1

    campaign.audience_count = len(users)
    campaign.queued_count = queued
    campaign.suppressed_count = suppressed
    campaign.status = CampaignStatus.QUEUED.value if queued else CampaignStatus.COMPLETED.value
    campaign.launched_at = now
    if not queued:
        campaign.completed_at = now
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.post("/campaigns/{campaign_id}/cancel")
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
    campaign.completed_at = datetime.now(timezone.utc)
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.get("/campaigns/{campaign_id}/messages")
async def campaign_messages(
    campaign_id: UUID,
    mail_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
):
    query = select(MailMessage).where(MailMessage.campaign_id == campaign_id)
    count_query = select(func.count(MailMessage.id)).where(MailMessage.campaign_id == campaign_id)
    if mail_status:
        query = query.where(MailMessage.status == mail_status)
        count_query = count_query.where(MailMessage.status == mail_status)
    result = await db_session.execute(query.order_by(MailMessage.created_at.desc()).offset(offset).limit(limit))
    total = await db_session.scalar(count_query)
    return response_success(messages=[_message_item(item) for item in result.scalars().all()], total=int(total or 0))
