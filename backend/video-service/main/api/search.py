from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import GroundQuery
from main.models.video import Video
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["search"])


class CorpusSearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    top_n: int = Field(default=10, ge=1, le=50)
    group_by: Literal["clip", "video"] = "clip"


def _qdrant():
    from qdrant_client import QdrantClient
    s = get_settings()
    return QdrantClient(host=s.qdrant_host, port=s.qdrant_port)


_embedder = None


def _embed_query(text: str):
    global _embedder
    if _embedder is None:
        from jockey.open_source.viclip_embedder import ViCLIPEmbedder
        from jockey.open_source.config import config
        _embedder = ViCLIPEmbedder(
            model_name_or_path=config.viclip_model_name,
            device=config.viclip_device,
        )
    return _embedder.encode_text(text)


@router.post("/search")
async def search_corpus(
    body: CorpusSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Search across all of the requesting user's ready videos."""
    user_id = UUID(payload.sub)
    rows = (await session.execute(
        select(Video.id, Video.original_filename, Video.duration_s).where(
            Video.user_id == user_id, Video.status == "ready",
        )
    )).all()
    video_meta = {
        str(r.id): {"original_filename": r.original_filename, "duration_s": r.duration_s}
        for r in rows
    }
    if not video_meta:
        return success_response({"query": body.query, "shots": []})

    s = get_settings()
    qvec = _embed_query(body.query)
    from qdrant_client.http import models as qm
    fetch_limit = body.top_n * 5 if body.group_by == "video" else body.top_n
    hits = _qdrant().search(
        collection_name=s.qdrant_collection,
        query_vector=qvec.tolist() if hasattr(qvec, "tolist") else list(qvec),
        query_filter=qm.Filter(must=[
            qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys()))),
        ]),
        limit=fetch_limit,
    )

    shots = []
    seen_videos: set[str] = set()
    for h in hits:
        vid = h.payload["video_id"]
        if body.group_by == "video":
            if vid in seen_videos:
                continue
            seen_videos.add(vid)
        meta = video_meta.get(vid, {})
        shots.append({
            "video_id": vid,
            "original_filename": meta.get("original_filename", ""),
            "video_duration_s": meta.get("duration_s"),
            "idx": h.payload["shot_idx"],
            "t_start": h.payload["t_start"],
            "t_end": h.payload["t_end"],
            "asr_text": h.payload.get("asr_text", ""),
            "ocr_text": h.payload.get("ocr_text", ""),
            "audio_tags": h.payload.get("audio_tags", []),
            "score": float(h.score),
        })
        if len(shots) >= body.top_n:
            break

    return success_response({"query": body.query, "group_by": body.group_by, "shots": shots})


@router.post("/{video_id}/search")
async def search(
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

    s = get_settings()
    qvec = _embed_query(body.query)
    from qdrant_client.http import models as qm
    hits = _qdrant().search(
        collection_name=s.qdrant_collection,
        query_vector=qvec.tolist() if hasattr(qvec, "tolist") else list(qvec),
        query_filter=qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]),
        limit=10,
    )
    return success_response({
        "video_id": str(video_id),
        "query": body.query,
        "shots": [
            {
                "idx": h.payload["shot_idx"],
                "t_start": h.payload["t_start"],
                "t_end": h.payload["t_end"],
                "asr_text": h.payload.get("asr_text", ""),
                "score": float(h.score),
            }
            for h in hits
        ],
    })
