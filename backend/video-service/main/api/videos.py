from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.queue import VIDEO_INDEX_QUEUE, get_queue
from cm_shared.response import success_response
from cm_shared.schemas import VideoOut
from main.models.video import IndexingJob, Video
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


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a video and its derived artifacts.

    Removes the row from Postgres, the MP4 from MinIO, any shot thumbnails and feature
    cache, plus every Qdrant point referencing this video_id. Cleanly handles videos
    in any status (queued/indexing/ready/error) — only the artifacts that exist are
    deleted; the rest is best-effort.
    """
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")

    s = get_settings()

    # MinIO: source mp4, shot thumbs (best-effort).
    try:
        s3().delete_object(Bucket=s.minio_bucket_videos, Key=v.minio_key)
    except Exception:
        pass
    try:
        s3().delete_object(Bucket=s.minio_bucket_videos, Key=f"features/{video_id}.npz")
    except Exception:
        pass
    try:
        objs = s3().list_objects_v2(Bucket=s.minio_bucket_thumbs, Prefix=f"{video_id}/")
        for obj in objs.get("Contents", []) or []:
            s3().delete_object(Bucket=s.minio_bucket_thumbs, Key=obj["Key"])
    except Exception:
        pass

    # Qdrant: drop every shot tied to this video_id.
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm
        client = QdrantClient(host=s.qdrant_host, port=s.qdrant_port)
        client.delete(
            collection_name=s.qdrant_collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]),
            ),
        )
    except Exception:
        pass

    # Postgres: clear FK-referencing rows first, then the video row.
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(IndexingJob).where(IndexingJob.video_id == video_id))
    await session.delete(v)
    await session.commit()
    return None


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
    """Return a presigned URL for a shot thumbnail (symmetric with /stream).

    The indexing worker writes JPEGs to ``thumbs/{video_id}/{idx}.jpg``. We return
    JSON ``{url}`` instead of a 307 redirect because ``<img src>`` does not send the
    Bearer token, so a redirect-guarded endpoint would fail before the redirect could
    fire. The frontend fetches the URL with axios (which carries the token) and then
    points ``<img src>`` at the presigned MinIO URL directly.
    """
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    s = get_settings()
    url = presigned_get(s.minio_bucket_thumbs, f"{video_id}/{shot_idx}.jpg")
    return success_response({"url": url})
