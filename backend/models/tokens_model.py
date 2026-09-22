from datetime import datetime, timezone
from uuid import UUID as UUIDType, uuid4

from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database


class Marketplace(PyEnum):
    WILDBERRIES = "wildberries"
    OZON = "ozon"
    YANDEX_MARKET = "yandex_market"


class TokenTypeWB(PyEnum):
    """Документированные типы кабинетов JWT Wildberries."""

    BASE = "base"
    TEST = "test"
    PERSONAL = "personal"
    SERVICE = "service"


class APIToken(Database.Base):
    """
    Зашифрованные реквизиты кабинета маркетплейса.

    `encrypted_token` хранит секрет маркетплейса, например JWT Wildberries
    или API-ключ Ozon. `external_account_id` хранит несекретный идентификатор
    кабинета, когда API требует пару реквизитов, например Client-Id и Api-Key Ozon.
    """

    __tablename__ = "api_tokens"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Владелец реквизитов кабинета маркетплейса",
    )

    marketplace: Mapped[Marketplace] = mapped_column(
        Enum(Marketplace, name="marketplace_enum"),
        nullable=False,
        index=True,
        comment="Провайдер маркетплейса",
    )

    token_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Тип реквизитов или авторизации конкретного маркетплейса",
    )

    external_account_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Идентификатор продавца или кабинета на стороне маркетплейса; не является секретом",
    )

    encrypted_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Зашифрованный секрет маркетплейса",
    )

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Некоторые провайдеры, например JWT Wildberries, публикуют срок действия.
    # Другие реквизиты, например API-ключ Ozon, действуют до отзыва и поэтому
    # не имеют достоверной даты окончания.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="api_tokens")

    def __repr__(self):
        return (
            f"<ApiToken(id={self.id}, marketplace={self.marketplace}, "
            f"type={self.token_type}, external_account_id={self.external_account_id})>"
        )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_revoked and not self.is_expired
