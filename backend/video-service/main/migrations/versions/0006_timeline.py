"""create timeline_tracks + timeline_segments (standing event timeline)

Revision ID: 0006_timeline
Revises: 0005_video_chunks
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_timeline"
down_revision = "0005_video_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "timeline_tracks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("video_id", UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_timeline_tracks_video", "timeline_tracks", ["video_id"])

    op.create_table(
        "timeline_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("track_id", UUID(as_uuid=True), sa.ForeignKey("timeline_tracks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("t_start", sa.Float(), nullable=False),
        sa.Column("t_end", sa.Float(), nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("qdrant_point_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_timeline_segments_track", "timeline_segments", ["track_id"])
    op.create_index("ix_timeline_segments_video", "timeline_segments", ["video_id"])


def downgrade() -> None:
    op.drop_table("timeline_segments")
    op.drop_table("timeline_tracks")
