from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class OperationLogEvent(Database.Base):
    """Неизменяемый шаг бизнес-операции для технической диагностики."""

    __tablename__ = "operation_log_events"
    __table_args__ = (
        Index("ix_operation_log_operation_created", "operation_id", "created_at"),
        Index("ix_operation_log_user_created", "user_id", "created_at"),
        Index("ix_operation_log_domain_created", "domain", "created_at"),
        Index("ix_operation_log_status_created", "status", "created_at"),
        Index("ix_operation_log_subject_created", "subject_type", "subject_id", "created_at"),
        Index("ix_operation_log_request_id", "request_id"),
        Index("ix_operation_log_request_sequence", "request_id", "sequence_no"),
        Index("ix_operation_log_component_created", "component", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    operation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    parent_operation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    step: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="info",
        server_default=text("'info'"),
    )
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="business_step",
        server_default=text("'business_step'"),
    )
    component: Mapped[str | None] = mapped_column(String(96), nullable=True)
    direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="internal",
        server_default=text("'internal'"),
    )
    subject_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    output_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    metrics: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    context_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )