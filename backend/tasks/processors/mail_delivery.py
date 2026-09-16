import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from celery_app import celery_app
from core.database_celery import get_session
from core.lifecycle_config import lifecycle_config
from models.mail_delivery import CampaignStatus, MailCampaign, MailMessage
from services.mail_campaign_service import due_scheduled_campaign_ids, launch_campaign
from services.mail_service import (
    PermanentMailDeliveryError,
    deliver_message,
    due_message_ids,
    mark_message_failure,
    refresh_campaign_counters,
)


async def _campaign_id(message_id):
    session = await get_session()
    try:
        result = await session.execute(select(MailMessage.campaign_id).where(MailMessage.id == message_id))
        return result.scalar_one_or_none()
    finally:
        await session.close()


async def _refresh_campaign(campaign_id) -> None:
    if campaign_id is None:
        return
    session = await get_session()
    try:
        await refresh_campaign_counters(session, campaign_id)
        await session.commit()
    except Exception:
        await session.rollback()
    finally:
        await session.close()


async def _process_due_campaigns() -> dict[str, int]:
    if not lifecycle_config.MAIL_DELIVERY_ENABLED:
        return {"launched": 0, "failed": 0}

    session = await get_session()
    try:
        campaign_ids = await due_scheduled_campaign_ids(session)
    finally:
        await session.close()

    launched = failed = 0
    for campaign_id in campaign_ids:
        session = await get_session()
        try:
            result = await session.execute(
                select(MailCampaign)
                .where(MailCampaign.id == campaign_id)
                .with_for_update()
            )
            campaign = result.scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if (
                campaign is None
                or campaign.status != CampaignStatus.SCHEDULED.value
                or campaign.scheduled_at is None
                or campaign.scheduled_at > now
            ):
                await session.rollback()
                continue
            await launch_campaign(session, campaign, now=now)
            await session.commit()
            launched += 1
        except Exception:
            await session.rollback()
            failed += 1
        finally:
            await session.close()

    return {"launched": launched, "failed": failed}


async def _process_due_mail() -> dict[str, int]:
    if not celery_app.conf.get("mail_delivery_enabled", True):
        return {"processed": 0, "failed": 0}

    session = await get_session()
    try:
        ids = await due_message_ids(
            session,
            include_marketing=lifecycle_config.MAIL_DELIVERY_ENABLED,
        )
    finally:
        await session.close()

    processed = failed = 0
    for message_id in ids:
        campaign_id = await _campaign_id(message_id)
        session = await get_session()
        try:
            await deliver_message(session, message_id)
            await session.commit()
            processed += 1
        except Exception as exc:
            # Roll back first: if a one-time token was minted for this attempt it
            # disappears together with the failed delivery transaction.
            await session.rollback()
            await session.close()
            session = await get_session()
            try:
                terminal = isinstance(exc, PermanentMailDeliveryError)
                error_code = exc.code if terminal else type(exc).__name__.lower()
                await mark_message_failure(
                    session,
                    message_id,
                    error_code,
                    terminal=terminal,
                )
                await session.commit()
            except Exception:
                await session.rollback()
            failed += 1
        finally:
            await session.close()
        await _refresh_campaign(campaign_id)

    return {"processed": processed, "failed": failed}


@celery_app.task(name="mail.campaign.scan")
def scan_scheduled_campaigns():
    return asyncio.run(_process_due_campaigns())


@celery_app.task(name="mail.delivery.scan")
def scan_mail_delivery():
    return asyncio.run(_process_due_mail())
