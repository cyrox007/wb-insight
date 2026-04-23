from datetime import datetime
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import UUID as PG_UUID, ForeignKey, String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database

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

    token_id: Mapped[str] = mapped_column(   # 🔥 КЛЮЧЕВОЕ
        String(36),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    entity: Mapped[str] = mapped_column(     # stocks / realization
        String(50),
        index=True,
        nullable=False
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

    __table_args__ = (
        UniqueConstraint("user_id", "token_id", "entity", name="uq_sync_state"),
    )