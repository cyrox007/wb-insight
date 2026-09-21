import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Database


class MailKind(str, enum.Enum):
    TRANSACTIONAL = "transactional"
    CAMPAIGN = "campaign"
    TEST = "test"


class MailStatus(str, enum.Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    CANCELLED = "cancelled"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailVerificationToken(Database.Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MailCampaign(Database.Base):
    __tablename__ = "mail_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=CampaignStatus.DRAFT.value, server_default=CampaignStatus.DRAFT.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    audience_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    scheduled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    launched_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    messages = relationship("MailMessage", back_populates="campaign")


class MailMessage(Database.Base):
    __tablename__ = "mail_messages"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_mail_messages_idempotency_key"),
        Index("ix_mail_messages_due", "status", "next_attempt_at", "created_at"),
        Index("ix_mail_messages_campaign_status", "campaign_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_campaigns.id", ondelete="CASCADE"), nullable=True
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=MailStatus.QUEUED.value, server_default=MailStatus.QUEUED.value)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    next_attempt_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_attempt_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    campaign = relationship("MailCampaign", back_populates="messages")


class MailSuppression(Database.Base):
    __tablename__ = "mail_suppressions"
    __table_args__ = (UniqueConstraint("email", name="uq_mail_suppressions_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default="unsubscribe", server_default="unsubscribe")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)



class MailProviderConfig(Database.Base):
    __tablename__ = "mail_provider_configs"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_mail_provider_configs_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="smtp")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587, server_default="587")
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    starttls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    encrypted_secrets: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
