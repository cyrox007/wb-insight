from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import permissions_for_roles
from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.marketplace_access_service import (
    get_allowed_wb_tokens,
    get_wb_account_quota,
)
from services.subscription_service import get_user_subscription
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


def _public_token(token, *, dashboard_available: bool | None = None) -> dict:
    data = {
        "id": str(token.id),
        "label": token.label,
        "marketplace": token.marketplace.value,
        "token_type": token.token_type,
        "issued_at": token.issued_at,
        "expires_at": token.expires_at,
        "is_active": token.is_active,
        "is_revoked": token.is_revoked,
        "is_valid": token.is_valid,
    }
    if dashboard_available is not None:
        data["dashboard_available"] = dashboard_available
    return data


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
    role_codes = [role.role for role in current_user.roles]
    permission_codes = sorted(
        permission.value for permission in permissions_for_roles(role_codes)
    )

    return response_success(
        tokens=[
            _public_token(token, dashboard_available=token.id in allowed_ids)
            for token in user_tokens
        ],
        user={
            "id": str(current_user.id),
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "entity_type": current_user.entity_type,
            "tax_rate": float(current_user.tax_rate or 0),
            "timezone": current_user.timezone,
            "is_active": current_user.is_active,
            "roles": role_codes,
            "permissions": permission_codes,
            "created_at": current_user.created_at,
        },
        subscription=None if not subscription else {
            "tariff_name": subscription.tariff.name,
            "status": subscription.status.value,
            "start_date": subscription.current_period_start,
            "end_date": subscription.current_period_end,
            "is_active": subscription.is_active,
        },
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

    token = await insert_token(
        session=db_session,
        user_id=user_id,
        raw_token=raw_token,
        marketplace_code="wb",
        token_type=data.get("token_type") or "personal",
        label=data.get("label") or "Wildberries",
    )
    if token is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TOKEN_CREATE_ERROR",
            message="Не удалось сохранить токен",
        )

    return response_success(
        token=_public_token(token, dashboard_available=True)
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

    if not await delete_token(db_session, token):
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response_error(
            code="INTERNAL_SERVER_ERROR",
            message="Ошибка при удалении токена",
        )

    return response_success(message="Токен удалён")
