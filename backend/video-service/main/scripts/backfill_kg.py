"""Run the Phase 2a knowledge-graph extraction over videos in an Index that
have already been ingested. No video re-decode, no re-embedding — reads window
summaries from the existing ``jockey_segments_text`` Qdrant payloads.

Use cases:
- A user creates an Index and adds existing Assets to it; their videos were
  ingested *before* the KG step existed (or with kg_enabled=false).
- ``settings.kg_enabled`` was turned on after the fact; you want to retroactively
  populate the graph for previously-indexed material.

Run inside the jockey-video-worker container (it has the OpenRouter API key
configured for the summarizer LLM):
    python -m main.scripts.backfill_kg --index <UUID>
    python -m main.scripts.backfill_kg --index <UUID> --videos <vid1> <vid2>

The script is idempotent: existing entity rows are reused (canonicalised by
cosine sim ≥ kg_canonical_sim_threshold), mentions are upserted by primary key
(entity_id, video_id, segment_idx), relations accumulate weights rather than
duplicate.
"""
from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from cm_shared.settings import get_base_settings
from main.models.index import Index, IndexVideo
from main.models.video import Video
from main.pipeline.kg_extract import run_kg_extract
from main.pipeline.summarize import SegmentRecord, WindowSummary
from main.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("backfill_kg")


def _sync_session() -> Session:
    engine = create_engine(get_base_settings().sync_database_url, pool_pre_ping=True, future=True)
    return sessionmaker(engine, expire_on_commit=False)()


def _load_video_state(video_id: UUID) -> tuple[list[SegmentRecord], list[WindowSummary]] | None:
    """Reconstruct (segments, windows) from this video's Qdrant text-payload
    rows. Returns None if the video has no payloads (not yet ingested or
    visual-only without the text collection)."""
    from qdrant_client.http import models as qm

    from main.qdrant_util import get_qdrant_client

    s = get_settings()
    client = get_qdrant_client(timeout=120)
    try:
        collections = {c.name for c in client.get_collections().collections}
    except Exception as exc:
        log.error("backfill_kg: could not list collections — %s", exc)
        return None
    if "jockey_segments_text" not in collections:
        log.warning("backfill_kg: jockey_segments_text collection missing — was this deployment ever upserted?")
        return None

    points: list = []
    offset = None
    while True:
        page, next_offset = client.scroll(
            collection_name="jockey_segments_text",
            scroll_filter=qm.Filter(
                must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]
            ),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend(page)
        if next_offset is None:
            break
        offset = next_offset

    if not points:
        return None

    # Segments first — one SegmentRecord per Qdrant point, indexed by segment_idx.
    seg_records: list[SegmentRecord] = []
    for p in points:
        pl = p.payload or {}
        idx = pl.get("segment_idx", pl.get("shot_idx"))
        if idx is None:
            continue
        seg_records.append(
            SegmentRecord(
                idx=int(idx),
                t_start=float(pl.get("t_start", 0.0)),
                t_end=float(pl.get("t_end", 0.0)),
                caption=pl.get("caption", "") or "",
                transcript=pl.get("transcript") or pl.get("asr_text", "") or "",
                audio_tags=pl.get("audio_tags", []) or [],
            )
        )
    seg_records.sort(key=lambda s: s.idx)

    # Group segments by window_idx → reconstruct WindowSummary list. The window
    # summary itself lives in the same payload (copy of summarize.py output).
    by_window: dict[int, dict] = {}
    for p in points:
        pl = p.payload or {}
        widx = pl.get("window_idx")
        if widx is None:
            continue
        bucket = by_window.setdefault(
            int(widx),
            {
                "idx": int(widx),
                "summary": pl.get("window_summary", "") or "",
                "segment_indices": [],
                "t_start": float(pl.get("t_start", 0.0)),
                "t_end": float(pl.get("t_end", 0.0)),
            },
        )
        sidx = pl.get("segment_idx", pl.get("shot_idx"))
        if sidx is not None and sidx not in bucket["segment_indices"]:
            bucket["segment_indices"].append(int(sidx))
        bucket["t_start"] = min(bucket["t_start"], float(pl.get("t_start", bucket["t_start"])))
        bucket["t_end"] = max(bucket["t_end"], float(pl.get("t_end", bucket["t_end"])))

    windows = [
        WindowSummary(
            idx=b["idx"],
            t_start=b["t_start"],
            t_end=b["t_end"],
            segment_indices=sorted(b["segment_indices"]),
            summary=b["summary"],
        )
        for b in sorted(by_window.values(), key=lambda x: x["idx"])
    ]
    return seg_records, windows


