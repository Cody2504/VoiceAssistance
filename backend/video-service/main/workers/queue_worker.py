"""RQ worker for video indexing jobs.

Run as:
    python -m main.workers.queue_worker

Architecture: the default RQ ``Worker`` forks a fresh work-horse per job.
The parent process MUST NOT touch CUDA — kernel handles in libcuda are
tied to the originating PID and copy-on-write inheritance corrupts them,
so the first ``.to("cuda")`` call inside a child of a CUDA-warm parent
SIGSEGVs. Concretely that means:

  * No ``import torch`` at this module's top level.
  * No transitive import that initializes CUDA (every encoder module
    keeps its torch imports lazy — verified in 2026-05-26).
  * The CUDA + cuBLAS + cuDNN preflight lives inside :func:`index_video`
    so it only runs in the forked child.

Cost of this design: every job cold-loads ~14 GB of model weights
(Whisper distil-large + CLIP-L + CLAP + SlowFast + OCR + PANN + NSFW)
which is roughly 30–60 s of startup per video. The benefit is fault
isolation — a SIGSEGV / OOM in one job no longer takes down the worker —
and clean compatibility with CUDA MPS, which lets multiple replicas'
work-horses share the GPU at SM granularity instead of time-slicing
the whole context. See ``docker-compose.yml`` for the MPS wiring.
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


def _preflight_cuda() -> None:
    """Init torch + cuBLAS + cuDNN before any video lib loads.

    libavcodec (pulled in by PyAV / decord / opencv inside the encoders)
    links against libcuda symbols that conflict with libtorch's runtime
    if torch is initialized after them. Runs once at the start of every
    forked work-horse.
    """
    print("[preflight] importing torch...", flush=True)
    import torch
    print(f"[preflight] torch={torch.__version__} cuda_avail={torch.cuda.is_available()}", flush=True)
    if not torch.cuda.is_available():
        return
    print("[preflight] forcing CUDA + cuBLAS + cuDNN init", flush=True)
    torch.cuda.init()
    a = torch.randn(8, 8, device="cuda")
    _ = a @ a  # cuBLAS
    try:
        torch.backends.cudnn.is_available()
        c = torch.randn(1, 3, 8, 8, device="cuda")
        w = torch.randn(3, 3, 3, 3, device="cuda")
        _ = torch.nn.functional.conv2d(c, w)  # cuDNN
    except Exception as exc:
        print(f"[preflight] cudnn warm-up skipped: {exc}", flush=True)
    torch.cuda.synchronize()
    print(f"[preflight] CUDA ready, vram_alloc={torch.cuda.memory_allocated()//1024} KiB", flush=True)


def index_video(video_id: str) -> dict:
    """Top-level RQ-callable. Runs in the forked work-horse."""
    _preflight_cuda()

    # boto3 clients hold connection pool FDs that don't survive fork cleanly
    # (403 HeadObject even with correct config). Drop the lru_cache so the
    # forked child builds a fresh client.
    from main.storage.minio import s3, _s3_public
    s3.cache_clear()
    _s3_public.cache_clear()

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
            video.modality = result.get("modality")
            video.has_video = result.get("has_video")
            video.has_audio = result.get("has_audio")
            video.global_summary = result.get("global_summary")
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
        log.info("video-worker (Worker, fork-per-job) listening on queue=%s", VIDEO_INDEX_QUEUE)
        Worker([Queue(VIDEO_INDEX_QUEUE)]).work(with_scheduler=False)


if __name__ == "__main__":
    sys.exit(main() or 0)
