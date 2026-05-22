"""Re-index all currently-ready videos: clear their Qdrant shots and re-run the pipeline.

Run inside the jockey-video-worker container (it has the heavy models):
    python -m main.scripts.reindex
"""
import logging
import sys
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from cm_shared.settings import get_base_settings
from main.models.video import Video
from main.pipeline.ingest import run_indexing
from main.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("reindex")


def _sync_session() -> Session:
    engine = create_engine(get_base_settings().sync_database_url, pool_pre_ping=True, future=True)
    return sessionmaker(engine, expire_on_commit=False)()


def _drop_qdrant_shots(video_id: UUID) -> int:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm
    s = get_settings()
    client = QdrantClient(host=s.qdrant_host, port=s.qdrant_port)
    res = client.delete(
        collection_name=s.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))])
        ),
    )
    log.info("dropped qdrant shots for %s: %s", video_id, getattr(res, "status", res))
    return 0


def main(video_ids: list[str] | None = None) -> None:
    session = _sync_session()
    try:
        q = select(Video).where(Video.status == "ready")
        rows = session.execute(q).scalars().all()
        if video_ids:
            wanted = {UUID(v) for v in video_ids}
            rows = [r for r in rows if r.id in wanted]

        log.info("reindex:found %d ready videos", len(rows))
        for v in rows:
            log.info("reindex:start id=%s file=%s", v.id, v.original_filename)
            _drop_qdrant_shots(v.id)
            v.status = "indexing"
            session.commit()
            try:
                summary = run_indexing(v.id, v.minio_key)
                v.status = "ready"
                v.duration_s = summary.get("duration_s")
                v.shot_count = summary.get("shot_count")
                v.error = None
                session.commit()
                log.info("reindex:ok id=%s shots=%d duration=%.2fs", v.id, summary["shot_count"], summary["duration_s"])
            except Exception as exc:
                v.status = "error"
                v.error = str(exc)[:1000]
                session.commit()
                log.exception("reindex:fail id=%s", v.id)
    finally:
        session.close()


if __name__ == "__main__":
    main(sys.argv[1:] if len(sys.argv) > 1 else None)
