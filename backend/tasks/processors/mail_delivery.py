import asyncio

from celery_app import celery_app
from core.database_celery import get_session
from models.mail_delivery import MailMessage
from services.mail_service import deliver_message, due_message_ids, refresh_campaign_counters
from sqlalchemy import select


async def _process_due_mail() -> dict[str, int]:
    if not celery_app.conf.get("mail_delivery_enabled", True):
        return {"processed": 0}

    session = await get_session()
    try:
        ids = await due_message_ids(session)
    finally:
        await session.close()

    processed = 0
    for message_id in ids:
        session = await get_session()
        campaign_id = None
        try:
            result = await session.execute(select(MailMessage.campaign_id).where(MailMessage.id == message_id))
            campaign_id = result.scalar_one_or_none()
            await deliver_message(session, message_id)
            if campaign_id is not None:
                await refresh_campaign_counters(session, campaign_id)
            await session.commit()
            processed += 1
        except Exception:
            await session.rollback()
        finally:
            await session.close()
    return {"processed": processed}


@celery_app.task(name="mail.delivery.scan")
def scan_mail_delivery():
    return asyncio.run(_process_due_mail())
