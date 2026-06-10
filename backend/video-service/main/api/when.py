from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.pipeline.when_v2 import load_timeline, run_when

router = APIRouter(prefix="/api/v1/videos", tags=["when"])


class WhenQuery(BaseModel):
    query: str
    top_n: int | None = None
    refine: bool | None = None


async def _require_ready_video(session: AsyncSession, video_id: UUID, payload: TokenPayload) -> Video:
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")
    return v


@router.get("/{video_id}/timeline")
async def get_timeline(
    video_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await _require_ready_video(session, video_id, payload)
    tracks = await load_timeline(session, video_id)
    return success_response({"video_id": str(video_id), "duration_s": v.duration_s, "tracks": tracks})


@router.post("/{video_id}/when")
async def when_does_x_happen(
    video_id: UUID,
    body: WhenQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await _require_ready_video(session, video_id, payload)
    if not body.query.strip():
        raise HTTPException(400, "query is required")
    res = run_when(str(video_id), body.query.strip(), modality=v.modality,
                   top_n=body.top_n, refine=body.refine, minio_key=v.minio_key)
    return success_response({"video_id": str(video_id), "query": res.query, "events": res.events})
