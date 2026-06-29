from __future__ import annotations

import logging
from dataclasses import dataclass, field

from main.pipeline.ground_v2 import _iou  # reuse 1-D IoU
from main.qdrant_util import to_vector_list
from main.settings import get_settings

log = logging.getLogger(__name__)

# Stream families and their base weights. The two *precise* localizers —
# "grounding" (trained DETR head) and "event:vlm_actions" (per-action moments) —
# are weighted above the coarse appearance streams: for "when does X" a tight,
# action-specific window should beat a 30 s shot that merely *contains* X.
# A key with ":" is a source-specific override that wins over its family weight.
_BASE_WEIGHTS = {
    "visual": 1.0, "event": 1.0, "segment": 1.0, "tag_ocr": 0.9, "ocr": 1.0, "audio": 1.0,
    "motion": 1.0, "grounding": 1.1, "event:vlm_actions": 1.2,
}

_AUDIO_CUES = ("cheer", "applause", "whistle", "crowd", "roar", "clap", "shout", "music", "sound")
_TEXT_CUES = ("say", "said", "says", "mention", "talk", "speak", "discuss", "explain", "tell")
_OCR_CUES = ("text", "slide", "caption", "subtitle", "score", "scoreboard", "title")
_NON_MOMENT_CUES = ("summary", "summarize", "overview", "what is this video", "describe the video", "about")


@dataclass
class WhenCandidate:
    t_start: float
    t_end: float
    score: float
    source: str            # "visual" | "event:<kind>" | "segment" | "tag_ocr" | "grounding"
    label: str
    metadata: dict = field(default_factory=dict)

    @property
    def family(self) -> str:
        return self.source.split(":", 1)[0]


def stream_weights(query: str) -> dict[str, float]:
    """Light routing heuristic: boost streams whose cue words appear in the query."""
    q = (query or "").lower()
    w = dict(_BASE_WEIGHTS)
    if any(c in q for c in _AUDIO_CUES):
        w["tag_ocr"] += 0.6
        w["event"] += 0.3
        w["audio"] = w.get("audio", 1.0) + 0.5
    if any(c in q for c in _TEXT_CUES):
        w["segment"] += 0.6
    if any(c in q for c in _OCR_CUES):
        w["tag_ocr"] += 0.4
    return w


def is_moment_like(query: str) -> bool:
    """Whether to spend the DETR-refine stream. Broad/summary queries skip it."""
    q = (query or "").lower()
    return not any(c in q for c in _NON_MOMENT_CUES)


def apply_weights(cands: list[WhenCandidate], weights: dict[str, float]) -> list[WhenCandidate]:
    """Max-normalize each candidate's score within its family, then × the family weight."""
    by_family: dict[str, float] = {}
    for c in cands:
        by_family[c.family] = max(by_family.get(c.family, 0.0), c.score)
    out: list[WhenCandidate] = []
    for c in cands:
        fmax = by_family.get(c.family, 0.0) or 1.0
        # source-specific weight (e.g. "event:vlm_actions") wins over the family.
        w = weights.get(c.source, weights.get(c.family, 1.0))
        out.append(WhenCandidate(
            c.t_start, c.t_end, (c.score / fmax) * w, c.source, c.label, c.metadata,
        ))
    return out


def merge_rank(cands: list[WhenCandidate], *, top_n: int, iou_threshold: float) -> list[dict]:
    """Sort by score desc, greedily keep non-overlapping; fold overlapping lower-
    scored candidates into the kept one's `also_matched` provenance."""
    # Sort by score desc; break ties toward the TIGHTER span (a precise moment
    # beats a coarse shot of equal relevance for a "when does X" query).
    ordered = sorted(cands, key=lambda c: (-c.score, c.t_end - c.t_start))
    kept: list[dict] = []
    for c in ordered:
        hit = None
        for k in kept:
            if _iou((c.t_start, c.t_end, c.score), (k["t_start"], k["t_end"], k["score"])) >= iou_threshold:
                hit = k
                break
        if hit is None:
            kept.append({
                "t_start": float(c.t_start), "t_end": float(c.t_end), "score": float(c.score),
                "source": c.source, "label": c.label, "metadata": c.metadata, "also_matched": [],
            })
        elif c.family not in hit["also_matched"] and c.family != hit["source"].split(":", 1)[0]:
            hit["also_matched"].append(c.family)
    return kept[:top_n]


# Fan-out stream fetchers

def _qdrant():
    from main.qdrant_util import get_qdrant_client
    return get_qdrant_client(timeout=60)


def _video_filter(video_id):
    from qdrant_client.http import models as qm
    return qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))])


