"""add modality + global_summary columns to videos

Revision ID: 0002_modality_and_summary
Revises: 0001_videos
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_modality_and_summary"
down_revision = "0001_videos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("modality", sa.String(16), nullable=True))
    op.add_column("videos", sa.Column("has_video", sa.Boolean(), nullable=True))
    op.add_column("videos", sa.Column("has_audio", sa.Boolean(), nullable=True))
    op.add_column("videos", sa.Column("global_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "global_summary")
    op.drop_column("videos", "has_audio")
    op.drop_column("videos", "has_video")
    op.drop_column("videos", "modality")
