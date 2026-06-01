"""create billing tables + seed plans

Revision ID: 0001_billing
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_billing"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("stripe_price_id", sa.String(64), nullable=True),
        sa.Column("monthly_index_minutes", sa.Integer, nullable=True),
        sa.Column("monthly_search_queries", sa.Integer, nullable=True),
        sa.Column("monthly_ground_calls", sa.Integer, nullable=True),
        sa.Column("monthly_qa_calls", sa.Integer, nullable=True),
        sa.Column("monthly_summary_calls", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.String(32), sa.ForeignKey("plans.id"), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Seed the three tiers so they line up with frontend pricingData.ts TIERS.
    # Free caps mirror ITEMS.freeMonthly; developer/enterprise are unlimited (NULL).
    plans = sa.table(
        "plans",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("stripe_price_id", sa.String),
        sa.column("monthly_index_minutes", sa.Integer),
        sa.column("monthly_search_queries", sa.Integer),
        sa.column("monthly_ground_calls", sa.Integer),
        sa.column("monthly_qa_calls", sa.Integer),
        sa.column("monthly_summary_calls", sa.Integer),
    )
    op.bulk_insert(
        plans,
        [
            {
                "id": "free", "name": "Free", "stripe_price_id": None,
                "monthly_index_minutes": 300, "monthly_search_queries": 1000,
                "monthly_ground_calls": 100, "monthly_qa_calls": 200, "monthly_summary_calls": 50,
            },
            {
                "id": "developer", "name": "Developer", "stripe_price_id": None,
                "monthly_index_minutes": None, "monthly_search_queries": None,
                "monthly_ground_calls": None, "monthly_qa_calls": None, "monthly_summary_calls": None,
            },
            {
                "id": "enterprise", "name": "Enterprise", "stripe_price_id": None,
                "monthly_index_minutes": None, "monthly_search_queries": None,
                "monthly_ground_calls": None, "monthly_qa_calls": None, "monthly_summary_calls": None,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("billing_webhook_events")
    op.drop_table("subscriptions")
    op.drop_table("plans")
