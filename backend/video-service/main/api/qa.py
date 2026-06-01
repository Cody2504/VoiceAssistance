"""Analyze tile backend — long-context Q&A over a single video.

Delegates the actual retrieval + LLM call to `pipeline.analyze.run_analyze`.
This module is now thin: it authenticates the user, fetches the global
summary from the videos row (no extra DB hop in the pipeline), and shapes the
response for the frontend.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.pipeline.analyze import run_analyze

router = APIRouter(prefix="/api/v1/videos", tags=["qa"])


class QaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2048)
    # Legacy fields kept so the existing frontend can still send a time range
    # without breaking; the new pipeline ignores them and answers using
    # retrieval over the whole video. A subsequent UI change can drop these.
    t_start: float | None = None
    t_end: float | None = None


@router.post("/{video_id}/qa")
async def qa(
    video_id: UUID,
    body: QaRequest,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    try:
        result = run_analyze(video_id, body.question, global_summary=v.global_summary)
    except Exception as exc:
        raise HTTPException(502, f"Analyze backend error: {exc}") from exc

    return success_response({
        "video_id": str(video_id),
        "question": body.question,
        "answer": result.answer,
        "citations": result.citations,
        "used_windows": result.used_windows,
        "used_segments": result.used_segments,
        "modality": v.modality,
    })
