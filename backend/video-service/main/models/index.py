from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from cm_shared.db import Base


class Index(Base):
    __tablename__ = "indexes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="auto")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class IndexVideo(Base):
    __tablename__ = "index_videos"

    index_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("indexes.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
