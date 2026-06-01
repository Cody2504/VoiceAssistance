"""add parent_video_id + offset_s to videos (chunked long-video ingest, Option B)

Revision ID: 0005_video_chunks
Revises: 0004_kg
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0005_video_chunks"
down_revision = "0004_kg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A long video uploaded via POST /api/v1/videos/chunked is split into
    # time-windowed child videos. `parent_video_id` groups the chunks (a logical
    # id, no FK row required); `offset_s` is the chunk's start time in the full
    # source so retrieval can reconstruct global time (global_t = offset_s + local_t).
    op.add_column("videos", sa.Column("parent_video_id", PG_UUID(as_uuid=True), nullable=True))
    op.add_column("videos", sa.Column("offset_s", sa.Float(), nullable=True))
    op.create_index("ix_videos_parent_video_id", "videos", ["parent_video_id"])


def downgrade() -> None:
    op.drop_index("ix_videos_parent_video_id", table_name="videos")
    op.drop_column("videos", "offset_s")
    op.drop_column("videos", "parent_video_id")
