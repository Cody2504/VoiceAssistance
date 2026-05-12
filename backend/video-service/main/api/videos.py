from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.queue import VIDEO_INDEX_QUEUE, get_queue
from cm_shared.response import success_response
from cm_shared.schemas import VideoOut
from main.models.video import Video
from main.settings import get_settings
from main.storage.minio import presigned_get, s3

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    file: UploadFile = File(...),
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    s = get_settings()
    if not (file.filename or "").lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
        raise HTTPException(400, "Unsupported file extension (allowed: mp4/mov/mkv/webm)")

    video_id = uuid4()
    user_id = UUID(payload.sub)
    key = f"{user_id}/{video_id}.mp4"

    s3().upload_fileobj(file.file, s.minio_bucket_videos, key,
                        ExtraArgs={"ContentType": file.content_type or "video/mp4"})

    video = Video(
        id=video_id, user_id=user_id, original_filename=file.filename or "upload.mp4",
        minio_key=key, status="queued",
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)

    get_queue(VIDEO_INDEX_QUEUE).enqueue(
        "main.workers.queue_worker.index_video",
        str(video_id),
        job_timeout=3600,
    )

    return success_response(VideoOut.model_validate(video, from_attributes=True).model_dump(mode="json"))


@router.get("")
async def list_videos(payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    user_id = UUID(payload.sub)
    rows = (await session.execute(select(Video).where(Video.user_id == user_id).order_by(Video.created_at.desc()))).scalars().all()
    return success_response([VideoOut.model_validate(v, from_attributes=True).model_dump(mode="json") for v in rows])


@router.get("/{video_id}")
async def get_video(video_id: UUID, payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    return success_response(VideoOut.model_validate(v, from_attributes=True).model_dump(mode="json"))


@router.get("/{video_id}/stream")
async def stream_url(video_id: UUID, payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    s = get_settings()
    return success_response({"url": presigned_get(s.minio_bucket_videos, v.minio_key)})


@router.get("/{video_id}/thumb/{shot_idx}")
async def thumb_url(
    video_id: UUID,
    shot_idx: int,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Redirect to a presigned MinIO URL for a shot thumbnail.

    The indexing worker writes JPEGs to `thumbs/{video_id}/{idx}.jpg`. We use a 307 here
    so `<img src="...">` can render the JPEG directly without an extra auth round-trip.
    """
    from fastapi.responses import RedirectResponse

    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    s = get_settings()
    url = presigned_get(s.minio_bucket_thumbs, f"{video_id}/{shot_idx}.jpg")
    return RedirectResponse(url, status_code=307)
