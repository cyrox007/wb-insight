from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from integrations.mail.rusender import RuSenderAPIError
from models.mail_delivery import CampaignStatus, MailCampaign, MailMessage, MailStatus
from models.subscription_model import SubscriptionStatus
from models.tariffs_model import TariffPlan
from models.users_model import UserRole
from services.mail_campaign_service import (
    CampaignStateConflict,
    launch_campaign,
    preview_campaign_audience,
    schedule_campaign,
)
from services.mail_service import queue_test_email
from services.mail_transport_service import (
    get_mail_transport_runtime,
    mail_transport_payload,
    send_mail_transport_test,
    upsert_mail_transport,
)
from utils.mail_html import html_to_text, sanitize_mail_html
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
        "body_html": item.body_html,
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


async def _normalized_segment(
    db_session: AsyncSession,
    raw_segment: dict | None,
) -> dict:
    source = raw_segment if isinstance(raw_segment, dict) else {}
    segment: dict = {
        "verified_only": source.get("verified_only", True) is not False,
    }

    if isinstance(source.get("active"), bool):
        segment["active"] = source["active"]

    requested_roles = list(dict.fromkeys(
        str(value).strip().lower()
        for value in (source.get("roles") or [])
        if str(value).strip()
    ))
    valid_roles = {role.value for role in UserRole}
    unknown_roles = sorted(set(requested_roles) - valid_roles)
    if unknown_roles:
        raise ValueError("Неизвестные роли: " + ", ".join(unknown_roles))
    segment["roles"] = requested_roles

    tariff_result = await db_session.execute(
        select(TariffPlan.code).order_by(TariffPlan.name.asc())
    )
    available_codes = [str(code) for code in tariff_result.scalars().all()]
    tariff_map = {code.lower(): code for code in available_codes}
    requested_tariffs = list(dict.fromkeys(
        str(value).strip().lower()
        for value in (source.get("tariff_codes") or [])
        if str(value).strip()
    ))
    unknown_tariffs = sorted(code for code in requested_tariffs if code not in tariff_map)
    if unknown_tariffs:
        raise ValueError("Неизвестные тарифы: " + ", ".join(unknown_tariffs))
    segment["tariff_codes"] = [tariff_map[code] for code in requested_tariffs]

    valid_statuses = {item.value for item in SubscriptionStatus}
    requested_statuses = list(dict.fromkeys(
        str(value).strip().lower()
        for value in (source.get("subscription_statuses") or [])
        if str(value).strip()
    ))
    unknown_statuses = sorted(set(requested_statuses) - valid_statuses)
    if unknown_statuses:
        raise ValueError("Неизвестные статусы подписки: " + ", ".join(unknown_statuses))
    segment["subscription_statuses"] = requested_statuses
    return segment


def _campaign_content(payload: dict) -> tuple[str, str | None]:
    raw_html = str(payload.get("body_html") or "").strip()
    safe_html = sanitize_mail_html(raw_html) if raw_html else ""
    text_body = str(payload.get("body") or "").strip()
    if not text_body and safe_html:
        text_body = html_to_text(safe_html)
    if not text_body:
        raise ValueError("Добавьте содержимое письма")
    if len(text_body) > 100_000 or len(safe_html) > 200_000:
        raise ValueError("Письмо превышает допустимый размер")
    return text_body, safe_html or None


async def _require_campaign_delivery(
    response: Response,
    db_session: AsyncSession,
):
    payload = await mail_transport_payload(db_session)
    if payload.get("marketing_ready"):
        return None
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if not payload.get("ready"):
        message = "Почтовый шлюз не настроен или не готов к отправке"
    elif not payload.get("enabled"):
        message = "Пользовательские кампании отключены"
    elif not payload.get("unsubscribe_configured"):
        message = "Не настроен безопасный one-click unsubscribe для маркетинговых писем"
    else:
        message = "Почтовый шлюз не готов к маркетинговой отправке"
    return response_error(
        code="MAIL_DELIVERY_DISABLED",
        message=message,
    )


