"""durable append-only audit events

Revision ID: e4a7b2c9d105
Revises: d1f6a3b9c742
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4a7b2c9d105"
down_revision: Union[str, Sequence[str], None] = "d1f6a3b9c742"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_roles", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=160), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=96), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), server_default=sa.text("'api'"), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("client_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)
    op.create_index("ix_audit_events_actor_created", "audit_events", ["actor_user_id", "created_at"], unique=False)
    op.create_index("ix_audit_events_action_created", "audit_events", ["action", "created_at"], unique=False)
    op.create_index("ix_audit_events_target_created", "audit_events", ["target_type", "target_id", "created_at"], unique=False)
    op.create_index("ix_audit_events_result_created", "audit_events", ["result", "created_at"], unique=False)
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"], unique=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION wb_reject_audit_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION wb_reject_audit_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS wb_reject_audit_event_mutation()")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_result_created", table_name="audit_events")
    op.drop_index("ix_audit_events_target_created", table_name="audit_events")
    op.drop_index("ix_audit_events_action_created", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_created", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
