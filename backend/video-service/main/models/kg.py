"""Knowledge-graph ORM models — entities, mentions, relations.

Per-index. An Entity is the canonical "softmax" / "attention" / "Prof. Nguyễn"
that may be discussed across multiple videos. EntityMention links the entity to
a specific Qdrant segment point so we can expand a graph hit back into evidence.
EntityRelation captures LLM-extracted "X is-a-form-of Y" / "X applied-in Y" edges
scoped to the same index (a relation only makes sense inside one course).
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from cm_shared.db import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    index_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    qdrant_point_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    video_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    segment_idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    qdrant_point_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    t_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")


class EntityRelation(Base):
    __tablename__ = "entity_relations"

    index_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    src_entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dst_entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(256), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    source_segment_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
