import asyncio

from sqlalchemy import select

from celery_app import celery_app
from core.database_celery import get_session
from models.mail_delivery import MailMessage
from services.mail_service import (
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


async def _process_due_mail() -> dict[str, int]:
    if not celery_app.conf.get("mail_delivery_enabled", True):
        return {"processed": 0, "failed": 0}

    session = await get_session()
    try:
        ids = await due_message_ids(session)
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
                await mark_message_failure(session, message_id, type(exc).__name__.lower())
                await session.commit()
            except Exception:
                await session.rollback()
            failed += 1
        finally:
            await session.close()
        await _refresh_campaign(campaign_id)

    return {"processed": processed, "failed": failed}


@celery_app.task(name="mail.delivery.scan")
def scan_mail_delivery():
    return asyncio.run(_process_due_mail())
