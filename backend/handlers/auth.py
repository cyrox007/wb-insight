from datetime import datetime
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request, Response, status

from core.dependencies import get_db_session
from core.logger import setup_logger

from schemas.auth import LoginRequest
from services.user_service import get_user_by_email, get_user_by_inn, get_user_by_phone, insert_user
from utils.hashed_password import verify_password
from utils.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, create_refresh_token, verify_token
from utils.responce_helps import response_error, response_success

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
        return response_error(
            code="INVALID_CREDENTIALS",
            message="Неверный email или пароль",
            details={}
        )
    
    if not verify_password(login_data.password, str(user.hashed_password)):
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code="INVALID_CREDENTIALS",
            message="Неверный email или пароль",
            details={}
        )
    
    if not bool(user.is_active):
        response.status_code = status.HTTP_403_FORBIDDEN
        return response_error(
            code="USER_INACTIVE",
            message="Аккаунт деактивирован",
            details={}
        )
    
    # 4. Получаем роли пользователя
    # roles = await get_user_roles(db_session, user)

    tariff = None

    # 5. Создаем токены
    token_data = {
        "sub": str(user.id),
        "email": user.email
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Только по HTTPS в production
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # в секундах
        path="/auth/refresh"  # Доступно только для эндпоинта refresh
    )
    return response_success(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            'tariff': tariff,
            "roles": user.roles
        }
    )

@router.get('/refresh')
async def refresh_token(request: Request, response: Response):
    refresh_token = request.cookies.get('refresh_token')
    
    if not refresh_token:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="INVALID_TOKEN",
            message="Токен не найден",
            details={}
        )
    
    pyload = verify_token(refresh_token)

    if not pyload:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response_error(
            code="INVALID_TOKEN",
            message="Неверный токен",
            details={}
        )
    
    access_token = create_access_token(pyload)
    refresh_token = create_refresh_token(pyload)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Только по HTTPS в production
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # в секундах
        path="/auth/refresh"  # Доступно только для эндпоинта refresh
    )
    return response_success(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.post('/check-email')
async def check_email(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    allow_fields = ['email']
    if not allow_fields in await request.json():
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="INVALID_REQUEST",
            message="Неверный запрос"
        )
    data = await request.json()

    user = await get_user_by_email(db_session, data['email'])
    if user:
        return response_error(
            code="EMAIL_ALREADY_EXISTS",
            message="Пользователь с таким Email уже зарегестрирован"
        )

    return response_success(
        message="Email свободен"
    )

@router.post('/check-phone')
async def check_phone(request: Request, db_session: AsyncSession = Depends(get_db_session)):
    data = await request.json()

    user = await get_user_by_phone(db_session, data['phone'])
    if user:
        return response_error(
            code="PHONE_ALREADY_EXISTS",
            message="Пользователь с таким номером телефона уже зарегестрирован"
        )
    
    return response_success(
        message="Номер телефона свободен"
    )

@router.post('/check-inn')
async def check_inn(request: Request, db_session: AsyncSession = Depends(get_db_session)):
    data = await request.json()

    user = await get_user_by_inn(db_session, data['inn'])
    if user: 
        return response_error(
            code="INN_ALREADY_EXISTS",
            message="Пользователь с таким ИНН уже зарегестрирован"
        )
    
    return response_success(
        message="ИНН свободен"
    )

@router.post('/registration')
async def registration(request: Request, db_session: AsyncSession = Depends(get_db_session)):
    data = await request.json()
    regData = data.get('registrationData')

    user = await insert_user(db_session, data.get('registrationData', None))
    if not user:
        return response_error(
            code="REGISTRATION_ERROR",
            message="Ошибка при регистрации"
        )

    return response_success(message='Зарегестрирован')