def _visual_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """CLIP-L text->shot retrieval over jockey_shots (the Marengo-style stream)."""
    try:
        from main.encoders.clipl_embedder import CLIPLEmbedder
        device = getattr(settings, "iv2_device", "cpu")
        qvec = CLIPLEmbedder(device=device).encode_text(query)
        hits = _qdrant().search(
            collection_name=settings.qdrant_collection,
            query_vector=to_vector_list(qvec),
            query_filter=_video_filter(video_id),
            limit=settings.when_top_n,
            with_payload=True,
        )
        return [
            WhenCandidate(
                float(h.payload["t_start"]), float(h.payload["t_end"]), float(h.score),
                "visual", (h.payload.get("chunk_caption") or h.payload.get("asr_text") or "shot"),
                {"shot_idx": h.payload.get("shot_idx")},
            )
            for h in hits if h.payload
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("when:visual stream failed: %s", exc)
        return []


def _text_embed(query):
    from main.encoders.config import config
    from main.encoders.search import TextEmbedder
    return TextEmbedder(
        api_key=config.openrouter_api_key, model=config.text_embedding_model,
        base_url=config.openrouter_base_url,
    ).encode(query)


def _event_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """Event-level semantic search over jockey_timeline_events (whole long events)."""
    try:
        qvec = _text_embed(query)
        hits = _qdrant().search(
            collection_name=settings.timeline_events_collection,
            query_vector=to_vector_list(qvec),
            query_filter=_video_filter(video_id),
            limit=settings.when_top_n,
            with_payload=True,
        )
        return [
            WhenCandidate(
                float(h.payload["t_start"]), float(h.payload["t_end"]), float(h.score),
                f"event:{h.payload.get('track_kind', 'event')}", h.payload.get("label", "event"),
                h.payload.get("metadata", {}) or {},
            )
            for h in hits if h.payload
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("when:event stream failed: %s", exc)
        return []


def _segment_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """30 s caption+transcript matches over jockey_segments_text (short narrated moments)."""
    try:
        qvec = _text_embed(query)
        hits = _qdrant().search(
            collection_name="jockey_segments_text",
            query_vector=to_vector_list(qvec),
            query_filter=_video_filter(video_id),
            limit=settings.when_top_n,
            with_payload=True,
        )
        return [
            WhenCandidate(
                float(h.payload["t_start"]), float(h.payload["t_end"]), float(h.score),
                "segment", (h.payload.get("caption") or h.payload.get("transcript") or "segment"),
                {"segment_idx": h.payload.get("segment_idx")},
            )
            for h in hits if h.payload
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("when:segment stream failed: %s", exc)
        return []


def _tag_ocr_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """Lexical complement: scroll the audio_events/on_screen_text events and keep
    those whose label contains a query term (exact terms semantic search misses)."""
    from qdrant_client.http import models as qm
    terms = [t for t in (query or "").lower().split() if len(t) >= 3]
    if not terms:
        return []
    try:
        flt = qm.Filter(
            must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))],
            should=[
                qm.FieldCondition(key="track_kind", match=qm.MatchValue(value="audio_events")),
                qm.FieldCondition(key="track_kind", match=qm.MatchValue(value="on_screen_text")),
            ],
        )
        points, _ = _qdrant().scroll(
            collection_name=settings.timeline_events_collection,
            scroll_filter=flt, with_payload=True, with_vectors=False, limit=512,
        )
        out: list[WhenCandidate] = []
        for p in points:
            pl = p.payload or {}
            label = (pl.get("label") or "").lower()
            if any(t in label for t in terms):
                out.append(WhenCandidate(
                    float(pl["t_start"]), float(pl["t_end"]), 1.0,
                    "tag_ocr", pl.get("label", ""), pl.get("metadata", {}) or {},
                ))
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("when:tag_ocr stream failed: %s", exc)
        return []


