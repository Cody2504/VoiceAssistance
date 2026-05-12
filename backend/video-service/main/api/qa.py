from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video
from main.storage.minio import presigned_get
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["qa"])


class QaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2048)
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

    s = get_settings()
    video_url = presigned_get(s.minio_bucket_videos, v.minio_key, expires=3600)

    try:
        from jockey.open_source.video_qa import VideoQA  # type: ignore
        client = VideoQA()
        answer = client.ask(video_url=video_url, question=body.question, t_start=body.t_start, t_end=body.t_end)
    except Exception as exc:
        raise HTTPException(502, f"QA backend error: {exc}") from exc

    return success_response({"video_id": str(video_id), "question": body.question, "answer": answer})
