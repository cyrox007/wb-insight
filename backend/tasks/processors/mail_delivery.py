import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from celery_app import celery_app
from core.database_celery import get_session
from core.operation_context import (
    OperationContext,
    bind_operation_context,
    reset_operation_context,
)
from integrations.mail.rusender import RuSenderAPIError
from models.mail_delivery import CampaignStatus, MailCampaign, MailMessage
from services.mail_campaign_service import due_scheduled_campaign_ids, launch_campaign
from services.mail_service import (
    PermanentMailDeliveryError,
    deliver_message,
    due_message_ids,
    mark_message_failure,
    refresh_campaign_counters,
)
from services.mail_transport_service import get_mail_transport_runtime
from services.operation_log_service import persist_current_operation_event


def _delivery_failure(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, PermanentMailDeliveryError):
        return exc.code, True
    if isinstance(exc, RuSenderAPIError):
        return exc.safe_code, False
    return type(exc).__name__.lower(), False


async def _message_context(message_id) -> dict | None:
    session = await get_session()
    try:
        result = await session.execute(
            select(
                MailMessage.user_id,
                MailMessage.campaign_id,
                MailMessage.kind,
                MailMessage.template_code,
                MailMessage.recipient_email,
                MailMessage.attempt_count,
                MailMessage.max_attempts,
            ).where(MailMessage.id == message_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return {
            "user_id": row.user_id,
            "campaign_id": row.campaign_id,
            "kind": row.kind,
            "template_code": row.template_code,
            "recipient_email": row.recipient_email,
            "attempt_count": int(row.attempt_count or 0),
            "max_attempts": int(row.max_attempts or 0),
        }
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
    session = await get_session()
    try:
        runtime = await get_mail_transport_runtime(session)
        if not runtime.MAIL_DELIVERY_ENABLED or not runtime.ready:
            return {"launched": 0, "failed": 0}
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
        runtime = await get_mail_transport_runtime(session)
        if not runtime.ready:
            return {"processed": 0, "failed": 0}
        provider_code = runtime.MAIL_PROVIDER
        ids = await due_message_ids(
            session,
            include_marketing=runtime.MAIL_DELIVERY_ENABLED,
        )
    finally:
        await session.close()

    processed = failed = 0
    for message_id in ids:
        message_context = await _message_context(message_id)
        if message_context is None:
            continue

        operation_token = bind_operation_context(
            OperationContext(
                operation_id=message_id,
                actor_user_id=message_context["user_id"],
            )
        )
        await persist_current_operation_event(
            domain="mail",
            operation="mail_delivery",
            step="delivery_started",
            status="started",
            event_kind="background_job",
            component="mail_delivery_worker",
            direction="internal",
            user_id=message_context["user_id"],
            subject_type="mail_message",
            subject_id=message_id,
            provider=provider_code,
            message="Начата фоновая попытка доставки письма",
            input_data={
                "recipient_email": message_context["recipient_email"],
                "kind": message_context["kind"],
                "template_code": message_context["template_code"],
                "campaign_id": message_context["campaign_id"],
            },
            metrics={
                "attempt_count": message_context["attempt_count"] + 1,
                "max_attempts": message_context["max_attempts"],
            },
        )

        session = await get_session()
        try:
            delivery_status = await deliver_message(session, message_id)
            await session.commit()
            processed += 1
            await persist_current_operation_event(
                domain="mail",
                operation="mail_delivery",
                step="delivery_completed",
                status="success",
                event_kind="background_job",
                component="mail_delivery_worker",
                direction="internal",
                user_id=message_context["user_id"],
                subject_type="mail_message",
                subject_id=message_id,
                provider=provider_code,
                message="Фоновая попытка доставки письма завершена",
                output_data={"status": delivery_status},
            )
        except Exception as exc:
            # Сначала откатываем транзакцию: одноразовый токен, созданный для
            # неудачной попытки, должен исчезнуть вместе с её изменениями.
            await session.rollback()
            await session.close()
            session = await get_session()
            try:
                error_code, terminal = _delivery_failure(exc)
                delivery_status = await mark_message_failure(
                    session,
                    message_id,
                    error_code,
                    terminal=terminal,
                )
                await session.commit()
                await persist_current_operation_event(
                    domain="mail",
                    operation="mail_delivery",
                    step="delivery_failed",
                    status="failed" if terminal else "warning",
                    severity="error" if terminal else "warning",
                    event_kind="background_job",
                    component="mail_delivery_worker",
                    direction="internal",
                    user_id=message_context["user_id"],
                    subject_type="mail_message",
                    subject_id=message_id,
                    provider=provider_code,
                    error_code=error_code,
                    message="Почтовая доставка завершилась ошибкой",
                    output_data={
                        "status": delivery_status,
                        "terminal": terminal,
                    },
                )
            except Exception:
                await session.rollback()
            failed += 1
        finally:
            await session.close()
            reset_operation_context(operation_token)

        await _refresh_campaign(message_context["campaign_id"])

    return {"processed": processed, "failed": failed}


@celery_app.task(name="mail.campaign.scan")
def scan_scheduled_campaigns():
    return asyncio.run(_process_due_campaigns())


@celery_app.task(name="mail.delivery.scan")
def scan_mail_delivery():
    return asyncio.run(_process_due_mail())
