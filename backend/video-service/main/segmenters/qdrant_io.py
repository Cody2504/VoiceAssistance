"""Shared Qdrant readers for segmenters.

All segmenters that need indexed shot data come through here, so the Qdrant
scroll/search code lives in one place and the rest of the package stays
storage-agnostic.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from main.settings import get_settings


def _client():
    from main.qdrant_util import get_qdrant_client

    return get_qdrant_client()


def read_shots(video_id: UUID, with_vectors: bool = False) -> list[dict[str, Any]]:
    """Return all per-shot rows for a video, sorted by shot_idx.

    Each row contains the payload fields written by `pipeline/ingest.py` plus
    `vector` (the CLIP-L visual embedding) when `with_vectors=True`. Shots
    with missing index or boundaries are filtered out so downstream segmenters
    can iterate without None-checks.
    """
    from qdrant_client.http import models as qm

    s = get_settings()
    client = _client()
    flt = qm.Filter(
        must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))],
    )

    out: list[dict[str, Any]] = []
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=s.qdrant_collection,
            scroll_filter=flt,
            limit=256,
            offset=next_offset,
            with_payload=True,
            with_vectors=with_vectors,
        )
        for p in points:
            pl = p.payload or {}
            if pl.get("shot_idx") is None or pl.get("t_start") is None or pl.get("t_end") is None:
                continue
            row = {
                "idx": pl.get("shot_idx"),
                "t_start": float(pl.get("t_start")),
                "t_end": float(pl.get("t_end")),
                "asr_text": pl.get("asr_text", "") or "",
                "ocr_text": pl.get("ocr_text", "") or "",
                "chunk_caption": pl.get("chunk_caption", "") or "",
                "audio_tags": pl.get("audio_tags", []) or [],
            }
            if with_vectors:
                row["vector"] = list(p.vector) if p.vector is not None else None
            out.append(row)
        if next_offset is None:
            break

    out.sort(key=lambda r: r["idx"])

    # `jockey_shots` stores MULTIPLE points per shot (one per sampled frame),
    # all carrying the same shot_idx + boundaries. Segmenters expect ONE row per
    # shot. Collapse duplicates (keep the first per idx, preferring a row that
    # actually has a caption). Without this the semantic-boundary segmenter asks
    # the LLM for boundary indices into the per-frame list; those land mid-shot,
    # split a shot's duplicate rows across two groups, and each group inherits
    # the shared shot's full time span → overlapping segment time ranges.
    deduped: dict[Any, dict[str, Any]] = {}
    for r in out:
        cur = deduped.get(r["idx"])
        if cur is None:
            deduped[r["idx"]] = r
        elif not (cur.get("chunk_caption") or "").strip() and (r.get("chunk_caption") or "").strip():
            deduped[r["idx"]] = r
    return list(deduped.values())