def _point_id_for(video_id: UUID):
    from uuid import NAMESPACE_OID, uuid5

    def _impl(segment_idx: int) -> str:
        return str(uuid5(NAMESPACE_OID, f"{video_id}:{segment_idx}"))
    return _impl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill the KG for an Index's videos.")
    parser.add_argument("--index", required=True, help="Index UUID")
    parser.add_argument(
        "--videos",
        nargs="*",
        default=None,
        help="Optional list of video UUIDs to process. Defaults to all videos in the index.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.openrouter_api_key:
        log.error("backfill_kg: OPENROUTER_API_KEY is empty — KG extraction needs an LLM. Aborting.")
        return 2

    index_id = UUID(args.index)
    session = _sync_session()
    try:
        idx = session.get(Index, index_id)
        if idx is None:
            log.error("backfill_kg: index %s not found", index_id)
            return 2

        if args.videos:
            video_ids = [UUID(v) for v in args.videos]
            # Confirm each belongs to this index.
            ok = (
                session.execute(
                    select(IndexVideo.video_id).where(
                        IndexVideo.index_id == index_id,
                        IndexVideo.video_id.in_(video_ids),
                    )
                )
                .scalars()
                .all()
            )
            video_ids = list(ok)
        else:
            video_ids = (
                session.execute(
                    select(IndexVideo.video_id)
                    .where(IndexVideo.index_id == index_id)
                    .order_by(IndexVideo.position.asc())
                )
                .scalars()
                .all()
            )

        if not video_ids:
            log.warning("backfill_kg: no videos to process for index %s", index_id)
            return 0

        totals = {"videos": 0, "entities_added": 0, "entities_reused": 0, "mentions": 0, "relations": 0}
        for vid in video_ids:
            video = session.get(Video, vid)
            if video is None or video.status != "ready":
                log.info("backfill_kg: skipping video %s (status=%s)", vid, video.status if video else "missing")
                continue
            state = _load_video_state(vid)
            if state is None:
                log.info("backfill_kg: video %s has no segment payloads in Qdrant — skipping", vid)
                continue
            seg_records, windows = state
            if not windows:
                log.info("backfill_kg: video %s has no window summaries — skipping", vid)
                continue

            result = run_kg_extract(
                video_id=vid,
                index_id=index_id,
                user_id=video.user_id,
                video_title=video.original_filename or "",
                segments=seg_records,
                windows=windows,
                qdrant_point_id_for=_point_id_for(vid),
                db_session=session,
                settings=settings,
            )
            totals["videos"] += 1
            totals["entities_added"] += result.entities_added
            totals["entities_reused"] += result.entities_reused
            totals["mentions"] += result.mentions
            totals["relations"] += result.relations
            log.info(
                "backfill_kg: video=%s done — +%d entities, %d reused, %d mentions, %d relations",
                vid,
                result.entities_added,
                result.entities_reused,
                result.mentions,
                result.relations,
            )

        log.info(
            "backfill_kg: index=%s — totals: %d videos, +%d entities, %d reused, %d mentions, %d relations",
            index_id,
            totals["videos"],
            totals["entities_added"],
            totals["entities_reused"],
            totals["mentions"],
            totals["relations"],
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
