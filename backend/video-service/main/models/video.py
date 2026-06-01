from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from cm_shared.db import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    minio_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration_s: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued", index=True)
    shot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Modality routing: populated at ingest by ffprobe. `modality` is the
    # high-level label used by the frontend to gate visual / audio tiles;
    # `has_video` and `has_audio` are the raw stream flags from ffprobe.
    modality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    has_video: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_audio: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Global one-shot summary used by the Analyze tile to give the LLM a
    # whole-video skeleton; per-window summaries live in Qdrant payloads.
    global_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Long-video chunking (Option B): a video uploaded via POST /videos/chunked
    # is split into time-windowed child videos that each fit GPU memory + the
    # per-job timeout. `parent_video_id` groups the chunks (a logical grouping
    # id, not a FK to a row); `offset_s` is the chunk's start time in the full
    # source so retrieval can reconstruct global timestamps (global_t =
    # offset_s + local_t). Both NULL for ordinary single-file uploads.
    parent_video_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    offset_s: Mapped[float | None] = mapped_column(nullable=True)


class IndexingJob(Base):
    __tablename__ = "indexing_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    video_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("videos.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
