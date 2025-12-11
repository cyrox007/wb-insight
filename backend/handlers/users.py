import traceback
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Response, status

from core.dependencies import get_db_session
from core.logger import setup_logger
from schemas.users import UserCreateRequest
from services.user_service import get_user_by_email, get_user_by_phone, insert_user, set_user_role


routers = APIRouter(prefix="/users", tags=["users"])

logger = setup_logger(__name__)

@routers.get('/')
async def get_users(db_session: AsyncSession = Depends(get_db_session)):
    # print(db_session)
    return {}

@routers.post('/create', status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Создание нового пользователя в системе
    
    Принимает валидированные данные пользователя, проверяет уникальность
    email и телефона, сохраняет пользователя в базу данных.
    
    Args:
        user_data: Валидированные данные пользователя
        db_session: Сессия базы данных (внедряется декоратором)
        
    Returns:
        dict: Результат операции с данными созданного пользователя
        
    Raises:
        HTTPException: При ошибках валидации или проблемах с БД
    """
    try:
        existing_user_by_email = await get_user_by_email(session=db_session, email=user_data.email)
        existing_user_by_phone = await get_user_by_phone(session=db_session, phone=user_data.phone)

        if existing_user_by_email or existing_user_by_phone:
            error_detail = "User with this email already exists" if existing_user_by_email else "User with this phone already exists"
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                "status": "error",
                "error": {
                    "code": "USER_ALREADY_EXISTS",
                    "message": "Пользователь уже существует в системе",
                    "details": {
                        "email": user_data.email if existing_user_by_email else None,
                        "phone": user_data.phone if existing_user_by_phone else None
                    }
                },
                "meta": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "request_id": str(uuid4())
                }
            }
        
        user = await insert_user(db_session, user_data)
        await set_user_role(db_session, user, 'user')
        
        return {
            "status": "success",
            "data": {
                "user_id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": str(uuid4())
            }
        }
        
    except Exception as e:
        logger.error(f"Unexpected error creating user: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return {
            "status": "error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Внутренняя ошибка сервера",
                "details": {
                    "reason": str(e)
                }
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": str(uuid4())
            }
        }