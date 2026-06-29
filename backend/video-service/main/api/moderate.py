"""Content-moderation endpoints — UC #14.

Two surfaces:
  - Per-video detail (owner or admin): flagged shots for a video. For a `ready`
    video this reads `nsfw/violence/toxic_score` from each shot's Qdrant payload;
    for a quarantined (`flagged`) video — which was never upserted to Qdrant — it
    serves the stored verdict (`videos.moderation_detail`) instead.
  - Admin review (`require_admin`): list flagged videos, approve (re-index) or
    reject (quarantine → tombstone). See
    docs/superpowers/specs/2026-06-27-content-moderation-guardrail-design.md.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_admin, require_user
from cm_shared.db import get_session
from cm_shared.queue import VIDEO_INDEX_QUEUE, get_queue
from cm_shared.response import success_response
from main.models.video import IndexingJob, Video
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["moderate"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["moderate-admin"])


def _qdrant():
    from main.qdrant_util import get_qdrant_client

    return get_qdrant_client()


def _labels(v: Video) -> list[str]:
    return v.moderation_labels.split(",") if v.moderation_labels else []


@router.get("/{video_id}/moderate")
async def moderate(
    video_id: UUID,
    threshold: float = 0.5,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    v = await session.get(Video, video_id)
    if not v or (v.user_id != UUID(payload.sub) and payload.role != "admin"):
        raise HTTPException(404, "Video not found")

    # Quarantined videos aren't in Qdrant — serve the stored verdict.
    if v.status == "flagged":
        detail = v.moderation_detail or []
        return success_response({
            "video_id": str(video_id),
            "status": "flagged",
            "threshold": threshold,
            "summary": {
                "max_nsfw": v.nsfw_max or 0.0,
                "max_violence": v.violence_max or 0.0,
                "max_toxic": v.toxic_max or 0.0,
                "labels": _labels(v),
                "flagged_count": len(detail),
            },
            "flagged_shots": detail,
        })

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
    max_violence = 0.0
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
            vi = float(pl.get("violence_score", 0.0) or 0.0)
            t = float(pl.get("toxic_score", 0.0) or 0.0)
            max_nsfw = max(max_nsfw, n)
            max_violence = max(max_violence, vi)
            max_toxic = max(max_toxic, t)
            if max(n, vi, t) >= threshold:
                flagged.append({
                    "idx": pl.get("shot_idx"),
                    "t_start": pl.get("t_start"),
                    "t_end": pl.get("t_end"),
                    "nsfw_score": n,
                    "violence_score": vi,
                    "toxic_score": t,
                    "asr_text": pl.get("asr_text", ""),
                })
        if next_offset is None:
            break

    flagged.sort(key=lambda x: -max(x["nsfw_score"], x["violence_score"], x["toxic_score"]))

    return success_response({
        "video_id": str(video_id),
        "status": v.status,
        "threshold": threshold,
        "summary": {
            "max_nsfw": max_nsfw,
            "max_violence": max_violence,
            "max_toxic": max_toxic,
            "flagged_count": len(flagged),
        },
        "flagged_shots": flagged,
    })


@admin_router.get("/videos/flagged")
async def list_flagged(
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """All quarantined videos awaiting review, newest first."""
    rows = (
        await session.execute(
            select(Video).where(Video.status == "flagged").order_by(Video.created_at.desc())
        )
    ).scalars().all()
    return success_response({
        "flagged": [
            {
                "video_id": str(v.id),
                "user_id": str(v.user_id),
                "original_filename": v.original_filename,
                "labels": _labels(v),
                "nsfw_max": v.nsfw_max or 0.0,
                "violence_max": v.violence_max or 0.0,
                "toxic_max": v.toxic_max or 0.0,
                "flagged_count": len(v.moderation_detail or []),
                "created_at": v.created_at.isoformat(),
            }
            for v in rows
        ],
    })


@router.post("/{video_id}/moderation/approve")
async def approve(
    video_id: UUID,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Approve a quarantined video: re-index with the guardrail bypassed so it
    becomes searchable (`flagged` → `queued` → `ready`)."""
    v = await session.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status != "flagged":
        raise HTTPException(409, f"Video is not flagged (status={v.status})")
    v.moderation_override = True
    v.status = "queued"
    await session.commit()
    get_queue(VIDEO_INDEX_QUEUE).enqueue(
        "main.workers.queue_worker.index_video", str(video_id), job_timeout=3600,
    )
    return success_response({"video_id": str(video_id), "status": "queued"})


@router.post("/{video_id}/moderation/reject")
async def reject(
    video_id: UUID,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Reject a quarantined video: delete the source file and tombstone the row
    (`status='rejected'`). A flagged video was never indexed, so there is no
    Qdrant/timeline/feature data to clean up."""
    v = await session.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status != "flagged":
        raise HTTPException(409, f"Video is not flagged (status={v.status})")

    s = get_settings()
    from main.storage.minio import s3
    try:
        s3().delete_object(Bucket=s.minio_bucket_videos, Key=v.minio_key)
    except Exception:
        pass
    await session.execute(sa_delete(IndexingJob).where(IndexingJob.video_id == video_id))
    v.status = "rejected"
    v.moderation_detail = None
    await session.commit()
    return success_response({"video_id": str(video_id), "status": "rejected"})
