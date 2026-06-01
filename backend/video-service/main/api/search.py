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


class CorpusImageSearchQuery(BaseModel):
    # base64 data URL (e.g. "data:image/png;base64,..."); kept consistent with
    # SegmentDefinition.image_attachment so the frontend round-trips uniformly.
    image: str = Field(min_length=1)
    top_n: int = Field(default=10, ge=1, le=50)
    group_by: Literal["clip", "video"] = "clip"


class ImageQuery(BaseModel):
    image: str = Field(min_length=1)


def _qdrant():
    from qdrant_client import QdrantClient
    s = get_settings()
    return QdrantClient(host=s.qdrant_host, port=s.qdrant_port)


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from main.encoders.viclip_embedder import ViCLIPEmbedder
        from main.encoders.config import config
        _embedder = ViCLIPEmbedder(
            model_name_or_path=config.viclip_model_name,
            device=config.viclip_device,
        )
    return _embedder


def _embed_query(text: str):
    return _get_embedder().encode_text(text)


def _embed_image(data_url: str):
    """Embed a single still image into the same 768-d ViCLIP space as the
    `jockey_shots` vectors — a one-frame "video". Accepts a base64 data URL or
    bare base64. Raises HTTPException(400) on undecodable input."""
    import base64
    import binascii
    from io import BytesIO

    import numpy as np

    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        img_bytes = base64.b64decode(raw, validate=False)
        from PIL import Image
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
    except (binascii.Error, ValueError, OSError) as exc:
        raise HTTPException(400, f"Invalid image data: {exc}") from exc
    frames = np.asarray(img, dtype=np.uint8)[None, ...]  # [1, H, W, 3]
    return _get_embedder().encode_video(frames)


@router.post("/search")
async def search_corpus(
    body: CorpusSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Search across all of the requesting user's ready videos."""
    video_meta = await _user_ready_video_meta(session, UUID(payload.sub))
    if not video_meta:
        return success_response({"query": body.query, "shots": []})

    shots = _corpus_shots(_embed_query(body.query), video_meta, body.top_n, body.group_by)
    return success_response({"query": body.query, "group_by": body.group_by, "shots": shots})


async def _user_ready_video_meta(session: AsyncSession, user_id: UUID) -> dict:
    rows = (await session.execute(
        select(Video.id, Video.original_filename, Video.duration_s).where(
            Video.user_id == user_id, Video.status == "ready",
        )
    )).all()
    return {
        str(r.id): {"original_filename": r.original_filename, "duration_s": r.duration_s}
        for r in rows
    }


def _corpus_shots(qvec, video_meta: dict, top_n: int, group_by: str) -> list[dict]:
    """Shared corpus retrieval: query vector (from text OR image) → jockey_shots
    hits → formatted shot dicts, with optional dedupe-by-video."""
    s = get_settings()
    from qdrant_client.http import models as qm
    fetch_limit = top_n * 5 if group_by == "video" else top_n
    hits = _qdrant().search(
        collection_name=s.qdrant_collection,
        query_vector=qvec.tolist() if hasattr(qvec, "tolist") else list(qvec),
        query_filter=qm.Filter(must=[
            qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys()))),
        ]),
        limit=fetch_limit,
    )
    shots: list[dict] = []
    seen_videos: set[str] = set()
    for h in hits:
        vid = h.payload["video_id"]
        if group_by == "video":
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
        if len(shots) >= top_n:
            break
    return shots


@router.post("/search/image")
async def search_corpus_image(
    body: CorpusImageSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """@Entity image-as-query: find the moments across the user's videos that
    look most like the supplied image (ViCLIP visual embedding → jockey_shots)."""
    video_meta = await _user_ready_video_meta(session, UUID(payload.sub))
    if not video_meta:
        return success_response({"query": "(image)", "group_by": body.group_by, "shots": []})
    shots = _corpus_shots(_embed_image(body.image), video_meta, body.top_n, body.group_by)
    return success_response({"query": "(image)", "group_by": body.group_by, "shots": shots})


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


@router.post("/{video_id}/search/image")
async def search_image(
    video_id: UUID,
    body: ImageQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """@Entity image-as-query within a single video."""
    v = await session.get(Video, video_id)
    if not v or v.user_id != UUID(payload.sub):
        raise HTTPException(404, "Video not found")
    if v.status != "ready":
        raise HTTPException(409, f"Video is not ready (status={v.status})")

    s = get_settings()
    qvec = _embed_image(body.image)
    from qdrant_client.http import models as qm
    hits = _qdrant().search(
        collection_name=s.qdrant_collection,
        query_vector=qvec.tolist() if hasattr(qvec, "tolist") else list(qvec),
        query_filter=qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]),
        limit=10,
    )
    return success_response({
        "video_id": str(video_id),
        "query": "(image)",
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
