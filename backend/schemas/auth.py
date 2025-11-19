import re
from pydantic import BaseModel, field_validator

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        Валидация email адреса
        
        Проверяет:
        - Соответствие базовому формату email
        - Приводит к нижнему регистру
        - Убирает лишние пробелы
        
        Args:
            v: Входной email
            
        Returns:
            str: Нормализованный email
            
        Raises:
            ValueError: Если email не соответствует формату
        """
        if not v:
            raise ValueError('Email cannot be empty')
        
        # Базовая проверка формата email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format. Example: user@example.com')
        
        return v.lower().strip()

class TokenResponse(BaseModel):
    status: str = "success"
    data: dict
    meta: dict

class TokenData(BaseModel):
    user_id: str
    email: str
    roles: list[str]

