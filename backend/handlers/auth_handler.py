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
from models.users_model import EntityType
from schemas.auth import LoginRequest
from services.legal_service import LegalConsentError, record_consents, validate_consent_payload
from services.mail_service import queue_transactional_email
from services.mail_transport_service import get_mail_transport_runtime
from services.session_identity import session_user_payload
from services.subscription_service import create_demo_subscription
from services.tariff_service import get_tariff_by_code
from services.user_identity import (
    normalize_email as _normalize_email_preflight,
    normalize_inn as _normalize_inn_preflight,
    normalize_phone as _normalize_phone_preflight,
)
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


router = APIRouter(prefix="/auth", tags=["Аутентификация"])
logger = setup_logger(__name__)


class RegistrationAbort(Exception):
    """Управляемая ошибка атомарного блока регистрации."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def _request_json_object(request: Request) -> dict | None:
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_registration_identity_conflict(exc: IntegrityError) -> bool:
    """Определяет только известные конфликты уникальности регистрационных идентификаторов."""
    known_constraints = (
        "ix_users_email",
        "users_email_key",
        "uq_users_email_lower",
        "ix_users_phone",
        "users_phone_key",
        "idx_users_phone_email_unique",
        "uq_users_inn_normalized",
    )
    original = getattr(exc, "orig", None)
    sources = (
        original,
        getattr(original, "__cause__", None),
    )

    for source in sources:
        if source is None:
            continue
        constraint_name = getattr(source, "constraint_name", None)
        if constraint_name in known_constraints:
            return True

        diagnostic = getattr(source, "diag", None)
        diagnostic_name = getattr(diagnostic, "constraint_name", None)
        if diagnostic_name in known_constraints:
            return True

    error_text = str(original or "").lower()
    return any(constraint in error_text for constraint in known_constraints)


def _validated_registration_data(payload: dict | None) -> tuple[dict, dict, str]:
    if not isinstance(payload, dict):
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "REGISTRATION_PAYLOAD_INVALID",
            "Ожидается JSON-объект регистрации",
        )

    reg_data = payload.get("registrationData")
    if not isinstance(reg_data, dict):
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "REGISTRATION_DATA_INVALID",
            "Поле registrationData должно быть объектом",
        )

    allowed_fields = {
        "entity_type",
        "full_name",
        "email",
        "phone",
        "password",
        "inn",
        "kpp",
        "legal_address",
        "timezone",
        "newsletter_subscription",
        "agree_terms",
        "agree_privacy",
        "agree_data_processing",
        "legal_consents",
    }
    unsupported_fields = sorted(set(reg_data) - allowed_fields)
    if unsupported_fields:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "REGISTRATION_FIELDS_UNSUPPORTED",
            "Запрос регистрации содержит неподдерживаемые поля",
        )

    entity_type = str(reg_data.get("entity_type") or "").strip().lower()
    allowed_entity_types = {item.value for item in EntityType}
    if entity_type not in allowed_entity_types:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "ENTITY_TYPE_INVALID",
            "Укажите корректный тип пользователя",
        )

    full_name = reg_data.get("full_name")
    if not isinstance(full_name, str) or not full_name.strip():
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "FULL_NAME_REQUIRED",
            "Укажите ФИО или название организации",
        )
    if len(full_name.strip()) > 255:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "FULL_NAME_INVALID",
            "ФИО или название организации не должно превышать 255 символов",
        )

    email = _normalize_email_preflight(reg_data.get("email"))
    if email is None:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "EMAIL_INVALID",
            "Укажите корректный email",
        )

    phone = _normalize_phone_preflight(reg_data.get("phone"))
    if phone is None:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "PHONE_INVALID",
            "Укажите корректный номер телефона",
        )

    password = reg_data.get("password")
    if not isinstance(password, str) or len(password) < 8:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "PASSWORD_INVALID",
            "Пароль должен содержать минимум 8 символов",
        )
    if len(password.encode("utf-8")) > 72:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "PASSWORD_TOO_LONG",
            "Пароль не должен превышать 72 байта в кодировке UTF-8",
        )

    if (
        "newsletter_subscription" in reg_data
        and not isinstance(reg_data["newsletter_subscription"], bool)
    ):
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "NEWSLETTER_FLAG_INVALID",
            "Поле newsletter_subscription должно быть логическим значением",
        )

    raw_inn = reg_data.get("inn")
    inn = ""
    if raw_inn is not None and raw_inn != "":
        inn = _normalize_inn_preflight(raw_inn) or ""
        expected_inn_length = 10 if entity_type == EntityType.LEGAL_ENTITY.value else 12
        if len(inn) != expected_inn_length:
            raise RegistrationAbort(
                status.HTTP_400_BAD_REQUEST,
                "INN_INVALID",
                (
                    "ИНН юридического лица должен содержать 10 цифр"
                    if entity_type == EntityType.LEGAL_ENTITY.value
                    else "ИНН физического лица или ИП должен содержать 12 цифр"
                ),
            )

    if entity_type == EntityType.LEGAL_ENTITY.value and not inn:
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "INN_REQUIRED",
            "ИНН обязателен для юридического лица",
        )

    raw_kpp = reg_data.get("kpp")
    kpp = ""
    if raw_kpp is not None and raw_kpp != "":
        if not isinstance(raw_kpp, str):
            raise RegistrationAbort(
                status.HTTP_400_BAD_REQUEST,
                "KPP_INVALID",
                "КПП должен содержать 9 цифр",
            )
        kpp = raw_kpp.strip()
        if not kpp.isdigit() or len(kpp) != 9:
            raise RegistrationAbort(
                status.HTTP_400_BAD_REQUEST,
                "KPP_INVALID",
                "КПП должен содержать 9 цифр",
            )

    legal_address = reg_data.get("legal_address")
    if (
        entity_type == EntityType.LEGAL_ENTITY.value
        and (not isinstance(legal_address, str) or not legal_address.strip())
    ):
        raise RegistrationAbort(
            status.HTTP_400_BAD_REQUEST,
            "LEGAL_ADDRESS_REQUIRED",
            "Юридический адрес обязателен для юридического лица",
        )

    timezone_value = reg_data.get("timezone")
    if timezone_value is not None and timezone_value != "":
        if not isinstance(timezone_value, str) or len(timezone_value.strip()) > 50:
            raise RegistrationAbort(
                status.HTTP_400_BAD_REQUEST,
                "TIMEZONE_INVALID",
                "Некорректный часовой пояс",
            )

    normalized = dict(reg_data)
    normalized.update(
        {
            "entity_type": entity_type,
            "full_name": full_name.strip(),
            "email": email,
            "phone": phone,
            "inn": inn or None,
            "kpp": kpp or None,
            "legal_address": (
                legal_address.strip()
                if isinstance(legal_address, str) and legal_address.strip()
                else None
            ),
            "timezone": (
                timezone_value.strip()
                if isinstance(timezone_value, str) and timezone_value.strip()
                else "Europe/Moscow"
            ),
        }
    )

    persisted_fields = {
        "entity_type",
        "full_name",
        "email",
        "phone",
        "password",
        "inn",
        "kpp",
        "legal_address",
        "timezone",
    }
    user_data = {
        key: normalized.get(key)
        for key in persisted_fields
    }
    legal_context = (
        "registration_legal"
        if entity_type == EntityType.LEGAL_ENTITY.value
        else "registration"
    )
    return normalized, user_data, legal_context


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
async def check_email(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    data = await _request_json_object(request)
    email = _normalize_email_preflight(data.get("email") if data else None)
    if email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="EMAIL_INVALID",
            message="Укажите корректный email",
        )

    user = await get_user_by_email(db_session, email)
    if user:
        return response_error(
            code="EMAIL_ALREADY_EXISTS",
            message="Пользователь с таким email уже зарегистрирован",
        )
    return response_success(message="Email свободен")


@router.post("/check-phone")
async def check_phone(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    data = await _request_json_object(request)
    phone = _normalize_phone_preflight(data.get("phone") if data else None)
    if phone is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="PHONE_INVALID",
            message="Укажите корректный номер телефона",
        )

    user = await get_user_by_phone(db_session, phone)
    if user:
        return response_error(
            code="PHONE_ALREADY_EXISTS",
            message="Пользователь с таким номером телефона уже зарегистрирован",
        )
    return response_success(message="Номер телефона свободен")


@router.post("/check-inn")
async def check_inn(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    data = await _request_json_object(request)
    inn = _normalize_inn_preflight(data.get("inn") if data else None)
    if inn is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="INN_INVALID",
            message="ИНН должен содержать 10 или 12 цифр",
        )

    user = await get_user_by_inn(db_session, inn)
    if user:
        return response_error(
            code="INN_ALREADY_EXISTS",
            message="Пользователь с таким ИНН уже зарегистрирован",
        )
    return response_success(message="ИНН свободен")


@router.post("/registration")
async def registration(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Создаёт аккаунт атомарно; demo-доступ выдаётся после проверки владения email."""
    data = await _request_json_object(request)
    try:
        reg_data, user_data, legal_context = _validated_registration_data(data)
    except RegistrationAbort as exc:
        response.status_code = exc.status_code
        return response_error(code=exc.code, message=exc.message)

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
    except IntegrityError as exc:
        if not _is_registration_identity_conflict(exc):
            raise
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="REGISTRATION_CONFLICT",
            message="Email, телефон или ИНН уже используются другим аккаунтом",
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
