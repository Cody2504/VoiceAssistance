"""add content-moderation guardrail columns to videos

Revision ID: 0007_moderation
Revises: 0006_timeline
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_moderation"
down_revision = "0006_timeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("nsfw_max", sa.Float(), nullable=True))
    op.add_column("videos", sa.Column("violence_max", sa.Float(), nullable=True))
    op.add_column("videos", sa.Column("toxic_max", sa.Float(), nullable=True))
    op.add_column("videos", sa.Column("moderation_labels", sa.String(128), nullable=True))
    op.add_column("videos", sa.Column("moderation_detail", JSONB(), nullable=True))
    op.add_column(
        "videos",
        sa.Column("moderation_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("videos", "moderation_override")
    op.drop_column("videos", "moderation_detail")
    op.drop_column("videos", "moderation_labels")
    op.drop_column("videos", "toxic_max")
    op.drop_column("videos", "violence_max")
    op.drop_column("videos", "nsfw_max")
