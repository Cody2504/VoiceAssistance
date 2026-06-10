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
from main.qdrant_util import to_vector_list
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
    from main.qdrant_util import get_qdrant_client
    return get_qdrant_client()


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from main.encoders.clipl_embedder import CLIPLEmbedder
        from main.encoders.config import config
        _embedder = CLIPLEmbedder(
            model_name_or_path=config.clipl_model_name,
            device=config.clipl_device,
        )
    return _embedder


def _embed_query(text: str):
    return _get_embedder().encode_text(text)


def _embed_image(data_url: str):
    """Embed a single still image into the same 768-d CLIP-L space as the
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
        query_vector=to_vector_list(qvec),
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


def _embed_image_tiles(data_url: str, grid: int):
    """Multi-crop (#6): full-image + per-crop CLIP-L vectors for the query image,
    so a small logo/object (washed out in the global embedding) is represented by
    its own crop vector."""
    import base64
    import binascii
    from io import BytesIO

    import numpy as np
    from PIL import Image

    from main.pipeline.image_tiling import tile_frames

    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        img = Image.open(BytesIO(base64.b64decode(raw, validate=False))).convert("RGB")
    except (binascii.Error, ValueError, OSError) as exc:
        raise HTTPException(400, f"Invalid image data: {exc}") from exc
    frames = np.asarray(img, dtype=np.uint8)[None, ...]  # [1, H, W, 3]
    emb = _get_embedder()
    vecs = [emb.encode_video(frames)]                    # full image
    for _region, crop in tile_frames(frames, grid):
        if crop is not None and len(crop):
            vecs.append(emb.encode_video(crop))
    return vecs


def _corpus_shots_multi(qvecs, video_meta: dict, top_n: int, group_by: str) -> list[dict]:
    """Multi-crop corpus search (#6): search jockey_shots with each crop vector,
    merge by (video_id, shot_idx) keeping the max score, then format."""
    from qdrant_client.http import models as qm

    from main.pipeline.image_tiling import merge_hits_by_shot
    s = get_settings()
    flt = qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys())))])
    per_query: list[list[dict]] = []
    for qv in qvecs:
        hits = _qdrant().search(
            collection_name=s.qdrant_collection,
            query_vector=to_vector_list(qv),
            query_filter=flt, limit=top_n * 5,
        )
        per_query.append([
            {"video_id": h.payload["video_id"], "shot_idx": h.payload["shot_idx"],
             "t_start": h.payload["t_start"], "t_end": h.payload["t_end"],
             "asr_text": h.payload.get("asr_text", ""), "ocr_text": h.payload.get("ocr_text", ""),
             "audio_tags": h.payload.get("audio_tags", []), "score": float(h.score)}
            for h in hits
        ])
    merged = merge_hits_by_shot(per_query, top_n * 5)
    shots: list[dict] = []
    seen: set[str] = set()
    for h in merged:
        vid = h["video_id"]
        if group_by == "video":
            if vid in seen:
                continue
            seen.add(vid)
        meta = video_meta.get(vid, {})
        shots.append({
            "video_id": vid, "original_filename": meta.get("original_filename", ""),
            "video_duration_s": meta.get("duration_s"), "idx": h["shot_idx"],
            "t_start": h["t_start"], "t_end": h["t_end"], "asr_text": h["asr_text"],
            "ocr_text": h["ocr_text"], "audio_tags": h["audio_tags"], "score": h["score"],
        })
        if len(shots) >= top_n:
            break
    return shots


@router.post("/search/motion")
async def search_corpus_motion(
    body: CorpusSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Motion search (research A): ViCLIP text→video retrieval over
    `jockey_motion` — temporal matching for actions/movement that
    appearance-only CLIP-L conflates ("adding tomato" vs "tomato visible")."""
    s = get_settings()
    if not s.motion_enabled:
        raise HTTPException(503, "Motion search is not enabled on this deployment")
    video_meta = await _user_ready_video_meta(session, UUID(payload.sub))
    if not video_meta:
        return success_response({"query": body.query, "group_by": body.group_by, "shots": []})

    from main.encoders.motion_encoder import MotionEncoder
    enc = MotionEncoder.from_settings(s)
    qvec = enc.encode_text(body.query) if enc.is_available() else None
    if qvec is None:
        raise HTTPException(503, "Motion encoder unavailable (ViCLIP weights missing?)")

    from qdrant_client.http import models as qm
    fetch_limit = body.top_n * 5 if body.group_by == "video" else body.top_n
    hits = _qdrant().search(
        collection_name=s.motion_collection,
        query_vector=to_vector_list(qvec),
        query_filter=qm.Filter(must=[
            qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys()))),
        ]),
        limit=fetch_limit,
    )
    shots: list[dict] = []
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
            "idx": h.payload.get("segment_idx"),
            "t_start": h.payload["t_start"],
            "t_end": h.payload["t_end"],
            "caption": h.payload.get("caption", ""),
            "score": float(h.score),
        })
        if len(shots) >= body.top_n:
            break
    return success_response({"query": body.query, "group_by": body.group_by, "shots": shots})


@router.post("/search/image")
async def search_corpus_image(
    body: CorpusImageSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """@Entity image-as-query: find the moments across the user's videos that
    look most like the supplied image (CLIP-L visual embedding → jockey_shots)."""
    video_meta = await _user_ready_video_meta(session, UUID(payload.sub))
    if not video_meta:
        return success_response({"query": "(image)", "group_by": body.group_by, "shots": []})
    s = get_settings()
    if s.image_tiling_enabled:
        shots = _corpus_shots_multi(
            _embed_image_tiles(body.image, s.image_tile_grid), video_meta, body.top_n, body.group_by,
        )
    else:
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
        query_vector=to_vector_list(qvec),
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
        query_vector=to_vector_list(qvec),
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
