"""Модуль аутентификации и регистрации пользователей."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.lifecycle_config import lifecycle_config
from core.logger import setup_logger
from core.session_cookie import set_refresh_cookie
from models.mail_delivery import MailSuppression
from schemas.auth import LoginRequest
from services.legal_service import LegalConsentError, record_consents, validate_consent_payload
from services.mail_service import queue_transactional_email
from services.mail_transport_service import get_mail_transport_runtime
from services.session_identity import session_user_payload
from services.subscription_service import create_demo_subscription
from services.tariff_service import get_tariff_by_code
from services.user_service import (
    create_user_role_association,
    get_user_by_email,
    get_user_by_inn,
    get_user_by_phone,
    insert_user,
)
from settings import config
from utils.hashed_password import verify_password
from utils.jwt import create_access_token, create_refresh_token
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/auth", tags=["authentication"])
logger = setup_logger(__name__)


class RegistrationAbort(Exception):
    """Управляемая ошибка атомарного блока регистрации."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def _materialize_registration(
    request: Request,
    db_session: AsyncSession,
    *,
    reg_data: dict,
    user_data: dict,
    legal_documents,
    legal_context: str,
):
    user = await insert_user(db_session, user_data)
    if user is None:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "REGISTRATION_ERROR",
            "Ошибка при регистрации",
        )

    role_created = await create_user_role_association(
        db_session,
        str(user.id),
        "user",
    )
    if not role_created:
        raise RegistrationAbort(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            "Ошибка при регистрации",
        )

    await record_consents(
        db_session,
        user_id=user.id,
        documents=legal_documents,
        context=legal_context,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        context_reference=str(user.id),
    )

    if reg_data.get("newsletter_subscription") is False:
        db_session.add(
            MailSuppression(
                user_id=user.id,
                email=user.email.strip().lower(),
                reason="registration_opt_out",
                active=True,
            )
        )
        await db_session.flush()

    demo = await get_tariff_by_code(db_session, "demo")
    if demo is None:
        raise RegistrationAbort(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            "Ошибка при регистрации",
        )

    if lifecycle_config.EMAIL_VERIFICATION_ENABLED:
        user.email_verified_at = None
        await queue_transactional_email(
            db_session,
            user=user,
            template_code="email_verification",
            idempotency_key=f"registration-verify:{user.id}",
        )
        return user

    user.email_verified_at = datetime.now(timezone.utc)
    await create_demo_subscription(db=db_session, user_id=user.id)
    return user


@router.post("/login")
async def login(login_data: LoginRequest, response: Response, db_session: AsyncSession = Depends(get_db_session)) -> dict:
    user = await get_user_by_email(db_session, login_data.email)
    if not user or not verify_password(login_data.password, str(user.hashed_password)):
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(code="INVALID_CREDENTIALS", message="Неверный email или пароль", details={})
    if not user.is_active:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(code="USER_INACTIVE", message="Аккаунт деактивирован", details={})
    if lifecycle_config.EMAIL_VERIFICATION_ENABLED and getattr(user, "email_verified_at", None) is None:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code="EMAIL_NOT_VERIFIED",
            message="Подтвердите email перед входом",
            details={"email_verification_required": True},
        )

    token_data = {"sub": str(user.id), "email": user.email, "sv": user.session_version}
    access_token = create_access_token(token_data)
    set_refresh_cookie(response, create_refresh_token(token_data))
    return response_success(
        access_token=access_token,
        token_type="bearer",
        expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=session_user_payload(user),
    )


@router.post("/check-email")
async def check_email(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)) -> dict:
    data = await request.json()
    if "email" not in data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="INVALID_REQUEST", message="Неверный запрос")
    user = await get_user_by_email(db_session, data["email"])
    if user:
        return response_error(code="EMAIL_ALREADY_EXISTS", message="Пользователь с таким Email уже зарегистрирован")
    return response_success(message="Email свободен")


@router.post("/check-phone")
async def check_phone(request: Request, db_session: AsyncSession = Depends(get_db_session)) -> dict:
    data = await request.json()
    user = await get_user_by_phone(db_session, data["phone"])
    if user:
        return response_error(code="PHONE_ALREADY_EXISTS", message="Пользователь с таким номером телефона уже зарегистрирован")
    return response_success(message="Номер телефона свободен")


@router.post("/check-inn")
async def check_inn(request: Request, db_session: AsyncSession = Depends(get_db_session)) -> dict:
    data = await request.json()
    user = await get_user_by_inn(db_session, data["inn"])
    if user:
        return response_error(code="INN_ALREADY_EXISTS", message="Пользователь с таким ИНН уже зарегистрирован")
    return response_success(message="ИНН свободен")


@router.post("/registration")
async def registration(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Создаёт аккаунт атомарно; demo-доступ выдаётся после проверки владения email."""
    data = await request.json()
    reg_data = data.get("registrationData") or {}
    legal_context = (
        "registration_legal"
        if reg_data.get("entity_type") == "legal_entity"
        else "registration"
    )

    if lifecycle_config.EMAIL_VERIFICATION_ENABLED:
        mail_runtime = await get_mail_transport_runtime(db_session)
        if not mail_runtime.ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return response_error(
                code="EMAIL_VERIFICATION_DELIVERY_UNAVAILABLE",
                message="Регистрация временно недоступна: сервис подтверждения email не готов",
            )

    try:
        legal_documents = validate_consent_payload(
            reg_data.get("legal_consents"),
            context=legal_context,
        )
    except LegalConsentError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code=exc.code, message=str(exc))

    user_data = {
        key: value
        for key, value in reg_data.items()
        if key not in {
            "legal_consents",
            "agree_terms",
            "agree_privacy",
            "agree_data_processing",
            "newsletter_subscription",
        }
    }

    try:
        async with db_session.begin_nested():
            user = await _materialize_registration(
                request,
                db_session,
                reg_data=reg_data,
                user_data=user_data,
                legal_documents=legal_documents,
                legal_context=legal_context,
            )
    except IntegrityError:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="REGISTRATION_CONFLICT",
            message="Email, телефон или другие уникальные данные уже используются",
        )
    except RegistrationAbort as exc:
        response.status_code = exc.status_code
        return response_error(code=exc.code, message=exc.message)

    if lifecycle_config.EMAIL_VERIFICATION_ENABLED:
        return response_success(
            message="Регистрация создана. Подтвердите email по ссылке из письма.",
            email_verification_required=True,
            email=user.email,
        )

    return response_success(
        message="Зарегистрирован",
        email_verification_required=False,
    )
