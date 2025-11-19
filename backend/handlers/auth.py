from datetime import datetime
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Response, status

from core.dependencies import get_db_session
from core.logger import setup_logger

from schemas.auth import LoginRequest, TokenResponse
from services.user_service import get_user_by_email, get_user_roles
from utils.hashed_password import verify_password
from utils.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = setup_logger(__name__)

@router.post("/login")
async def login(
    login_data: LoginRequest,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session)
):   
    user = await get_user_by_email(db_session, login_data.email)
    if not user:
        response.status_code = status.HTTP_403_FORBIDDEN
        return {
            "status": "error",
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Неверный email или пароль",
                "details": {}
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": str(uuid4())
            }
        }
    
    if not verify_password(login_data.password, str(user.hashed_password)):
        response.status_code = status.HTTP_403_FORBIDDEN
        return {
            "status": "error",
            "error": {
                "code": "INVALID_CREDENTIALS", 
                "message": "Неверный email или пароль",
                "details": {}
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": str(uuid4())
            }
        }
    
    if not bool(user.is_active):
        response.status_code = status.HTTP_403_FORBIDDEN
        return {
            "status": "error",
            "error": {
                "code": "USER_INACTIVE",
                "message": "Аккаунт деактивирован",
                "details": {}
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": str(uuid4())
            }
        }
    
    # 4. Получаем роли пользователя
    
    roles = await get_user_roles(db_session, user)

    # 5. Создаем токены
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "roles": roles
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "roles": roles
            }
        },
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": str(uuid4())
        }
    }