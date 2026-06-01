"""Auto-Highlights tile backend.

Saliency-ranked moments across the full video. Visual videos use Lighthouse
CG-DETR saliency on cached CLIP+SlowFast features; audio-only videos use a
QD-DETR-CLAP fallback (same generic highlight prompt).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.pipeline.highlights_v2 import run_highlights_v2

router = APIRouter(prefix="/api/v1/videos", tags=["highlights"])


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
    result = run_highlights_v2(
        str(video_id),
        duration_s=v.duration_s or 0.0,
        modality=v.modality,
        top_k=top_k,
    )
    return success_response({
        "video_id": result.video_id,
        "duration_s": result.duration_s,
        "moments": result.moments,
        "modality_used": result.modality_used,
        "query_used": result.query_used,
    })
