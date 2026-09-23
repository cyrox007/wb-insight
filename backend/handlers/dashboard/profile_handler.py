from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import permissions_for_roles
from core.dependencies import get_db_session
from core.middleware import auth_middle
from integrations.wildberries.token_metadata import WBTokenValidationError
from models.users_model import EntityType
from services.legal_service import (
    LegalConsentError,
    record_consents,
    validate_consent_payload,
)
from services.marketplace_access_service import (
    get_allowed_wb_tokens,
    get_wb_account_quota,
)
from services.subscription_service import get_user_subscription
from services.sync_onboarding_service import bootstrap_token_sync
from services.token_services import (
    delete_token,
    get_token_by_id,
    get_tokens_by_user_id,
    insert_token,
)
from services.user_service import get_user_by_uuid
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/profile", tags=["dashboard.profile"])


def _current_user_id(request: Request) -> UUID:
    return UUID(str(request.state.user["sub"]))


def _token_connection_status(
    token,
    *,
    dashboard_available: bool | None = None,
) -> str:
    """Возвращает безопасную причину доступности подключения Wildberries."""
    if token.is_revoked:
        return "revoked"

    expires_at = getattr(token, "expires_at", None)
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return "expired"

    if not token.is_active:
        return "inactive"
    if dashboard_available is False:
        return "outside_tariff"
    return "active"


def _public_token(token, *, dashboard_available: bool | None = None) -> dict:
    data = {
        "id": str(token.id),
        "label": token.label,
        "marketplace": token.marketplace.value,
        "token_type": token.token_type,
        "external_account_id": getattr(token, "external_account_id", None),
        "issued_at": token.issued_at,
        "expires_at": token.expires_at,
        "is_active": token.is_active,
        "is_revoked": token.is_revoked,
        "is_valid": token.is_valid,
        "connection_status": _token_connection_status(
            token,
            dashboard_available=dashboard_available,
        ),
    }
    if dashboard_available is not None:
        data["dashboard_available"] = dashboard_available
    return data


def _public_user(user) -> dict:
    role_codes = [role.role for role in user.roles]
    permission_codes = sorted(
        permission.value for permission in permissions_for_roles(role_codes)
    )
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "entity_type": user.entity_type,
        "tax_rate": float(user.tax_rate or 0),
        "timezone": user.timezone,
        "is_active": user.is_active,
        "roles": role_codes,
        "permissions": permission_codes,
        "created_at": user.created_at,
    }


