"""sber acquiring foundation

Revision ID: a1c4e8f2b730
Revises: f3b1c9d7a620
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1c4e8f2b730"
down_revision: Union[str, Sequence[str], None] = "f3b1c9d7a620"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing enum is shared by the Payment model. Add Sber without replacing
    # the type so old rows and constraints remain intact.
    op.execute("ALTER TYPE payment_provider ADD VALUE IF NOT EXISTS 'sber'")

    op.add_column(
        "payments",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
            comment="Client payment-attempt idempotency key; unique per user/provider",
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "provider_status",
            sa.String(length=64),
            nullable=True,
            comment="Last normalized provider status",
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the provider was server-side confirmed as paid",
        ),
    )
    op.alter_column(
        "payments",
        "currency",
        existing_type=sa.String(),
        type_=sa.String(length=3),
        existing_nullable=False,
    )
    op.alter_column(
        "payments",
        "external_payment_id",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="Provider-side order/payment identifier",
        existing_comment=None,
    )
    op.alter_column(
        "payments",
        "provider_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
        comment="Non-secret provider metadata needed for reconciliation",
        existing_comment=None,
    )
    op.create_unique_constraint(
        "uq_payments_user_provider_idempotency",
        "payments",
        ["user_id", "provider", "idempotency_key"],
    )
    op.create_index(
        "ix_payments_external_payment_id",
        "payments",
        ["external_payment_id"],
        unique=False,
    )

    op.add_column(
        "subscriptions",
        sa.Column(
            "payment_id",
            sa.UUID(),
            nullable=True,
            comment="Confirmed payment that activated this subscription",
        ),
    )
    op.create_unique_constraint(
        "uq_subscriptions_payment_id",
        "subscriptions",
        ["payment_id"],
    )
    op.create_foreign_key(
        "fk_subscriptions_payment_id_payments",
        "subscriptions",
        "payments",
        ["payment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column(
            "event_type",
            sa.String(length=64),
            nullable=False,
            comment="Internal event name, e.g. registered/status_checked/callback",
        ),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("provider_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_events_payment_id"),
        "payment_events",
        ["payment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_events_payment_id"), table_name="payment_events")
    op.drop_table("payment_events")

    op.drop_constraint(
        "fk_subscriptions_payment_id_payments",
        "subscriptions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_subscriptions_payment_id",
        "subscriptions",
        type_="unique",
    )
    op.drop_column("subscriptions", "payment_id")

    op.drop_index("ix_payments_external_payment_id", table_name="payments")
    op.drop_constraint(
        "uq_payments_user_provider_idempotency",
        "payments",
        type_="unique",
    )
    op.alter_column(
        "payments",
        "provider_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
        comment=None,
        existing_comment="Non-secret provider metadata needed for reconciliation",
    )
    op.alter_column(
        "payments",
        "external_payment_id",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment=None,
        existing_comment="Provider-side order/payment identifier",
    )
    op.alter_column(
        "payments",
        "currency",
        existing_type=sa.String(length=3),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.drop_column("payments", "confirmed_at")
    op.drop_column("payments", "provider_status")
    op.drop_column("payments", "idempotency_key")

    # PostgreSQL cannot drop an enum value in place. Rebuild the enum for a
    # true downgrade. Sber payments cannot exist in a schema that predates Sber;
    # fail the downgrade rather than silently relabel financial records.
    bind = op.get_bind()
    sber_count = bind.execute(
        sa.text("SELECT count(*) FROM payments WHERE provider::text = 'sber'")
    ).scalar_one()
    if sber_count:
        raise RuntimeError("Cannot downgrade while Sber payment rows exist")

    op.execute("ALTER TABLE payments ALTER COLUMN provider TYPE text USING provider::text")
    op.execute("DROP TYPE payment_provider")
    old_provider = postgresql.ENUM(
        "fake",
        "yookassa",
        name="payment_provider",
    )
    old_provider.create(bind, checkfirst=False)
    op.execute(
        "ALTER TABLE payments ALTER COLUMN provider TYPE payment_provider "
        "USING provider::payment_provider"
    )
