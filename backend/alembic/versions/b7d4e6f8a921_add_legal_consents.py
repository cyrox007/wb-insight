"""add legal consent evidence

Revision ID: b7d4e6f8a921
Revises: a1c4e8f2b730
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7d4e6f8a921"
down_revision: Union[str, Sequence[str], None] = "a1c4e8f2b730"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_code", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column("context", sa.String(length=32), nullable=False),
        sa.Column("context_reference", sa.String(length=128), nullable=True),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip_hmac", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hmac", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_consents_user_id", "legal_consents", ["user_id"])
    op.create_index(
        "ix_legal_consents_document",
        "legal_consents",
        ["document_code", "document_version"],
    )
    op.create_index(
        "ix_legal_consents_context",
        "legal_consents",
        ["context", "accepted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_legal_consents_context", table_name="legal_consents")
    op.drop_index("ix_legal_consents_document", table_name="legal_consents")
    op.drop_index("ix_legal_consents_user_id", table_name="legal_consents")
    op.drop_table("legal_consents")
