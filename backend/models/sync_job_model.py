from datetime import datetime
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import JSON, UUID as PG_UUID, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column


from core.database import Database

class SyncJob(Database.Base):
    __tablename__ = "sync_jobs"

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

    token_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    entity: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",  # pending / processing / done / failed
        index=True
    )

    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))