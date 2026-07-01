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
    # VLM-verify the candidates against the query image (drops the unrelated tail
    # that CLIP-L score-ranks next on a small/mixed corpus). Default on; the
    # verifier no-ops to "keep all" when OpenRouter isn't configured.
    verify: bool = True


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


_text_embedder = None


def _get_text_embedder():
    global _text_embedder
    if _text_embedder is None:
        from main.encoders.search import TextEmbedder
        _text_embedder = TextEmbedder(api_key=get_settings().openrouter_api_key)
    return _text_embedder


def _embed_text_rag(text: str):
    """text-embedding-3-large query vector for the jockey_segments_text collection
    (caption + transcript + on-screen OCR) — the same model that indexed those vectors."""
    return _get_text_embedder().encode(text)


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


def _rgb_from_data_url(data_url: str):
    """Decode a base64 data URL (or bare base64) to an HxWx3 uint8 RGB array, for the
    LightGlue verifier. Same input handling as `_embed_image`."""
    import base64
    import binascii
    from io import BytesIO

    import numpy as np

    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        from PIL import Image
        img = Image.open(BytesIO(base64.b64decode(raw, validate=False))).convert("RGB")
    except (binascii.Error, ValueError, OSError) as exc:
        raise HTTPException(400, f"Invalid image data: {exc}") from exc
    return np.asarray(img, dtype=np.uint8)


_dino_embedder = None


def _get_dino_embedder():
    global _dino_embedder
    if _dino_embedder is None:
        from main.encoders.dino_embedder import DINOv2Embedder
        s = get_settings()
        _dino_embedder = DINOv2Embedder(
            model_name_or_path=s.dino_model, device=(s.dino_device or "cuda"),
        )
    return _dino_embedder


def _embed_image_dino(data_url: str):
    """Embed the query image with DINOv2 (instance channel) into the jockey_dino
    space. Same base64/data-URL handling as `_embed_image`."""
    import base64
    import binascii
    from io import BytesIO

    import numpy as np
    from PIL import Image

    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        img = Image.open(BytesIO(base64.b64decode(raw, validate=False))).convert("RGB")
    except (binascii.Error, ValueError, OSError) as exc:
        raise HTTPException(400, f"Invalid image data: {exc}") from exc
    frames = np.asarray(img, dtype=np.uint8)[None, ...]
    return _get_dino_embedder().encode_video(frames)


