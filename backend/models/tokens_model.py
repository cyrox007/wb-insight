from datetime import datetime, timedelta, timezone
from uuid import uuid4

from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Boolean, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database import Database

class Marketplace(PyEnum):
    WILDBERRIES = "wildberries"
    OZON = "ozon"
    YANDEX_MARKET = "yandex_market"
    # добавите другие по мере необходимости


class TokenTypeWB(PyEnum):
    # Типы токенов Wildberries (можно расширять)
    PERSONAL = "personal"       # Персональный (старый тип)
    SERVICE = "service"         # Сервисный (новый, через кабинет)
    BASIC = "basic"             # Базовый (ограниченный)
    TEST = "test"               # Тестовый (если используется)


class APIToken(Database.Base):
    __tablename__ = 'api_tokens'

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid4())
    )

    # Привязка к пользователю
    user_id: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Маркетплейс
    marketplace: Mapped[Marketplace] = mapped_column(
        Enum(Marketplace, name='marketplace_enum'),
        nullable=False,
        index=True
    )

    # Тип токена (для WB — из(TokenTypeWB); для других — можно оставить NULL или использовать JSON/гибкое поле)
    token_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Зашифрованный токен (в продакшене — шифрование!)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)  # ← оригинальный токен в зашифрованном виде

    # Срок действия
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Дополнительно: описание (например, "Токен для аналитики")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Отношение (опционально)
    user = relationship("User", back_populates="api_tokens")

    def __repr__(self):
        return f"<ApiToken(id={self.id}, marketplace={self.marketplace}, type={self.token_type})>"
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_revoked and not self.is_expired

    # Метод для установки срока действия (например, 180 дней для WB)
    def set_expires_for_wb(self):
        """Устанавливает срок действия на 180 дней от issued_at"""
        if self.issued_at:
            self.expires_at = self.issued_at + timedelta(days=180)
        else:
            now = datetime.now(timezone.utc)
            self.issued_at = now
            self.expires_at = now + timedelta(days=180)