@router.get("/meta")
async def mail_meta(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    result = await db_session.execute(
        select(TariffPlan).order_by(TariffPlan.name.asc(), TariffPlan.code.asc())
    )
    tariffs = [
        {
            "id": str(item.id),
            "code": item.code,
            "name": item.name,
            "is_active": bool(item.is_active),
            "is_public": bool(item.is_public),
        }
        for item in result.scalars().all()
    ]
    permissions = set(getattr(request.state, "permissions", set()))
    return response_success(
        roles=[role.value for role in UserRole],
        tariffs=tariffs,
        subscription_statuses=[item.value for item in SubscriptionStatus],
        can_manage=Permission.MAIL_WRITE.value in permissions,
        gateway=await mail_transport_payload(db_session),
        editor={
            "rich_html": True,
            "image_source": "https_url",
            "max_html_bytes": 200_000,
        },
    )


@router.get("/gateway")
async def gateway_detail(
    db_session: AsyncSession = Depends(get_db_session),
):
    return response_success(gateway=await mail_transport_payload(db_session))


@router.put(
    "/gateway",
    dependencies=[Depends(require_permission(Permission.MAIL_WRITE))],
)
async def gateway_update(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Тело запроса должно быть объектом")
        await upsert_mail_transport(
            db_session,
            actor_id=UUID(str(request.state.user_id)),
            values=payload,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_GATEWAY_INVALID", message=str(exc))
    return response_success(gateway=await mail_transport_payload(db_session))


@router.post(
    "/gateway/test",
    dependencies=[Depends(require_permission(Permission.MAIL_WRITE))],
)
async def gateway_test(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        payload = await request.json()
        message_id = await send_mail_transport_test(
            db_session,
            recipient_email=str(payload.get("email") or ""),
        )
    except ValueError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_GATEWAY_TEST_INVALID", message=str(exc))
    except RuSenderAPIError as exc:
        response.status_code = status.HTTP_502_BAD_GATEWAY
        messages = {
            "rusender_http_401": "RuSender отклонил API token. Проверьте или перевыпустите токен.",
            "rusender_http_402": "RuSender сообщает, что лимит или баланс отправок исчерпан.",
            "rusender_http_403": "RuSender запретил отправку. Проверьте право external_mail.send и активность ключа отправки.",
            "rusender_http_404": "RuSender не нашёл ключ отправки или домен From. Проверьте Key ID и email отправителя.",
            "rusender_http_422": "RuSender не может доставлять на этот тестовый адрес.",
            "rusender_http_429": "Превышен лимит запросов RuSender. Повторите тест позже.",
            "rusender_http_503": "RuSender временно недоступен. Повторите тест позже.",
            "rusender_timeout": "RuSender не ответил вовремя. Повторите тест позже.",
            "rusender_network_error": "Не удалось подключиться к RuSender по HTTPS.",
        }
        details = {"transport_code": exc.code}
        if exc.provider_error_code:
            details["provider_error_code"] = exc.provider_error_code
        return response_error(
            code="MAIL_GATEWAY_TEST_FAILED",
            message=messages.get(exc.code, "RuSender не принял тестовое письмо."),
            details=details,
        )
    except Exception:
        response.status_code = status.HTTP_502_BAD_GATEWAY
        return response_error(
            code="MAIL_GATEWAY_TEST_FAILED",
            message="Почтовый провайдер не принял тестовое письмо. Проверьте настройки транспорта и credentials.",
        )
    return response_success(provider_message_id=message_id)


@router.post("/audience/preview")
async def audience_preview(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        body = await request.json()
        segment = await _normalized_segment(
            db_session,
            body.get("segment") if isinstance(body, dict) else None,
        )
    except ValueError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_SEGMENT_INVALID", message=str(exc))
    return response_success(**(await preview_campaign_audience(db_session, segment)))


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
    try:
        payload = await request.json()
        name = str(payload.get("name") or "").strip()
        subject = str(payload.get("subject") or "").strip()
        if not name or not subject:
            raise ValueError("Название кампании и тема письма обязательны")
        if len(subject) > 255:
            raise ValueError("Тема письма слишком длинная")
        body, body_html = _campaign_content(payload)
        segment = await _normalized_segment(db_session, payload.get("segment"))
    except ValueError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_CAMPAIGN_INVALID", message=str(exc))

    campaign = MailCampaign(
        name=name[:180],
        subject=subject,
        body=body,
        body_html=body_html,
        segment=segment,
        status=CampaignStatus.DRAFT.value,
        created_by=request.state.user_id,
    )
    db_session.add(campaign)
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.get("/campaigns/{campaign_id}")
async def campaign_detail(
    campaign_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    campaign = await db_session.get(MailCampaign, campaign_id)
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    return response_success(campaign=_campaign_item(campaign))


@router.put(
    "/campaigns/{campaign_id}",
    dependencies=[Depends(require_permission(Permission.MAIL_WRITE))],
)
async def campaign_update(
    campaign_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    campaign = await db_session.get(MailCampaign, campaign_id)
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    if campaign.status not in {CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value}:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="MAIL_CAMPAIGN_LOCKED",
            message="После запуска содержимое и аудиторию рассылки менять нельзя",
        )

    try:
        payload = await request.json()
        name = str(payload.get("name", campaign.name) or "").strip()
        subject = str(payload.get("subject", campaign.subject) or "").strip()
        if not name or not subject or len(subject) > 255:
            raise ValueError("Проверьте название кампании и тему письма")
        body_payload = {
            "body": payload.get("body", campaign.body),
            "body_html": payload.get("body_html", campaign.body_html),
        }
        body, body_html = _campaign_content(body_payload)
        segment = await _normalized_segment(
            db_session,
            payload.get("segment", campaign.segment or {}),
        )
    except ValueError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_CAMPAIGN_INVALID", message=str(exc))

    campaign.name = name[:180]
    campaign.subject = subject
    campaign.body = body
    campaign.body_html = body_html
    campaign.segment = segment
    await db_session.flush()
    return response_success(campaign=_campaign_item(campaign))


@router.post("/campaigns/{campaign_id}/preview")
async def campaign_preview(
    campaign_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
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
    disabled = await _require_campaign_delivery(response, db_session)
    if disabled is not None:
        return disabled
    campaign = await db_session.get(MailCampaign, campaign_id)
    if campaign is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="MAIL_CAMPAIGN_NOT_FOUND", message="Рассылка не найдена")
    payload = await request.json()
    email = str(payload.get("email") or "").strip().lower()
    if not email or "@" not in email or len(email) > 320:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="MAIL_TEST_EMAIL_INVALID", message="Укажите корректный email")
    message = await queue_test_email(
        db_session,
        recipient_email=email,
        subject=f"[TEST] {campaign.subject}",
        body=campaign.body,
        html_body=campaign.body_html,
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
    disabled = await _require_campaign_delivery(response, db_session)
    if disabled is not None:
        return disabled
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
async def campaign_launch(
    campaign_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    disabled = await _require_campaign_delivery(response, db_session)
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
async def campaign_cancel(
    campaign_id: UUID,
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
    result = await db_session.execute(
        query.order_by(MailMessage.created_at.desc()).offset(offset).limit(limit)
    )
    total = await db_session.scalar(count_query)
    return response_success(
        messages=[_message_item(item) for item in result.scalars().all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )
