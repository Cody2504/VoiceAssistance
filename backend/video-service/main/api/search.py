from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import GroundQuery
from main.models.video import Video
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/videos", tags=["search"])


def _qdrant():
    from qdrant_client import QdrantClient
    s = get_settings()
    return QdrantClient(host=s.qdrant_host, port=s.qdrant_port)


def _embed_query(text: str):
    from jockey.open_source.viclip_embedder import embed_text  # type: ignore
    return embed_text(text)


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
