from datetime import datetime
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import UUID as PG_UUID, ForeignKey, String, DateTime, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.users_model import User

class UserSyncState(Database.Base):
    __tablename__ = "user_sync_states"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    entity: Mapped[str] = mapped_column(     # stocks / realization
        String(50),
        index=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Дата создания"
    )

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="sync_states",
        lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "entity", name="uq_sync_state"),
    )