def _query_ocr_text(data_url: str) -> str:
    """OCR the query image with the same engine used at ingest. Best-effort: ''
    on any failure (no GPU OCR, bad image) so it simply contributes no signal."""
    import base64
    from io import BytesIO

    import numpy as np
    from PIL import Image

    try:
        raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
        img = Image.open(BytesIO(base64.b64decode(raw, validate=False))).convert("RGB")
        from main.encoders.ocr_encoder import OCREncoder
        enc = OCREncoder(device=(get_settings().dino_device or "cuda"))
        return (enc.extract_from_frame(np.asarray(img, dtype=np.uint8)) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


# An OCR match this many distinct content tokens deep is treated as a near-certain
# identity signal (a title card / player name), strong enough to pin ahead of the
# unreliable VLM verifier. One coincidental shared word (e.g. "tennis") is below it.
_STRONG_OCR_OVERLAP = 2


def _corpus_shots_ocr(query_ocr: str, video_meta: dict, top_n: int) -> tuple[list[dict], list]:
    """OCR *retrieval* stream: scroll the user's indexed shots and return those
    whose stored `ocr_text` shares content tokens with the query frame's OCR,
    ranked by overlap (desc).

    Returns `(shots, strong_keys)` where `strong_keys` is the (video_id, idx)
    tuples — best-first — whose overlap clears `_STRONG_OCR_OVERLAP` (pinned ahead
    of the VLM verifier by the endpoint).

    This is the signal that recovers a visually-confusable correct video — one
    CLIP-L/DINOv2 never surface among their nearest neighbours — by its on-screen
    title text (e.g. a show title or player name). Without it, OCR could only
    re-rank shots already in the visual pool, so a title-card frame whose video
    isn't a CLIP neighbour was unreachable. Best-effort: empty query or any
    Qdrant error → ([], []) (the stream simply contributes nothing)."""
    from main.search.ocr_match import _tokens
    q = _tokens(query_ocr)
    if not q:
        return [], []
    s = get_settings()
    from qdrant_client.http import models as qm
    flt = qm.Filter(must=[qm.FieldCondition(
        key="video_id", match=qm.MatchAny(any=list(video_meta.keys())))])
    best: dict = {}  # (video_id, shot_idx) -> (overlap, shot dict)
    next_offset = None
    scanned = 0
    try:
        while True:
            points, next_offset = _qdrant().scroll(
                collection_name=s.qdrant_collection, scroll_filter=flt,
                limit=256, offset=next_offset, with_payload=True, with_vectors=False,
            )
            for p in points:
                pl = p.payload or {}
                ocr = pl.get("ocr_text") or ""
                vid, idx = pl.get("video_id"), pl.get("shot_idx")
                if not ocr or vid is None or idx is None or pl.get("t_start") is None:
                    continue
                overlap = len(q & _tokens(ocr))
                if overlap <= 0:
                    continue
                key = (vid, idx)
                cur = best.get(key)
                if cur is None or overlap > cur[0]:
                    meta = video_meta.get(vid, {})
                    best[key] = (overlap, {
                        "video_id": vid, "original_filename": meta.get("original_filename", ""),
                        "video_duration_s": meta.get("duration_s"), "idx": idx,
                        "t_start": pl.get("t_start"), "t_end": pl.get("t_end"),
                        "asr_text": pl.get("asr_text", ""), "ocr_text": ocr,
                        "audio_tags": pl.get("audio_tags", []), "score": 0.0,
                    })
            scanned += len(points)
            if next_offset is None or scanned >= 5000:  # safety bound for large corpora
                break
    except Exception:  # noqa: BLE001 — best-effort stream, never breaks search
        return [], []
    ranked = sorted(best.values(), key=lambda t: t[0], reverse=True)
    shots = [shot for _, shot in ranked[: max(top_n, 10)]]
    strong_keys = [(shot["video_id"], shot["idx"]) for ov, shot in ranked if ov >= _STRONG_OCR_OVERLAP]
    return shots, strong_keys


def _corpus_shots_dino(qvec, video_meta: dict, top_n: int) -> list[dict]:
    """CLIP-shaped corpus retrieval against the jockey_dino collection. Returns
    [] (never raises) when the collection is missing/unsearchable (e.g. before
    the first fine re-index)."""
    s = get_settings()
    from qdrant_client.http import models as qm
    try:
        hits = _qdrant().search(
            collection_name=s.dino_collection,
            query_vector=to_vector_list(qvec),
            query_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys()))),
            ]),
            limit=top_n * 5,
        )
    except Exception:  # noqa: BLE001 — collection not present yet, etc.
        return []
    shots: list[dict] = []
    for h in hits:
        vid = h.payload["video_id"]
        meta = video_meta.get(vid, {})
        shots.append({
            "video_id": vid, "original_filename": meta.get("original_filename", ""),
            "video_duration_s": meta.get("duration_s"), "idx": h.payload["shot_idx"],
            "t_start": h.payload["t_start"], "t_end": h.payload["t_end"],
            "asr_text": h.payload.get("asr_text", ""), "ocr_text": h.payload.get("ocr_text", ""),
            "audio_tags": h.payload.get("audio_tags", []), "score": float(h.score),
        })
    return shots


def _corpus_shots_region(qvec, video_meta: dict, top_n: int) -> list[dict]:
    """Region-instance retrieval against jockey_regions (DINOv2 embeddings of the
    object/logo regions detected at ingest). Unlike `_corpus_shots_dino` (one vector
    per whole frame, where a clean logo/object query is dominated by the background),
    this matches the query against the regions themselves — background-invariant.
    Keeps the best region per (video_id, shot_idx). Returns [] when the collection is
    absent (before the first region re-index) — never raises."""
    s = get_settings()
    from qdrant_client.http import models as qm
    try:
        hits = _qdrant().search(
            collection_name=s.regions_collection,
            query_vector=to_vector_list(qvec),
            query_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys()))),
            ]),
            limit=top_n * 10,  # several regions per shot — collapse to best below
        )
    except Exception:  # noqa: BLE001 — collection not present yet, etc.
        return []
    best: dict = {}
    for h in hits:
        vid = h.payload["video_id"]
        idx = h.payload["shot_idx"]
        key = (vid, idx)
        score = float(h.score)
        if key in best and best[key]["score"] >= score:
            continue
        meta = video_meta.get(vid, {})
        best[key] = {
            "video_id": vid, "original_filename": meta.get("original_filename", ""),
            "video_duration_s": meta.get("duration_s"), "idx": idx,
            "t_start": h.payload["t_start"], "t_end": h.payload["t_end"],
            "asr_text": "", "ocr_text": "", "audio_tags": [], "score": score,
        }
    return sorted(best.values(), key=lambda sh: sh["score"], reverse=True)[: max(top_n, 10)]


