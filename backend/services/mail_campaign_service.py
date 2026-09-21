from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config
from models.mail_delivery import (
    CampaignStatus,
    MailCampaign,
    MailKind,
    MailMessage,
    MailStatus,
    MailSuppression,
)
from models.subscription_model import Subscription
from models.tariffs_model import TariffPlan
from models.users_model import User, UserRoleAssociation


class CampaignStateConflict(RuntimeError):
    pass


def apply_segment(query, segment: dict):
    """Apply the supported campaign audience contract to a User query."""
    verified_only = segment.get("verified_only", True) is not False
    if verified_only:
        query = query.where(User.email_verified_at.is_not(None))
    if isinstance(segment.get("active"), bool):
        query = query.where(User.is_active.is_(segment["active"]))

    roles = [str(value) for value in (segment.get("roles") or []) if value]
    if roles:
        query = query.join(
            UserRoleAssociation,
            UserRoleAssociation.user_id == User.id,
        ).where(UserRoleAssociation.role.in_(roles))

    tariff_codes = [str(value) for value in (segment.get("tariff_codes") or []) if value]
    subscription_statuses = [
        str(value) for value in (segment.get("subscription_statuses") or []) if value
    ]
    if tariff_codes or subscription_statuses:
        query = query.join(Subscription, Subscription.user_id == User.id).join(
            TariffPlan,
            TariffPlan.id == Subscription.tariff_id,
        )
        if tariff_codes:
            query = query.where(TariffPlan.code.in_(tariff_codes))
        if subscription_statuses:
            query = query.where(Subscription.status.in_(subscription_statuses))
    return query


async def campaign_audience(session: AsyncSession, segment: dict) -> list[User]:
    query = apply_segment(select(User).distinct(), segment).order_by(User.created_at.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def suppressed_audience_keys(
    session: AsyncSession,
    users: list[User],
) -> tuple[set[UUID], set[str]]:
    if not users:
        return set(), set()
    user_ids = [user.id for user in users]
    emails = [user.email.strip().lower() for user in users]
    result = await session.execute(
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


def user_is_suppressed(
    user: User,
    suppressed_user_ids: set[UUID],
    suppressed_emails: set[str],
) -> bool:
    return user.id in suppressed_user_ids or user.email.strip().lower() in suppressed_emails


async def preview_campaign_audience(session: AsyncSession, segment: dict) -> dict:
    users = await campaign_audience(session, segment)
    suppressed_user_ids, suppressed_emails = await suppressed_audience_keys(session, users)
    suppressed = sum(
        1
        for user in users
        if user_is_suppressed(user, suppressed_user_ids, suppressed_emails)
    )
    return {
        "audience_count": len(users),
        "deliverable_count": max(len(users) - suppressed, 0),
        "suppressed_count": suppressed,
        "sample": [{"id": str(user.id), "email": user.email} for user in users[:5]],
    }


def schedule_campaign(
    campaign: MailCampaign,
    scheduled_at: datetime,
    *,
    now: datetime | None = None,
) -> MailCampaign:
    """Move a draft/scheduled campaign to a future UTC launch instant."""
    if campaign.status not in {CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value}:
        raise CampaignStateConflict("campaign_not_schedulable")
    current = now or datetime.now(timezone.utc)
    if scheduled_at.tzinfo is None:
        raise ValueError("scheduled_at_timezone_required")
    launch_at = scheduled_at.astimezone(timezone.utc)
    if launch_at <= current:
        raise ValueError("scheduled_at_must_be_future")
    campaign.status = CampaignStatus.SCHEDULED.value
    campaign.scheduled_at = launch_at
    campaign.completed_at = None
    return campaign


async def launch_campaign(
    session: AsyncSession,
    campaign: MailCampaign,
    *,
    now: datetime | None = None,
) -> MailCampaign:
    """Materialize one campaign into idempotent per-user outbox messages.

    Materialization is intentionally safe to retry. Existing per-user rows are
    reused instead of relying only on the unique constraint, so an operational
    retry cannot turn a partially materialized campaign into a duplicate-key
    failure.
    """
    if campaign.status not in {CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value}:
        raise CampaignStateConflict("campaign_not_launchable")

    current = now or datetime.now(timezone.utc)
    users = await campaign_audience(session, campaign.segment or {})
    suppressed_user_ids, suppressed_emails = await suppressed_audience_keys(session, users)

    existing_result = await session.execute(
        select(MailMessage.user_id, MailMessage.status).where(
            MailMessage.campaign_id == campaign.id,
        )
    )
    existing_by_user = {
        user_id: mail_status
        for user_id, mail_status in existing_result.all()
        if user_id is not None
    }

    queued = sent = failed = suppressed = 0
    for user in users:
        existing_status = existing_by_user.get(user.id)
        if existing_status is not None:
            if existing_status in {MailStatus.QUEUED.value, MailStatus.SENDING.value}:
                queued += 1
            elif existing_status == MailStatus.SENT.value:
                sent += 1
            elif existing_status == MailStatus.FAILED.value:
                failed += 1
            elif existing_status in {MailStatus.SUPPRESSED.value, MailStatus.CANCELLED.value}:
                suppressed += 1
            continue

        email = user.email.strip().lower()
        is_suppressed = user_is_suppressed(user, suppressed_user_ids, suppressed_emails)
        session.add(
            MailMessage(
                user_id=user.id,
                campaign_id=campaign.id,
                recipient_email=email,
                kind=MailKind.CAMPAIGN.value,
                subject=campaign.subject,
                body=campaign.body,
                body_html=campaign.body_html,
                status=(
                    MailStatus.SUPPRESSED.value
                    if is_suppressed
                    else MailStatus.QUEUED.value
                ),
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
    campaign.sent_count = sent
    campaign.failed_count = failed
    campaign.suppressed_count = suppressed
    campaign.launched_at = campaign.launched_at or current
    campaign.scheduled_at = None
    campaign.completed_at = None
    if queued:
        campaign.status = CampaignStatus.QUEUED.value
    elif failed:
        campaign.status = CampaignStatus.FAILED.value
        campaign.completed_at = current
    else:
        campaign.status = CampaignStatus.COMPLETED.value
        campaign.completed_at = current
    await session.flush()
    return campaign


async def due_scheduled_campaign_ids(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 10,
) -> list[UUID]:
    current = now or datetime.now(timezone.utc)
    result = await session.execute(
        select(MailCampaign.id)
        .where(
            MailCampaign.status == CampaignStatus.SCHEDULED.value,
            MailCampaign.scheduled_at.is_not(None),
            MailCampaign.scheduled_at <= current,
        )
        .order_by(MailCampaign.scheduled_at.asc())
        .limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().all())
