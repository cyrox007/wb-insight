from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.mail_delivery import MailSuppression
from services.mail_unsubscribe_service import parse_unsubscribe_token
from services.user_service import get_user_by_uuid
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/account/mail", tags=["mail preferences"])


async def _suppress_marketing(
    db_session: AsyncSession,
    *,
    email: str,
    user_id: UUID | None,
) -> None:
    normalized = str(email or "").strip().lower()
    result = await db_session.execute(
        select(MailSuppression)
        .where(MailSuppression.email == normalized)
        .with_for_update()
    )
    suppression = result.scalar_one_or_none()
    if suppression is None:
        suppression = MailSuppression(
            user_id=user_id,
            email=normalized,
            reason="unsubscribe",
            active=True,
        )
        db_session.add(suppression)
    else:
        if user_id is not None:
            suppression.user_id = user_id
        suppression.reason = "unsubscribe"
        suppression.active = True
    await db_session.flush()


@router.post("/unsubscribe/{token}")
async def one_click_unsubscribe(
    token: str,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        identity = parse_unsubscribe_token(token)
        if identity.list_id != "marketing":
            raise ValueError("unsubscribe_list_invalid")
        user_id = UUID(identity.user_id) if identity.user_id else None
    except (ValueError, TypeError):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="UNSUBSCRIBE_TOKEN_INVALID",
            message="Ссылка отписки недействительна",
        )

    await _suppress_marketing(
        db_session,
        email=identity.email,
        user_id=user_id,
    )
    return response_success(unsubscribed=True)


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_landing(
    token: str,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        identity = parse_unsubscribe_token(token)
        if identity.list_id != "marketing":
            raise ValueError("unsubscribe_list_invalid")
        user_id = UUID(identity.user_id) if identity.user_id else None
        await _suppress_marketing(
            db_session,
            email=identity.email,
            user_id=user_id,
        )
        return HTMLResponse(
            "<!doctype html><html lang='ru'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Отписка · WB Insight</title>"
            "<body style='font-family:Arial,sans-serif;background:#f5f6fb;color:#182033;"
            "padding:40px'><main style='max-width:620px;margin:auto;background:white;"
            "padding:32px;border-radius:16px'><h1>Рассылка отключена</h1>"
            "<p>Вы больше не будете получать маркетинговые письма WB Insight.</p>"
            "<p>Системные письма о безопасности аккаунта и восстановлении доступа "
            "останутся доступными.</p></main></body></html>"
        )
    except (ValueError, TypeError):
        return HTMLResponse(
            "<!doctype html><html lang='ru'><meta charset='utf-8'>"
            "<title>Отписка · WB Insight</title><body style='font-family:Arial,sans-serif;"
            "padding:40px'><h1>Ссылка недействительна</h1>"
            "<p>Используйте ссылку из последнего письма WB Insight.</p></body></html>",
            status_code=400,
        )



@router.get("/preferences", dependencies=[Depends(auth_middle)])
async def get_preferences(request: Request, db_session: AsyncSession = Depends(get_db_session)):
    user_id = UUID(str(request.state.user["sub"]))
    user = await get_user_by_uuid(db_session, user_id)
    if user is None:
        return response_error(code="USER_NOT_FOUND", message="Пользователь не найден")
    result = await db_session.execute(
        select(MailSuppression).where(MailSuppression.email == user.email.strip().lower())
    )
    suppression = result.scalar_one_or_none()
    enabled = suppression is None or not suppression.active
    return response_success(marketing_emails_enabled=enabled)


@router.put("/preferences", dependencies=[Depends(auth_middle)])
async def update_preferences(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    user_id = UUID(str(request.state.user["sub"]))
    user = await get_user_by_uuid(db_session, user_id)
    if user is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="USER_NOT_FOUND", message="Пользователь не найден")
    body = await request.json()
    enabled = body.get("marketing_emails_enabled")
    if not isinstance(enabled, bool):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="marketing_emails_enabled должен быть boolean")

    email = user.email.strip().lower()
    result = await db_session.execute(
        select(MailSuppression)
        .where(MailSuppression.email == email)
        .with_for_update()
    )
    suppression = result.scalar_one_or_none()
    if enabled:
        if suppression is not None:
            suppression.active = False
            await db_session.flush()
    else:
        await _suppress_marketing(
            db_session,
            email=email,
            user_id=user.id,
        )
    return response_success(marketing_emails_enabled=enabled)
