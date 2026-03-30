"""Модуль вспомогательных функций для формирования ответов API."""

from datetime import datetime, timezone
from uuid import uuid4


def response_success(**kwargs) -> dict:
    """Формирует успешный ответ API.
    
    Args:
        **kwargs: Произвольные данные для включения в ответ.
        
    Returns:
        Словарь с форматом успешного ответа.
    """
    return {
        "status": "success",
        **kwargs,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": str(uuid4())
        }
    }


def response_error(code: str = '', message: str = '', details: dict | None = None, **kwargs) -> dict:
    """Формирует ответ с ошибкой API.
    
    Args:
        code: Код ошибки.
        message: Сообщение об ошибке.
        details: Детали ошибки.
        **kwargs: Дополнительные данные.
        
    Returns:
        Словарь с форматом ответа об ошибке.
    """
    if details is None:
        details = {}
    
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "details": details,
            **kwargs
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": str(uuid4())
        }
    }