_ve_embedder = None


def _get_text_embedder():
    """Same TextEmbedder + model the caption embeddings use (config.text_embedding_model),
    so index and query land in the same space. Constructed like _embed_captions."""
    global _ve_embedder
    if _ve_embedder is None:
        from main.encoders.search import TextEmbedder
        from main.encoders.config import config
        _ve_embedder = TextEmbedder(api_key=config.openrouter_api_key,
                                    model=config.text_embedding_model,
                                    base_url=config.openrouter_base_url)
    return _ve_embedder


def _corpus_shots_visual_entities(query: dict, video_meta: dict, top_n: int) -> list[dict]:
    """Visual-entities retrieval against jockey_visual_entities: semantic search of the
    query description + keyword boost on recognized brand/wordmark tokens. Returns []
    when the collection is absent (pre-backfill) — never raises."""
    s = get_settings()
    from qdrant_client.http import models as qm
    from main.search.visual_entities_rank import rank_with_keyword_boost
    desc = (query or {}).get("description") or ""
    tokens = (query or {}).get("tokens") or []
    if not desc:
        return []
    try:
        qvec = _get_text_embedder().encode(desc)  # encode(str) -> np.ndarray
        hits = _qdrant().search(
            collection_name=s.visual_entities_collection,
            query_vector=list(map(float, qvec)),
            query_filter=qm.Filter(must=[qm.FieldCondition(
                key="video_id", match=qm.MatchAny(any=list(video_meta.keys())))]),
            limit=max(top_n, 10) * 5,
        )
    except Exception:  # noqa: BLE001 — collection missing / infra
        return []
    cands = []
    for h in hits:
        vid = h.payload["video_id"]
        meta = video_meta.get(vid, {})
        cands.append({
            "video_id": vid, "original_filename": meta.get("original_filename", ""),
            "video_duration_s": meta.get("duration_s"), "idx": h.payload["shot_idx"],
            "t_start": h.payload["t_start"], "t_end": h.payload["t_end"],
            "asr_text": "", "ocr_text": "", "audio_tags": [],
            "visual_entities": h.payload.get("visual_entities", ""), "score": float(h.score),
        })
    ranked = rank_with_keyword_boost(cands, tokens, s.visual_entities_keyword_boost)
    for c in ranked:
        c["score"] = c.pop("score_boosted")
    return ranked[: max(top_n, 10)]


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

    s = get_settings()
    shots = _corpus_shots(
        _embed_query(body.query), video_meta, body.top_n, body.group_by,
        min_score=s.corpus_search_min_score,
        exclude_crops=s.shot_search_exclude_tiles,
        merge_gap_s=s.shot_search_merge_gap_s,
    )
    return success_response({"query": body.query, "group_by": body.group_by, "shots": shots})


