from __future__ import annotations

import logging
from uuid import NAMESPACE_OID, uuid5

import numpy as np

from main.pipeline.timeline import generators as _gen
from main.pipeline.timeline.persist import persist_timeline, upsert_event_vectors
from main.pipeline.timeline.types import GeneratedTrack, TimelineEvent
from main.qdrant_util import to_vector_list

log = logging.getLogger(__name__)

# kind -> generator function (uniform signature)
_GENERATORS = {
    "audio_events": _gen.gen_audio_events,
    "on_screen_text": _gen.gen_on_screen_text,
    "shots": _gen.gen_shots,
    "spoken_topics": _gen.gen_spoken_topics,
    "highlights": _gen.gen_highlights,
    "vlm_actions": _gen.gen_vlm_actions,
    "speakers": _gen.gen_speakers,
}


def event_text(event: TimelineEvent, artifacts) -> str:
    """Aggregate the label + the captions/transcripts of every 30 s segment that
    overlaps the event span — the text we embed for event-granularity search."""
    parts: list[str] = [event.label]
    for (t0, t1), cap, tr in zip(artifacts.segments, artifacts.captions, artifacts.transcripts):
        if t0 < event.t_end and t1 > event.t_start:  # overlap
            if cap and cap.strip():
                parts.append(cap.strip())
            if tr and tr.strip():
                parts.append(tr.strip())
    text = " | ".join(p for p in parts if p)
    return text[:1000]  # keep short to preserve embedding quality on long events


def _embed_texts(texts: list[str]) -> list[np.ndarray]:
    from main.encoders.config import config
    from main.encoders.search import TextEmbedder
    embedder = TextEmbedder(
        api_key=config.openrouter_api_key,
        model=config.text_embedding_model,
        base_url=config.openrouter_base_url,
    )
    return embedder.encode_batch(texts)


def build_timeline(video_id, artifacts, summary, *, settings, db_session) -> None:
    """Run the selected generators, embed each event, persist to Postgres +
    Qdrant. Each generator is best-effort: one failure drops only its track."""
    tracks: list[GeneratedTrack] = []
    for kind in settings.timeline_default_tracks:
        fn = _GENERATORS.get(kind)
        if fn is None:
            log.warning("timeline:unknown track kind %r — skipping", kind)
            continue
        try:
            t = fn(video_id, artifacts, summary, settings=settings)
            if t is not None and t.events:
                tracks.append(t)
        except Exception as exc:  # noqa: BLE001
            log.warning("timeline:generator %s failed for video=%s: %s", kind, video_id, exc)

    if not tracks:
        log.info("timeline:no events produced for video=%s", video_id)
        return

    # Embed every event; assign a deterministic Qdrant point id.
    texts, flat = [], []  # flat = (track, event)
    for t in tracks:
        for i, e in enumerate(t.events):
            e.metadata = dict(e.metadata or {})
            point_id = str(uuid5(NAMESPACE_OID, f"{video_id}:{t.kind}:{i}"))
            flat.append((t, e, point_id))
            texts.append(event_text(e, artifacts))
    vectors = _embed_texts(texts)

    points = []
    for (t, e, point_id), vec in zip(flat, vectors):
        e.metadata["qdrant_point_id"] = point_id
        points.append({
            "id": point_id,
            "vector": to_vector_list(vec),
            "payload": {
                "video_id": str(video_id),
                "track_kind": t.kind,
                "t_start": float(e.t_start),
                "t_end": float(e.t_end),
                "label": e.label,
                "source": e.source,
                "metadata": {k: v for k, v in e.metadata.items() if k != "qdrant_point_id"},
            },
        })

    persist_timeline(db_session=db_session, video_id=video_id, tracks=tracks)
    upsert_event_vectors(settings=settings, video_id=video_id, points=points)
    log.info("timeline:built video=%s tracks=%d events=%d", video_id, len(tracks), len(points))
