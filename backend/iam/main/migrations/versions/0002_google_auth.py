"""add google_sub and make password_hash nullable

Revision ID: 0002_google_auth
Revises: 0001_users
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_google_auth"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Social-only users (Google sign-in) have no local password.
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
    # NOTE: will fail if any rows have a NULL password_hash (Google-only users).
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