def _ocr_text_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """Full-text OCR match over jockey_segments_text.ocr_text (exact signage)."""
    try:
        from main.pipeline.ocr_search import ocr_candidates
        return [
            WhenCandidate(h["t_start"], h["t_end"], 1.0, "ocr", h["ocr_text"][:120],
                          {"ocr_text": h["ocr_text"]})
            for h in ocr_candidates(query, video_id=video_id, settings=settings)
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("when:ocr stream failed: %s", exc)
        return []


def _audio_event_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """CLAP text->audio retrieval over jockey_audio_events (non-speech audio
    events: cheering, whistle, applause, music)."""
    try:
        from main.encoders.clap_encoder import CLAPEncoder
        qvec = CLAPEncoder(use_cuda=False).encode_text(query)
        if qvec is None:
            return []
        hits = _qdrant().search(
            collection_name=settings.audio_events_collection,
            query_vector=to_vector_list(qvec),
            query_filter=_video_filter(video_id),
            limit=settings.when_top_n, with_payload=True,
        )
        out: list[WhenCandidate] = []
        for h in hits:
            if not h.payload:
                continue
            tags = h.payload.get("audio_tags") or []
            label = tags[0].get("label", "audio") if tags else "audio"
            out.append(WhenCandidate(
                float(h.payload["t_start"]), float(h.payload["t_end"]), float(h.score),
                "audio", label, {"audio_tags": tags},
            ))
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("when:audio stream failed: %s", exc)
        return []


def _motion_candidates(video_id, query, settings) -> list[WhenCandidate]:
    """ViCLIP text->video retrieval over jockey_motion (research A): temporal
    motion matching for silent/uncaptioned actions appearance-only CLIP misses."""
    if not settings.motion_enabled:
        return []
    try:
        from main.encoders.motion_encoder import MotionEncoder
        enc = MotionEncoder.from_settings(settings)
        qvec = enc.encode_text(query)
        if qvec is None:
            return []
        hits = _qdrant().search(
            collection_name=settings.motion_collection,
            query_vector=to_vector_list(qvec),
            query_filter=_video_filter(video_id),
            limit=settings.when_top_n, with_payload=True,
        )
        return [
            WhenCandidate(
                float(h.payload["t_start"]), float(h.payload["t_end"]), float(h.score),
                "motion", (h.payload.get("caption") or "motion match"),
                {"segment_idx": h.payload.get("segment_idx")},
            )
            for h in hits if h.payload
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("when:motion stream failed: %s", exc)
        return []


def _grounding_candidates(video_id, query, modality, settings) -> list[WhenCandidate]:
    """DETR-refine stream: reuse run_grounding_v2 (dense->greedy_merge->head)."""
    try:
        from main.pipeline.ground_v2 import run_grounding_v2
        res = run_grounding_v2(str(video_id), query, modality=modality)
        return [
            WhenCandidate(float(m["t_start"]), float(m["t_end"]), float(m["score"]),
                          "grounding", "grounded moment", {})
            for m in res.moments
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("when:grounding stream failed: %s", exc)
        return []


@dataclass
class WhenResult:
    video_id: str
    query: str
    events: list[dict]


def run_when(video_id, query, *, modality=None, top_n=None, refine=None,
             minio_key=None, settings=None) -> WhenResult:
    s = settings or get_settings()
    top_n = top_n or s.when_top_n
    refine = s.when_refine_default if refine is None else refine

    cands: list[WhenCandidate] = []
    cands += _visual_candidates(video_id, query, s)
    cands += _event_candidates(video_id, query, s)
    cands += _segment_candidates(video_id, query, s)
    cands += _tag_ocr_candidates(video_id, query, s)
    cands += _ocr_text_candidates(video_id, query, s)
    cands += _audio_event_candidates(video_id, query, s)
    cands += _motion_candidates(video_id, query, s)
    if refine and is_moment_like(query):
        cands += _grounding_candidates(video_id, query, modality, s)

    scored = apply_weights(cands, stream_weights(query))
    events = merge_rank(scored, top_n=top_n, iou_threshold=s.ground_iou_dedup_threshold)

    # Research B: GroundingDINO re-rank of the top candidates by whether the
    # query's object phrase is actually detectable in their frames. Best-effort
    # — any failure keeps the unverified ranking.
    if s.object_verify_enabled and minio_key and events:
        try:
            from main.pipeline.object_verify import verify_events
            from main.pipeline.query_video_cache import ensure_local_video
            local = ensure_local_video(str(video_id), minio_key)
            if local:
                events = verify_events(events, local, query, settings=s)
        except Exception as exc:  # noqa: BLE001
            log.warning("when:object verify failed: %s", exc)

    return WhenResult(video_id=str(video_id), query=query, events=events)


# Timeline read (Postgres -> Segment-UI shape)

def shape_timeline_rows(rows) -> list[dict]:
    """rows: iterable of (track_kind, track_label, t_start, t_end, label, metadata, score),
    ordered by (track_kind, t_start). Returns Segment-UI track shape."""
    tracks: dict[str, dict] = {}
    order: list[str] = []
    for kind, _label, t0, t1, _seg_label, meta, _score in rows:
        if kind not in tracks:
            tracks[kind] = {"definition_id": kind, "implemented": True, "segments": []}
            order.append(kind)
        tracks[kind]["segments"].append({
            "t_start": float(t0), "t_end": float(t1), "metadata": meta or {},
        })
    return [tracks[k] for k in order]


async def load_timeline(session, video_id) -> list[dict]:
    """Read persisted timeline tracks/segments for a video (async session)."""
    from sqlalchemy import select
    from main.models.timeline import TimelineSegment, TimelineTrack

    stmt = (
        select(
            TimelineTrack.kind, TimelineTrack.label, TimelineSegment.t_start,
            TimelineSegment.t_end, TimelineSegment.label, TimelineSegment.seg_metadata,
            TimelineSegment.score,
        )
        .join(TimelineSegment, TimelineSegment.track_id == TimelineTrack.id)
        .where(TimelineTrack.video_id == video_id)
        .order_by(TimelineTrack.kind, TimelineSegment.t_start)
    )
    result = await session.execute(stmt)
    return shape_timeline_rows(result.all())
