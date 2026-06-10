from __future__ import annotations

import logging
from uuid import UUID

from qdrant_client.http import models as qm

from main.models.timeline import TimelineSegment, TimelineTrack
from main.qdrant_util import batched_upsert, ensure_collection, get_qdrant_client

log = logging.getLogger(__name__)

_EVENT_VECTOR_DIM = 3072  # text-embedding-3-large
_QDRANT_TIMEOUT_SEC = 300
_QDRANT_BATCH = 32


def persist_timeline(*, db_session, video_id, tracks) -> None:
    """Delete any existing timeline for this video, then insert the new tracks +
    segments. Idempotent across re-index."""
    vid = video_id if isinstance(video_id, UUID) else UUID(str(video_id))
    existing = (
        db_session.query(TimelineTrack).filter(TimelineTrack.video_id == vid).all()
        if hasattr(db_session, "query")
        else []
    )
    for tr in existing:
        db_session.delete(tr)  # cascade removes its segments
    db_session.flush()

    for t in tracks:
        track_row = TimelineTrack(video_id=vid, kind=t.kind, label=t.label)
        db_session.add(track_row)
        db_session.flush()  # populate track_row.id
        for e in t.events:
            qpid = (e.metadata or {}).get("qdrant_point_id")
            db_session.add(TimelineSegment(
                track_id=track_row.id,
                video_id=vid,
                t_start=float(e.t_start),
                t_end=float(e.t_end),
                label=e.label,
                seg_metadata={k: v for k, v in (e.metadata or {}).items() if k != "qdrant_point_id"},
                source=e.source,
                score=float(e.score),
                qdrant_point_id=UUID(qpid) if qpid else None,
            ))
    db_session.commit()


def upsert_event_vectors(*, settings, video_id, points) -> None:
    """Create the event collection if needed and upsert one point per event."""
    if not points:
        return
    client = get_qdrant_client(timeout=_QDRANT_TIMEOUT_SEC)
    coll = settings.timeline_events_collection
    ensure_collection(client, coll, _EVENT_VECTOR_DIM)
    structs = [
        qm.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
        for p in points
    ]
    batched_upsert(client, coll, structs, batch_size=_QDRANT_BATCH)
