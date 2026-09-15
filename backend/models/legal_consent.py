from datetime import datetime
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Database


class LegalConsent(Database.Base):
    """Immutable evidence that a user accepted a concrete legal document version."""

    __tablename__ = "legal_consents"

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_code: Mapped[str] = mapped_column(String(64), nullable=False)
    document_version: Mapped[str] = mapped_column(String(32), nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[str] = mapped_column(String(32), nullable=False)
    context_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_legal_consents_user_id", "user_id"),
        Index(
            "ix_legal_consents_document",
            "document_code",
            "document_version",
        ),
        Index("ix_legal_consents_context", "context", "accepted_at"),
    )
