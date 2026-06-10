"""Audio-events endpoint — closes UC #15.

Reads per-shot `audio_tags` (top-K PANN AudioSet labels) from Qdrant payload.
GET /videos/{id}/sounds            → all shots with their tags
GET /videos/{id}/sounds?tag=Music  → only shots whose top tags include "Music"
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["sounds"])


def _qdrant():
    from main.qdrant_util import get_qdrant_client

    return get_qdrant_client()


@router.get("/{video_id}/sounds")
async def sounds(
    video_id: UUID,
    tag: str | None = Query(None, description="Optional AudioSet label to filter by (case-insensitive substring)."),
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    from qdrant_client.http import models as qm

    s = get_settings()
    client = _qdrant()
    flt = qm.Filter(
        must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))],
    )

    out: list[dict] = []
    next_offset = None
    tag_lc = (tag or "").lower().strip()

    while True:
        points, next_offset = client.scroll(
            collection_name=s.qdrant_collection,
            scroll_filter=flt,
            limit=256,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            pl = p.payload or {}
            tags = pl.get("audio_tags") or []
            if tag_lc:
                if not any(tag_lc in (t.get("label", "") or "").lower() for t in tags):
                    continue
            out.append({
                "idx": pl.get("shot_idx"),
                "t_start": pl.get("t_start"),
                "t_end": pl.get("t_end"),
                "audio_tags": tags,
                "asr_text": pl.get("asr_text", ""),
            })
        if next_offset is None:
            break

    out.sort(key=lambda x: x["idx"] if x["idx"] is not None else 0)
    return success_response({"video_id": str(video_id), "tag": tag, "shots": out})
