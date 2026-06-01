"""create indexes + index_videos

Revision ID: 0003_indexes
Revises: 0002_modality_and_summary
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_indexes"
down_revision = "0002_modality_and_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indexes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_indexes_user_id", "indexes", ["user_id"])

    op.create_table(
        "index_videos",
        sa.Column(
            "index_id",
            UUID(as_uuid=True),
            sa.ForeignKey("indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("index_id", "video_id"),
    )
    op.create_index("ix_index_videos_order", "index_videos", ["index_id", "position"])
    op.create_index("ix_index_videos_video_id", "index_videos", ["video_id"])


def downgrade() -> None:
    op.drop_table("index_videos")
    op.drop_table("indexes")
