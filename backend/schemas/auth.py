import re

from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Проверяет формат email, удаляет внешние пробелы и приводит к lowercase."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email не может быть пустым")

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, normalized):
            raise ValueError(
                "Некорректный формат email. Пример: user@example.com"
            )

        return normalized


class TokenResponse(BaseModel):
    status: str = "success"
    data: dict
    meta: dict


class TokenData(BaseModel):
    user_id: str
    email: str
    roles: list[str]
