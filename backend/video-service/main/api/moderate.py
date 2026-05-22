"""Content-moderation endpoint — closes UC #14.

Reads `nsfw_score` and `toxic_score` from each shot's Qdrant payload (written by
the moderation_encoder stages in pipeline/ingest.py) and returns the flagged
shots ranked by max(nsfw, toxic) with per-model attribution.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["moderate"])


def _qdrant():
    from qdrant_client import QdrantClient

    s = get_settings()
    return QdrantClient(host=s.qdrant_host, port=s.qdrant_port)


@router.get("/{video_id}/moderate")
async def moderate(
    video_id: UUID,
    threshold: float = 0.5,
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

    flagged: list[dict] = []
    max_nsfw = 0.0
    max_toxic = 0.0
    next_offset = None
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
            n = float(pl.get("nsfw_score", 0.0) or 0.0)
            t = float(pl.get("toxic_score", 0.0) or 0.0)
            max_nsfw = max(max_nsfw, n)
            max_toxic = max(max_toxic, t)
            if max(n, t) >= threshold:
                flagged.append({
                    "idx": pl.get("shot_idx"),
                    "t_start": pl.get("t_start"),
                    "t_end": pl.get("t_end"),
                    "nsfw_score": n,
                    "toxic_score": t,
                    "asr_text": pl.get("asr_text", ""),
                })
        if next_offset is None:
            break

    flagged.sort(key=lambda x: -max(x["nsfw_score"], x["toxic_score"]))

    return success_response({
        "video_id": str(video_id),
        "threshold": threshold,
        "summary": {
            "max_nsfw": max_nsfw,
            "max_toxic": max_toxic,
            "flagged_count": len(flagged),
        },
        "flagged_shots": flagged,
    })
