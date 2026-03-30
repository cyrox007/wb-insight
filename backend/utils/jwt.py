"""Модуль управления JWT токенами.

Предоставляет функции для создания и верификации JWT токенов.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

from settings import config


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание access токена.
    
    Args:
        data: Данные для кодирования в токене.
        expires_delta: Время жизни токена. Если не указано, используется значение из конфига.
        
    Returns:
        Закодированный JWT токен.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(seconds=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Создание refresh токена.
    
    Args:
        data: Данные для кодирования в токене.
        
    Returns:
        Закодированный JWT refresh токен.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Верификация JWT токена.
    
    Args:
        token: JWT токен для проверки.
        
    Returns:
        Расшифрованные данные токена или None если токен невалиден.
    """
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        return None