@router.get("/", dependencies=[Depends(auth_middle)])
async def get_profile(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    user_id = _current_user_id(request)
    current_user = await get_user_by_uuid(db_session, user_id)
    if current_user is None:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(code="UNAUTHORIZED", message="Неавторизован")

    subscription = await get_user_subscription(db_session, user_id)
    user_tokens = await get_tokens_by_user_id(db_session, user_id)
    allowed_ids = {token.id for token in await get_allowed_wb_tokens(db_session, user_id)}

    return response_success(
        tokens=[
            _public_token(token, dashboard_available=token.id in allowed_ids)
            for token in user_tokens
        ],
        user=_public_user(current_user),
        subscription=None if not subscription else {
            "id": str(subscription.id),
            "tariff_name": subscription.tariff.name,
            "status": subscription.status.value,
            "start_date": subscription.current_period_start,
            "end_date": subscription.current_period_end,
            "is_active": subscription.is_active,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "cancel_requested_at": subscription.cancel_requested_at,
        },
    )


@router.put("/", dependencies=[Depends(auth_middle)])
async def update_profile(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Обновляет безопасные self-service настройки продавца."""
    user_id = _current_user_id(request)
    current_user = await get_user_by_uuid(db_session, user_id)
    if current_user is None:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(code="UNAUTHORIZED", message="Неавторизован")

    try:
        payload = await request.json()
    except (TypeError, ValueError):
        payload = None

    if not isinstance(payload, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="PROFILE_PAYLOAD_INVALID",
            message="Ожидается JSON-объект настроек профиля",
        )

    allowed_fields = {"full_name", "tax_rate", "timezone", "entity_type"}
    unsupported_fields = sorted(set(payload) - allowed_fields)
    if unsupported_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="PROFILE_FIELDS_UNSUPPORTED",
            message="Запрос профиля содержит неподдерживаемые поля",
        )

    if "entity_type" in payload:
        requested_entity_type = str(payload.get("entity_type") or "").strip().lower()
        allowed_entity_types = {item.value for item in EntityType}
        if requested_entity_type not in allowed_entity_types:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code="ENTITY_TYPE_INVALID",
                message="Некорректный тип продавца",
            )
        if requested_entity_type != current_user.entity_type:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code="ENTITY_TYPE_CHANGE_REQUIRES_ADMIN",
                message=(
                    "Тип продавца меняется только через административную проверку "
                    "юридических реквизитов"
                ),
            )

    full_name = str(payload.get("full_name", current_user.full_name) or "").strip()
    if not full_name or len(full_name) > 255:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Укажите имя или название компании",
        )

    try:
        tax_rate = float(payload.get("tax_rate", current_user.tax_rate or 0))
    except (TypeError, ValueError):
        tax_rate = -1
    if tax_rate < 0 or tax_rate > 1:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Налоговая ставка должна быть от 0 до 100%",
        )

    timezone_name = str(payload.get("timezone", current_user.timezone) or "").strip()
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Некорректный часовой пояс",
        )

    current_user.full_name = full_name
    current_user.tax_rate = tax_rate
    current_user.timezone = timezone_name
    await db_session.flush()

    return response_success(
        user=_public_user(current_user),
        message="Настройки продавца сохранены",
    )


@router.get(
    "/check-token-permission/{user_id}",
    dependencies=[Depends(auth_middle)],
)
async def check_token_permission(
    user_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    current_user_id = _current_user_id(request)
    if user_id != current_user_id:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code="FORBIDDEN",
            message="Нельзя проверять лимиты другого пользователя",
        )

    quota = await get_wb_account_quota(db_session, current_user_id)
    if not quota["allowed"]:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code=quota["code"] or "TOKEN_LIMIT_EXCEEDED",
            message="Достигнут лимит кабинетов Wildberries для текущего тарифа",
            limit=quota["limit"],
            used=quota["used"],
        )

    return response_success(
        can_add_token=True,
        limit=quota["limit"],
        used=quota["used"],
    )


@router.post(
    "/token/add",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_middle)],
)
async def add_token(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Сохраняет совместимость со старым маршрутом подключения Wildberries."""
    user_id = _current_user_id(request)
    quota = await get_wb_account_quota(db_session, user_id)
    if not quota["allowed"]:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code=quota["code"] or "TOKEN_LIMIT_EXCEEDED",
            message="Достигнут лимит кабинетов Wildberries для текущего тарифа",
            limit=quota["limit"],
            used=quota["used"],
        )

    data = await request.json()
    raw_token = str(data.get("token") or "").strip()
    if not raw_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="Токен обязателен")

    try:
        legal_documents = validate_consent_payload(
            data.get("legal_consents"),
            context="marketplace_credential",
        )
    except LegalConsentError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code=exc.code, message=str(exc))

    try:
        token = await insert_token(
            session=db_session,
            user_id=user_id,
            raw_token=raw_token,
            marketplace_code="wb",
            label=data.get("label") or "Wildberries",
        )
    except WBTokenValidationError as exc:
        response.status_code = exc.status_code
        return response_error(code=exc.code, message=str(exc))

    await record_consents(
        db_session,
        user_id=user_id,
        documents=legal_documents,
        context="marketplace_credential",
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        context_reference=str(token.id),
    )

    sync_states_created, sync_jobs_created = await bootstrap_token_sync(
        session=db_session,
        user_id=user_id,
        token_id=token.id,
    )

    return response_success(
        token=_public_token(token, dashboard_available=True),
        message="Кабинет Wildberries подключён. Первичная синхронизация поставлена в очередь.",
        sync={
            "states_created": sync_states_created,
            "jobs_created": sync_jobs_created,
        },
    )


@router.delete("/token/{token_id}", dependencies=[Depends(auth_middle)])
async def delete_user_token(
    token_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    user_id = _current_user_id(request)
    token = await get_token_by_id(db_session, token_id)

    if token is None or token.user_id != user_id:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="TOKEN_NOT_FOUND", message="Токен не найден")

    await delete_token(db_session, token)
    return response_success(message="Токен удалён")
