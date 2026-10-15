"""Добавляет неизменяемый операционный журнал диагностики.

Revision ID: b8e1c4d7f260
Revises: a6d4f8c2e951
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8e1c4d7f260"
down_revision: Union[str, Sequence[str], None] = "a6d4f8c2e951"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operation_log_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("step", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), server_default=sa.text("'info'"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("event_kind", sa.String(length=32), server_default=sa.text("'business_step'"), nullable=False),
        sa.Column("component", sa.String(length=96), nullable=True),
        sa.Column("direction", sa.String(length=16), server_default=sa.text("'internal'"), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=True),
        sa.Column("subject_id", sa.String(length=160), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("input_data", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("output_data", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("metrics", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("context_data", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operation_log_operation_created",
        "operation_log_events",
        ["operation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_user_created",
        "operation_log_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_domain_created",
        "operation_log_events",
        ["domain", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_status_created",
        "operation_log_events",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_subject_created",
        "operation_log_events",
        ["subject_type", "subject_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_request_id",
        "operation_log_events",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_request_sequence",
        "operation_log_events",
        ["request_id", "sequence_no"],
        unique=False,
    )
    op.create_index(
        "ix_operation_log_component_created",
        "operation_log_events",
        ["component", "created_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION wb_reject_operation_log_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'operation_log_events допускает только добавление записей';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_operation_log_events_append_only
        BEFORE UPDATE OR DELETE ON operation_log_events
        FOR EACH ROW EXECUTE FUNCTION wb_reject_operation_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_operation_log_events_append_only ON operation_log_events"
    )
    op.execute("DROP FUNCTION IF EXISTS wb_reject_operation_log_mutation()")
    op.drop_index("ix_operation_log_component_created", table_name="operation_log_events")
    op.drop_index("ix_operation_log_request_sequence", table_name="operation_log_events")
    op.drop_index("ix_operation_log_request_id", table_name="operation_log_events")
    op.drop_index("ix_operation_log_subject_created", table_name="operation_log_events")
    op.drop_index("ix_operation_log_status_created", table_name="operation_log_events")
    op.drop_index("ix_operation_log_domain_created", table_name="operation_log_events")
    op.drop_index("ix_operation_log_user_created", table_name="operation_log_events")
    op.drop_index("ix_operation_log_operation_created", table_name="operation_log_events")
    op.drop_table("operation_log_events")