@router.post("/search/text")
async def search_corpus_text(
    body: CorpusSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Corpus-wide TEXT-RAG search over caption + transcript + on-screen OCR
    (jockey_segments_text), across all the user's ready videos. For spoken-words /
    on-screen-text / specific-phrase queries that CLIP-L visual search (/search)
    can't read — a scoreboard's numbers, what a speaker says. No Index required."""
    video_meta = await _user_ready_video_meta(session, UUID(payload.sub))
    if not video_meta:
        return success_response({"query": body.query, "shots": []})
    shots = _corpus_shots(
        _embed_text_rag(body.query), video_meta, body.top_n, body.group_by,
        min_score=get_settings().corpus_text_min_score,
        collection="jockey_segments_text",
    )
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


def _corpus_shots(qvec, video_meta: dict, top_n: int, group_by: str, min_score: float = 0.0,
                  collection: str | None = None, exclude_crops: bool = False,
                  merge_gap_s: float | None = None) -> list[dict]:
    """Shared corpus retrieval: query vector (CLIP-L visual, image, OR text-RAG) →
    `collection` hits → formatted shot dicts, with optional dedupe-by-video.
    `collection` defaults to the visual jockey_shots; the text endpoint passes
    jockey_segments_text (caption + transcript + on-screen OCR).

    `min_score` drops hits below an absolute cosine floor — used by TEXT search so
    a no-match query ("snowboarding" over a tennis/cooking corpus) returns [] rather
    than the top-N noise. Image search passes 0.0 (its fusion + VLM verify prune).

    `exclude_crops` skips the image-tiling crop points in jockey_shots (whole-frame
    points only) — for TEXT→shot search, where the crops duplicate a shot 5× and
    carry no asr_text. `merge_gap_s` (when set) collapses back-to-back shots of the
    same video into one clip after retrieval."""
    s = get_settings()
    from qdrant_client.http import models as qm
    merging = merge_gap_s is not None
    fetch_limit = top_n * 5 if (group_by == "video" or min_score > 0 or merging) else top_n
    must = [qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys())))]
    if exclude_crops:
        must.append(qm.IsEmptyCondition(is_empty=qm.PayloadField(key="crop")))
    hits = _qdrant().search(
        collection_name=collection or s.qdrant_collection,
        query_vector=to_vector_list(qvec),
        query_filter=qm.Filter(must=must),
        limit=fetch_limit,
    )
    shots: list[dict] = []
    seen_videos: set[str] = set()
    for h in hits:
        if min_score > 0 and float(h.score) < min_score:
            continue
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
            "caption": h.payload.get("caption", ""),
            "audio_tags": h.payload.get("audio_tags", []),
            "score": float(h.score),
        })
        # When merging we need the whole candidate pool first; truncate afterwards.
        if not merging and len(shots) >= top_n:
            break
    if merging:
        from main.search.shot_merge import merge_contiguous_shots
        shots = merge_contiguous_shots(shots, merge_gap_s)[:top_n]
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


def _rerank_motion_by_caption(query: str, shots: list[dict], top_n: int) -> list[dict]:
    """Keep only the candidates whose caption ACTUALLY depicts the queried action,
    best-match first. ViCLIP motion cosine (and text embeddings) can't isolate a fine
    action like 'dunking' when every candidate is the same sport — scores cluster in a
    razor-thin band and irrelevant clips (a player walking, smiling) outrank the real
    one. An LLM reading the captions resolves it. Fail-soft: returns the raw motion
    order on any error or when OpenRouter is unconfigured (never empties the result)."""
    import json as _json
    import logging
    import re as _re
    s = get_settings()
    captioned = [sh for sh in shots if (sh.get("caption") or "").strip()]
    if not s.openrouter_api_key or len(captioned) <= 1:
        return shots[:top_n]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)
        lines = "\n".join(f"[{i}] {(sh.get('caption') or '')[:280]}" for i, sh in enumerate(shots))
        prompt = (
            f'A user searched for: "{query}".\n'
            "Below are candidate video clips with captions. Return ONLY a JSON array of the "
            "clip indices that ACTUALLY depict that action, ordered best-match first. EXCLUDE "
            "clips that do not clearly show it. If none match, return [].\n\n" + lines
        )
        resp = client.chat.completions.create(
            model=s.summary_llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=20,
        )
        m = _re.search(r"\[.*\]", resp.choices[0].message.content or "", _re.S)
        order = _json.loads(m.group(0)) if m else []
        kept = [shots[i] for i in order if isinstance(i, int) and 0 <= i < len(shots)]
        return (kept or shots)[:top_n]
    except Exception as exc:
        logging.getLogger(__name__).warning("motion:caption rerank failed: %s", exc)
        return shots[:top_n]


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
    # Over-fetch so the caption re-rank has candidates to filter/reorder — the raw
    # ViCLIP top-N is noisy for fine actions (see _rerank_motion_by_caption).
    fetch_limit = body.top_n * 5 if body.group_by == "video" else max(body.top_n * 3, 12)
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
    # An LLM reads the captions and keeps only clips that actually depict the queried
    # action (drops "walks through crowd" for a "dunking" query), best-match first.
    shots = _rerank_motion_by_caption(body.query, shots, body.top_n)
    return success_response({"query": body.query, "group_by": body.group_by, "shots": shots})


# Cap the candidates handed to the VLM (one multi-image call, but very long
# corpora shouldn't pay for 50 thumbnails). The agent sends top_n=5, so this
# only bites the playground's larger top_n; anything past the cap is kept as-is.
_MAX_VERIFY = 12


def _thumb_bytes(s, video_id: str, shot_idx) -> bytes | None:
    """Read a shot's cached keyframe JPEG straight from MinIO (same container,
    so no presigned-URL round trip). Returns None when no thumbnail exists."""
    from main.storage.minio import s3
    try:
        resp = s3().get_object(Bucket=s.minio_bucket_thumbs, Key=f"{video_id}/{shot_idx}.jpg")
        return resp["Body"].read()
    except Exception:
        return None


def _verify_shots(image: str, shots: list[dict]) -> list[dict]:
    """VLM re-rank: reorder candidates best-first by likelihood of being the same
    source video (matching title text / logo / scene), dropping rejects.

    Candidates whose thumbnail is missing are dropped (they render as broken
    cards and can't be verified anyway — the grey '0:00' tile). Falls back to the
    single best shot if the VLM clears none, so "which video is this from?" still
    answers. The verifier no-ops to keep-all-in-order when OpenRouter is
    unconfigured, so this never empties a result on infra issues."""
    if not shots:
        return shots
    s = get_settings()
    head, tail = shots[:_MAX_VERIFY], shots[_MAX_VERIFY:]
    valid: list[dict] = []
    jpegs: list[bytes] = []
    for sh in head:
        b = _thumb_bytes(s, sh["video_id"], sh["idx"])
        if b is None:
            continue
        valid.append(sh)
        jpegs.append(b)
    if not valid:
        return shots[:1]
    from main.encoders.image_verify import verify_image_matches_ranked
    order = verify_image_matches_ranked(image, jpegs)  # 1-based, best-first
    reranked = [valid[i - 1] for i in order if 1 <= i <= len(valid)] or valid[:1]
    return reranked + tail


@router.post("/search/image")
async def search_corpus_image(
    body: CorpusImageSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """@Entity image-as-query: find the moments across the user's videos that
    look most like the supplied image. Multi-signal: CLIP-L (semantic) + DINOv2
    (instance) + OCR-text, fused by Reciprocal Rank Fusion, deduped, then the VLM
    verifier re-ranks the survivors. Fixes generic/title-card frames where CLIP
    alone ranks a different same-category video first."""
    video_meta = await _user_ready_video_meta(session, UUID(payload.sub))
    if not video_meta:
        return success_response({"query": "(image)", "group_by": body.group_by, "shots": []})
    s = get_settings()

    # Visual-entities path (primary when enabled): describe the query image with the
    # 32B VLM, then semantic + keyword retrieval over jockey_visual_entities. Falls
    # through to the existing CLIP/DINO/OCR fusion on any miss (VLM off/error/empty).
    if s.visual_entities_search_enabled:
        from main.search.visual_entities_query import describe_query_image
        q = describe_query_image(body.image)
        if q:
            ve_shots = _corpus_shots_visual_entities(q, video_meta, body.top_n)
            if ve_shots:
                shots = ve_shots
                if body.group_by == "video":
                    seen, grouped = set(), []
                    for sh in shots:
                        if sh["video_id"] in seen:
                            continue
                        seen.add(sh["video_id"]); grouped.append(sh)
                    shots = grouped
                return success_response({"query": "(image)", "group_by": body.group_by,
                                         "shots": shots[: body.top_n]})

    # CLIP-L candidates — always in "clip" mode so fusion sees every shot; the
    # group_by collapse happens AFTER fusion + verify (below).
    if s.image_tiling_enabled:
        clip_shots = _corpus_shots_multi(
            _embed_image_tiles(body.image, s.image_tile_grid), video_meta, body.top_n, "clip")
    else:
        clip_shots = _corpus_shots(_embed_image(body.image), video_meta, body.top_n, "clip")

    # DINOv2 instance candidates (best-effort; empty until the fine re-index).
    # The query's DINOv2 vector feeds both the whole-frame channel and the
    # region/object channel (computed once).
    dino_shots: list[dict] = []
    region_shots: list[dict] = []
    if s.dino_enabled:
        try:
            qvec_dino = _embed_image_dino(body.image)
            dino_shots = _corpus_shots_dino(qvec_dino, video_meta, body.top_n)
            # Region/object stream: matches the query against detected object regions
            # (background-invariant) — the fix for clean-logo / single-object queries
            # the whole-frame channels miss. Empty until a region re-index populates
            # jockey_regions; off by default (region_search_enabled).
            if s.region_search_enabled:
                region_shots = _corpus_shots_region(qvec_dino, video_meta, body.top_n)
        except Exception:  # noqa: BLE001
            dino_shots = []
            region_shots = []

    # OCR text of the query frame (best-effort instance signal for title cards).
    query_ocr = _query_ocr_text(body.image)

    # OCR retrieval stream — scrolls indexed ocr_text so a title-card video that
    # CLIP/DINOv2 never surface (visually confusable with a same-category video)
    # still enters the pool via its on-screen text. Requires no re-index.
    ocr_shots, strong_ocr_keys = _corpus_shots_ocr(query_ocr, video_meta, body.top_n)

    from main.search.image_pipeline import fuse_image_candidates, pin_strong_ocr
    fused = fuse_image_candidates(
        clip_shots, dino_shots, query_ocr, ocr_shots=ocr_shots,
        region_shots=region_shots, k=s.image_search_rrf_k)

    # Stage-2 re-rank / prune. Gated LightGlue (geometric instance match against
    # cached keyframe thumbnails) takes precedence when enabled — it's decisive for
    # logos/products where the VLM verifier is unreliable; otherwise the VLM path runs.
    shots = fused
    if s.lightglue_verify_enabled and fused:
        from main.search.lightglue_verify import verify_shots_lightglue
        shots = verify_shots_lightglue(
            _rgb_from_data_url(body.image), fused,
            lambda vid, idx: _thumb_bytes(s, vid, idx),
            min_inliers=s.lightglue_verify_min_inliers,
            top_k=s.lightglue_verify_top_k,
        )
    elif body.verify and fused:
        shots = _verify_shots(body.image, fused)

    # Pin the single strongest OCR title-text match ahead of the VLM verdict. The
    # 8B verifier is unreliable at same-domain identity and was dropping the exact
    # title-card match; on-screen text is a near-certain identity signal so it wins.
    shots = pin_strong_ocr(shots, fused, strong_ocr_keys[:1])

    # group_by + top_n (applied after fusion+verify so the right video surfaces).
    if body.group_by == "video":
        seen_v, grouped = set(), []
        for sh in shots:
            if sh["video_id"] in seen_v:
                continue
            seen_v.add(sh["video_id"])
            grouped.append(sh)
        shots = grouped
    shots = shots[:body.top_n]
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
    from main.search.shot_merge import merge_contiguous_shots
    must = [qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]
    if s.shot_search_exclude_tiles:
        # Rank only whole-frame points; skip the image-tiling crop points that
        # otherwise duplicate a shot 5× and carry no asr_text.
        must.append(qm.IsEmptyCondition(is_empty=qm.PayloadField(key="crop")))
    hits = _qdrant().search(
        collection_name=s.qdrant_collection,
        query_vector=to_vector_list(qvec),
        query_filter=qm.Filter(must=must),
        limit=10,
    )
    shots = [
        {
            "idx": h.payload["shot_idx"],
            "t_start": h.payload["t_start"],
            "t_end": h.payload["t_end"],
            "asr_text": h.payload.get("asr_text", ""),
            "score": float(h.score),
        }
        for h in hits
    ]
    shots = merge_contiguous_shots(shots, s.shot_search_merge_gap_s)
    return success_response({
        "video_id": str(video_id),
        "query": body.query,
        "shots": shots,
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
