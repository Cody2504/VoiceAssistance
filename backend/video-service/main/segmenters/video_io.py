"""Shared video-row + presigned-URL helpers for segmenters.

Centralized so individual segmenters don't each duplicate a sync engine
spin-up or guess the right bucket name.
"""
from __future__ import annotations

from uuid import UUID

from main.models.video import Video
from main.settings import get_settings
from main.storage.minio import presigned_get


def fetch_video(video_id: UUID) -> Video | None:
    """Synchronously load a Video row. Segmenters run inside the async request
    handler but each one wants its own short-lived sync session."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    s = get_settings()
    engine = create_engine(
        s.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://"),
        pool_pre_ping=True,
    )
    with Session(engine) as session:
        return session.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()


def stream_url(video: Video, public: bool = True, expires: int = 3600) -> str:
    """Return a presigned URL for the video object.

    `public=True` returns the externally-reachable form (used when handing
    the URL to a remote inference service). `public=False` returns the
    intra-network form (used when the local process downloads the file).
    """
    s = get_settings()
    return presigned_get(s.minio_bucket_videos, video.minio_key, expires=expires, public=public)
