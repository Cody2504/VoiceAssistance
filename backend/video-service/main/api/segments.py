"""List + run shot segments for a single video.

GET  exposes the per-shot payloads already written to Qdrant by
`pipeline/ingest.py` (PySceneDetect output). No new compute — just a read.

POST runs the Segment Builder: takes a list of `SegmentDefinition`s and
dispatches each to its segmenter via `main.segmenters.REGISTRY`. Each
preset id either maps to a real segmenter (returns segments) or doesn't
(returns an empty track, UI still renders the row).
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.api.segments_types import SegmentDefinition, SegmentRunRequest  # re-exported below
from main.models.video import Video
from main.segmenters import is_implemented, run_definition
from main.segmenters.qdrant_io import read_shots

router = APIRouter(prefix="/api/v1/videos", tags=["segments"])

# Re-export to keep existing imports stable.
__all__ = ["router", "SegmentDefinition", "SegmentRunRequest"]


@router.get("/{video_id}/segments")
async def list_segments(
    video_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Return all shot boundaries for a video, sorted by shot index."""
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    shots = read_shots(video_id, with_vectors=False)
    segments = [
        {"idx": sh["idx"], "t_start": sh["t_start"], "t_end": sh["t_end"], "asr_text": sh["asr_text"]}
        for sh in shots
    ]
    return success_response(
        {"video_id": str(video_id), "duration_s": v.duration_s, "segments": segments}
    )


def _filter_by_window(
    segs: list[dict[str, Any]],
    start_s: float | None,
    end_s: float | None,
    min_dur: float | None,
    max_dur: float | None,
) -> list[dict[str, Any]]:
    out = []
    for s in segs:
        ts, te = s.get("t_start"), s.get("t_end")
        if ts is None or te is None:
            continue
        if start_s is not None and te <= start_s:
            continue
        if end_s is not None and ts >= end_s:
            continue
        dur = te - ts
        if min_dur is not None and dur < min_dur:
            continue
        if max_dur is not None and dur > max_dur:
            continue
        out.append(s)
    return out


@router.post("/{video_id}/segment")
async def run_segment(
    video_id: UUID,
    body: SegmentRunRequest,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Run a multi-definition segmentation against a video.

    Body: `{definitions: [SegmentDefinition,...], start_s?, end_s?, min/max_duration_s?}`
    Response: `{video_id, duration_s, tracks: [{definition_id, implemented, segments}]}`
    """
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")
    if len(body.definitions) == 0:
        raise HTTPException(400, "At least one segment definition is required")
    if len(body.definitions) > 10:
        raise HTTPException(400, "At most 10 segment definitions per request")

    tracks = []
    for d in body.definitions:
        raw = run_definition(video_id, d)
        filtered = _filter_by_window(
            raw, body.start_s, body.end_s, body.min_duration_s, body.max_duration_s
        )
        tracks.append(
            {"definition_id": d.id, "implemented": is_implemented(d.id), "segments": filtered}
        )

    return success_response(
        {"video_id": str(video_id), "duration_s": v.duration_s, "tracks": tracks}
    )
