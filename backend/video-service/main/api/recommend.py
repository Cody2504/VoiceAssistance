"""Recommendations endpoint — closes UC #11.

Returns videos in the user's namespace most similar to a seed video by cosine
over the mean-pooled caption embedding stored in the `jockey_videos` Qdrant
collection (written at ingest time by pipeline/ingest.py stage 7b).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import Video

router = APIRouter(prefix="/api/v1/videos", tags=["recommend"])

META_COLLECTION = "jockey_videos"


def _qdrant():
    from main.qdrant_util import get_qdrant_client

    return get_qdrant_client()


@router.get("/{video_id}/similar")
async def similar(
    video_id: UUID,
    top_k: int = 5,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Top-K most similar videos to `video_id` in the requesting user's namespace.

    Cosine similarity over mean-pooled caption (3072-d text-embedding-3-large)
    embeddings — no new model required; just a different cut of existing data.
    """
    user_id = UUID(payload.sub)

    v = await session.get(Video, video_id)
    if not v or v.user_id != user_id:
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    client = _qdrant()
    try:
        collections = {c.name for c in client.get_collections().collections}
    except Exception as exc:
        raise HTTPException(503, f"Qdrant unreachable: {exc}")

    if META_COLLECTION not in collections:
        return success_response({"video_id": str(video_id), "results": [], "reason": "no metadata collection yet — re-ingest required"})

    # Fetch the seed video's vector from the collection
    from qdrant_client.http import models as qm

    points, _ = client.scroll(
        collection_name=META_COLLECTION,
        scroll_filter=qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]),
        limit=1,
        with_payload=False,
        with_vectors=True,
    )
    if not points:
        return success_response({"video_id": str(video_id), "results": [], "reason": "seed video has no metadata embedding (re-ingest needed)"})

    seed_vec = points[0].vector
    if isinstance(seed_vec, dict):  # Qdrant returns dict if multi-vector
        seed_vec = next(iter(seed_vec.values()))

    # Search within the user's namespace, exclude the seed video
    hits = client.search(
        collection_name=META_COLLECTION,
        query_vector=list(seed_vec),
        query_filter=qm.Filter(
            must=[qm.FieldCondition(key="user_id", match=qm.MatchValue(value=str(user_id)))],
            must_not=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))],
        ),
        limit=max(1, min(int(top_k), 20)),
    )

    # Annotate with Postgres metadata
    other_ids = [UUID(str(h.payload["video_id"])) for h in hits]
    rows = (await session.execute(
        select(Video.id, Video.original_filename, Video.duration_s, Video.shot_count, Video.created_at)
        .where(Video.id.in_(other_ids), Video.user_id == user_id, Video.status == "ready")
    )).all()
    meta = {str(r.id): r for r in rows}

    results = []
    for h in hits:
        vid = str(h.payload["video_id"])
        m = meta.get(vid)
        if not m:
            continue
        results.append({
            "video_id": vid,
            "original_filename": m.original_filename,
            "duration_s": m.duration_s,
            "shot_count": m.shot_count,
            "score": float(h.score),
        })

    return success_response({"video_id": str(video_id), "results": results})
