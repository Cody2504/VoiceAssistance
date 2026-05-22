"""Auto-highlights endpoint — closes UC #4.

Calls the QD-DETR backend with a generic "key moment / highlight" query so
saliency peaks correspond to interesting moments, even without a user query.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.pipeline.ground_qddetr import run_grounding_qddetr

router = APIRouter(prefix="/api/v1/videos", tags=["highlights"])

# Generic prompt chosen so QD-DETR's saliency head surfaces interesting moments
# rather than matching a specific subject. QVHighlights training data biases the
# model toward this notion of "highlight".
HIGHLIGHT_QUERY = "an interesting key moment or highlight from the video"


@router.get("/{video_id}/highlights")
async def highlights(
    video_id: UUID,
    top_k: int = 10,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    top_k = max(1, min(int(top_k), 20))
    result = run_grounding_qddetr(str(video_id), v.minio_key, HIGHLIGHT_QUERY, top_k=top_k)
    # Re-label fields for the highlights surface
    return success_response({
        "video_id": str(video_id),
        "duration_s": v.duration_s,
        "moments": result.get("spans", []),
        "shots": result.get("shots", []),
        "query_used": HIGHLIGHT_QUERY,
    })
