"""add is_active to users (admin suspend support)

Revision ID: 0003_is_active
Revises: 0002_google_auth
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_is_active"
down_revision = "0002_google_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
