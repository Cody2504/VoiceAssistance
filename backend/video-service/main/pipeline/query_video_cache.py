"""Query-time local video cache.

Object verification (research B) needs raw frames at query time, but videos
live in S3. Download once per video into a tmp cache keyed by video_id; later
queries against the same video reuse the file. Best-effort: returns None on
any failure so callers can skip verification rather than fail the request.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_CACHE_DIR = "/tmp/jockey_query_videos"


def ensure_local_video(video_id: str, minio_key: str) -> str | None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        ext = os.path.splitext(minio_key)[1] or ".mp4"
        path = os.path.join(_CACHE_DIR, f"{video_id}{ext}")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        from main.settings import get_settings
        from main.storage.minio import download_to_path
        download_to_path(get_settings().minio_bucket_videos, minio_key, path)
        return path if os.path.exists(path) and os.path.getsize(path) > 0 else None
    except Exception as exc:  # noqa: BLE001
        log.warning("query_video_cache: download failed for %s: %s", video_id, exc)
        try:
            if "path" in locals() and os.path.exists(path):
                os.unlink(path)  # don't cache a partial download
        except OSError:
            pass
        return None
