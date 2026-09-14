from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database

if TYPE_CHECKING:
    from models.tokens_model import APIToken
    from models.users_model import User


class UserSyncState(Database.Base):
    __tablename__ = "user_sync_states"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="кому принадлежит состояние",
    )
    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="кабинет/credential, к которому относится состояние",
    )
    entity: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="тип синхронизируемых данных",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="когда создано состояние",
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="последняя попытка синхронизации",
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="последняя успешная синхронизация",
    )
    source_cursor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="последняя ошибка синхронизации",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="sync_states",
        lazy="selectin",
    )
    token: Mapped["APIToken"] = relationship("APIToken", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "token_id", "entity", name="uq_sync_state"),
    )
