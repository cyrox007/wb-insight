from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.mail_delivery import MailSuppression
from services.user_service import get_user_by_uuid
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/account/mail", tags=["mail preferences"])


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
    result = await db_session.execute(select(MailSuppression).where(MailSuppression.email == email).with_for_update())
    suppression = result.scalar_one_or_none()
    if enabled:
        if suppression is not None:
            suppression.active = False
    else:
        if suppression is None:
            suppression = MailSuppression(
                user_id=user.id,
                email=email,
                reason="unsubscribe",
                active=True,
            )
            db_session.add(suppression)
        else:
            suppression.user_id = user.id
            suppression.reason = "unsubscribe"
            suppression.active = True
    await db_session.flush()
    return response_success(marketing_emails_enabled=enabled)
