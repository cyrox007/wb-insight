from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from settings import config


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT access-токена."""
    to_encode = data.copy()
    expire = (
        datetime.now(timezone.utc) + expires_delta
        if expires_delta
        else datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.pop("type", None)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Создание JWT refresh-токена."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Верификация JWT токена."""
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    except JWTError:
        return None
