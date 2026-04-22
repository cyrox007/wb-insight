from datetime import datetime, timedelta, timezone
from typing import Optional, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request, Response, status

from core.dependencies import get_db_session, require_permission
from core.logger import setup_logger
from core.middleware import auth_middle
from services.subscription_service import get_user_subscription
from services.tariff_service import get_tariff_by_id
from utils.responce_helps import response_error, response_success

from services.user_service import get_user_by_uuid
from services.token_services import get_tokens_by_user_id, get_user_token_count, insert_token, get_token_by_id, delete_token

router = APIRouter(prefix="/dashboard/profile", tags=["dashboard.profile"])
logger = setup_logger(__name__)

def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "*" * 8 + token[-4:]

@router.get("/", dependencies=[Depends(auth_middle)])
async def get_profile(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    current_user = await get_user_by_uuid(
        session=db_session,
        user_id=cast(UUID, request.state.user['sub'])
    )
    if current_user is None:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="UNAUTHORIZED",
            message="Неавторизован"
        )
    
    subscription = await get_user_subscription(
        db_session,
        cast(UUID, request.state.user['sub'])
    )

    user_tokens = await get_tokens_by_user_id(
        db_session, cast(UUID, request.state.user['sub'])
    )

    return response_success(
        tokens=[
            {
                "id": str(token.id),
                "label": token.label,
                "marketplace": token.marketplace,
                "encrypted_token": mask_token(token.encrypted_token),
                "issued_at": token.issued_at,
                "expires_at": token.expires_at
            }
            for token in user_tokens
        ],
        user={
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,

            "entity_type": current_user.entity_type,
            "tax_rate": float(current_user.tax_rate or 0),
            "timezone": current_user.timezone,

            "is_active": current_user.is_active,

            "roles": [r.role for r in current_user.roles],

            "created_at": current_user.created_at,
        },
        subscription = None if not subscription else {
            "tariff_name": subscription.tariff.name,
            "status": subscription.status,
            "start_date": subscription.current_period_start,
            "end_date": subscription.current_period_end,
            "is_active": subscription.status in ["active", "demo"]
        }
    )

@router.get("/check-token-permission/{user_id}", dependencies=[Depends(auth_middle)])
async def check_token_permission(
    user_id: UUID,
    tariff_id: Optional[UUID] = None, 
    db_session: AsyncSession = Depends(get_db_session)
):
    current_user = await get_user_by_uuid(db_session, user_id)
    if current_user is None:
        return response_error(
            code="USER_NOT_FOUND", 
            message='Пользователь не найден'
        )

    # проверим является ли наш тариф демо
    if tariff_id is None: # id тарифа не указано значит у нас демо тариф 
        # получим дату регистрации пользователя
        created_at = current_user.created_at 
        if created_at.tzinfo is None:
            # Если в БД хранится naive datetime — считаем его UTC
            created_at = created_at.replace(tzinfo=timezone.utc)

        demo_expires_at = created_at + timedelta(days=7)
        now = datetime.now(timezone.utc)
        
        if now > demo_expires_at: # type: ignore
            return response_error(
                code="DEMO_EXPIRED",
                message="Демо-период истёк. Пожалуйста, подключите тариф."
            )
        
        # надо проверить еще, если демо период не истек, то мы можем добавить только один токен
        # если он уже добавлен то мы не можем добавить еще один
        if await get_user_token_count(db_session, user_id) >= 1:
            return response_error(
                code="TOKEN_LIMIT_EXCEEDED",
                message="Вы достигли лимита токенов. Пожалуйста, подключите тариф."
            )
        
        # если мы дошли до этого места, значит у нас есть демо период и мы можем добавить 1 токен, проверка завершена, ответим фронтенду что можно добавлять
        return response_success(
            can_add_token=True
        )
        
    # дальше проверки если у нас не демо
    # в первую очередь нам надо проверить наш тариф и какие у нас есть разрешения на нем
    tariff = await get_tariff_by_id(db_session, tariff_id)

    print(tariff.__dict__)

    return response_success(
        can_add_token=True
    )


@router.post('/token/add', status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_middle)])
async def add_token(request: Request, db_session: AsyncSession = Depends(get_db_session)):
    data = await request.json()
    token = await insert_token(
        session=db_session,
        user_id=request.state.user.sub,
        raw_token=data.get('token'),
        marketplace_code='wb',
        token_type=data.get('token_type'),
        label=data.get('label')
    )

    return response_success(
        token=token
    )

@router.delete('/token/{token_id}', dependencies=[Depends(auth_middle)])
async def delete_user_token(token_id: UUID, request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    token = await get_token_by_id(db_session, token_id)

    if token is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="TOKEN_NOT_FOUND",
            message="Токен не найден"
        )
    
    if token.user_id != request.state.user["sub"]:
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code="TOKEN_NOT_FOUND",
            message="Токен не найден"
        )
    
    if await delete_token(db_session, token) == False:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response_error(
            code="INTERNAL_SERVER_ERROR",
            message="Ошибка при удалении токена"
        )
    
    return response_success(
        message="Токен удален"
    )
