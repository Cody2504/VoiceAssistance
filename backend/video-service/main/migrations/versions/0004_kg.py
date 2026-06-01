"""create entities + entity_mentions + entity_relations (Phase 2a knowledge graph)

Revision ID: 0004_kg
Revises: 0003_indexes
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004_kg"
down_revision = "0003_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column(
            "index_id",
            UUID(as_uuid=True),
            sa.ForeignKey("indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("canonical_name", sa.String(512), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        # Mirrors the point id in the jockey_entities Qdrant collection so we
        # can re-upsert without re-embedding when the description is updated.
        sa.Column("qdrant_point_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("index_id", "canonical_name", name="uq_entities_index_name"),
    )
    op.create_index("ix_entities_index_id", "entities", ["index_id"])
    op.create_index("ix_entities_type", "entities", ["entity_type"])

    op.create_table(
        "entity_mentions",
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment_idx", sa.Integer(), nullable=False),
        # Mirrors the per-segment point in jockey_segments_text — kept so
        # entity → segment expansion stays a single lookup.
        sa.Column("qdrant_point_id", UUID(as_uuid=True), nullable=False),
        sa.Column("t_start", sa.Float(), nullable=True),
        sa.Column("t_end", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.PrimaryKeyConstraint("entity_id", "video_id", "segment_idx"),
    )
    op.create_index("ix_entity_mentions_video", "entity_mentions", ["video_id"])

    op.create_table(
        "entity_relations",
        sa.Column("index_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "src_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dst_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        # JSONB list of source segment ids so we can cite where the relation
        # was observed when answering comparative queries (Phase 3).
        sa.Column("source_segment_ids", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint(
            "index_id", "src_entity_id", "dst_entity_id", "relation"
        ),
    )
    op.create_index("ix_entity_relations_index", "entity_relations", ["index_id"])


def downgrade() -> None:
    op.drop_table("entity_relations")
    op.drop_table("entity_mentions")
    op.drop_table("entities")
