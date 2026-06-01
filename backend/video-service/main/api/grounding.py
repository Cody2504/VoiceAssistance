"""Ground tile — moment retrieval for a specific natural-language query.

Backed by `pipeline.ground_v2`: dense top-K candidate segments are merged into
≤150-second windows, then Lighthouse CG-DETR (visual) or QD-DETR-CLAP (audio)
runs on the cached feature slices and returns sub-second `(start, end, score)`
moments deduped by 1-D IoU.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import GroundQuery
from main.models.video import Video
from main.pipeline.ground_v2 import run_grounding_v2

router = APIRouter(prefix="/api/v1/videos", tags=["grounding"])


@router.post("/{video_id}/ground")
async def ground(
    video_id: UUID,
    body: GroundQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    result = run_grounding_v2(str(video_id), body.query, modality=v.modality)
    return success_response({
        "video_id": result.video_id,
        "query": result.query,
        "moments": result.moments,
        "modality_used": result.modality_used,
        "candidate_windows": result.candidate_windows,
    })
