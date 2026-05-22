"""RQ worker for video indexing jobs.

Run as:
    python -m main.workers.queue_worker
"""
import logging
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

from redis import Redis
from rq import Connection, Queue, Worker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cm_shared.queue import VIDEO_INDEX_QUEUE
from cm_shared.settings import get_base_settings
from main.models.video import IndexingJob, Video
from main.pipeline.ingest import run_indexing

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("video-worker")


def _sync_session() -> Session:
    engine = create_engine(get_base_settings().sync_database_url, pool_pre_ping=True, future=True)
    return sessionmaker(engine, expire_on_commit=False)()


def index_video(video_id: str) -> dict:
    """Top-level RQ-callable. Updates DB state around the actual pipeline run."""
    vid = UUID(video_id)
    db = _sync_session()
    try:
        video = db.get(Video, vid)
        if not video:
            raise RuntimeError(f"video {video_id} not found")

        job = IndexingJob(video_id=vid, status="processing", started_at=datetime.now(timezone.utc))
        db.add(job)
        video.status = "processing"
        db.commit()

        try:
            result = run_indexing(
                vid, video.minio_key,
                user_id=video.user_id,
                original_filename=video.original_filename,
            )
            video.status = "ready"
            video.duration_s = result["duration_s"]
            video.shot_count = result["shot_count"]
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return result
        except Exception as exc:
            log.exception("indexing failed for %s", video_id)
            video.status = "error"
            video.error = str(exc)[:1000]
            job.status = "error"
            job.error = str(exc)[:1000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise
    finally:
        db.close()


def main():
    s = get_base_settings()
    redis = Redis(host=s.redis_host, port=s.redis_port)
    with Connection(redis):
        log.info("video-worker listening on queue=%s", VIDEO_INDEX_QUEUE)
        Worker([Queue(VIDEO_INDEX_QUEUE)]).work(with_scheduler=False)


if __name__ == "__main__":
    sys.exit(main() or 0)
