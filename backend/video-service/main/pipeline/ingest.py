"""Async indexing job — wraps jockey.open_source's indexer + encoders.

Stages: shot detect → frame extract → ViCLIP visual → wav2vec2 audio → Whisper ASR →
text-emb-3-large metadata → Qdrant upsert + thumbnails to MinIO.

Designed to be called from the RQ worker (`workers/queue_worker.py`) with a video_id.
"""
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, NAMESPACE_OID, uuid5

import numpy as np

from main.settings import get_settings
from main.storage.minio import download_to_path, s3

log = logging.getLogger(__name__)

# Heavy imports deferred — only the worker process loads them.


def _save_thumbnail(video_path: str, t_mid: float, dest_path: str) -> bool:
    import subprocess
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t_mid:.2f}", "-i", video_path,
             "-frames:v", "1", "-vf", "scale=160:-1", "-loglevel", "quiet", dest_path],
            check=True, capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def run_indexing(
    video_id: UUID,
    minio_key: str,
    user_id: UUID | None = None,
    original_filename: str = "",
) -> dict[str, Any]:
    """Index a single video end-to-end. Returns summary dict.

    Stages are kept loosely coupled so a missing optional module (e.g. audio_encoder
    without GPU) degrades gracefully — the video still becomes searchable on visual + ASR.
    """
    s = get_settings()
    log.info("ingest:start video_id=%s key=%s", video_id, minio_key)
    start = time.time()

    # --- 1. Download to scratch ---
    scratch = tempfile.mkdtemp(prefix="jockey-ingest-")
    local_video = os.path.join(scratch, "input.mp4")
    download_to_path(s.minio_bucket_videos, minio_key, local_video)

    # --- 2. Shot detection ---
    from jockey.open_source.indexer import detect_shots, _get_video_duration, extract_frames  # type: ignore
    from jockey.open_source.config import config as _jockey_config
    refine_with_speech = getattr(_jockey_config, "sentence_refine_enabled", False)
    shots = detect_shots(local_video, refine_with_speech=refine_with_speech)
    duration = _get_video_duration(local_video)
    log.info(
        "ingest:shots count=%d duration=%.1fs refine=%s",
        len(shots), duration, refine_with_speech,
    )

    # --- 3. Per-shot visual embeddings (CLIP via ViCLIPEmbedder) ---
    try:
        from jockey.open_source.viclip_embedder import ViCLIPEmbedder
        visual_embedder = ViCLIPEmbedder()
        frame_batches = [extract_frames(local_video, s_, e_, max_frames=8) for s_, e_ in shots]
        visual_feats = visual_embedder.encode_video_batch(frame_batches)
    except Exception as exc:
        log.warning("ingest:viclip failed: %s — falling back to zeros", exc)
        visual_feats = np.zeros((len(shots), 768), dtype=np.float32)

    # --- 4. Per-shot audio embeddings (wav2vec2) ---
    try:
        from jockey.open_source.audio_encoder import AudioEncoder
        audio_encoder = AudioEncoder()
        audio_feats = np.stack([
            audio_encoder.encode_audio(local_video, start_sec=s_, end_sec=e_)
            for s_, e_ in shots
        ])
    except Exception as exc:
        log.warning("ingest:audio failed: %s — falling back to zeros", exc)
        audio_feats = np.zeros((len(shots), 768), dtype=np.float32)

    # --- 5. ASR per shot (Whisper) ---
    try:
        from jockey.open_source.asr_whisper import transcribe_segment  # type: ignore
        asr_texts = [transcribe_segment(local_video, s_, e_) for s_, e_ in shots]
    except Exception as exc:
        log.warning("ingest:asr failed: %s — leaving empty", exc)
        asr_texts = ["" for _ in shots]

    # --- 5b. OCR per shot (EasyOCR on middle frame). Closes UC #17 + part of UC #6. ---
    ocr_texts: list[str] = ["" for _ in shots]
    try:
        from jockey.open_source.ocr_encoder import OCREncoder
        ocr_enc = OCREncoder(device="cpu")
        for idx, (s_, e_) in enumerate(shots):
            mid_frames = extract_frames(local_video, (s_ + e_) / 2, (s_ + e_) / 2 + 0.5, max_frames=1)
            if mid_frames is not None and len(mid_frames) > 0:
                ocr_texts[idx] = ocr_enc.extract_from_frame(mid_frames[0])
    except Exception as exc:
        log.warning("ingest:ocr failed: %s — payload ocr_text will be empty", exc)

    # --- 5c. Audio event tags (PANN CNN14) per shot. Closes UC #15. ---
    audio_tags_per_shot: list[list[dict]] = [[] for _ in shots]
    try:
        from jockey.open_source.audio_event_encoder import (
            AudioEventEncoder, _load_full_audio_32k_mono, slice_samples,
        )
        ae = AudioEventEncoder(device="cpu")
        full_audio_32k = _load_full_audio_32k_mono(local_video)
        for idx, (s_, e_) in enumerate(shots):
            seg = slice_samples(full_audio_32k, s_, e_, sr=32000)
            if seg is not None and seg.size > 0:
                audio_tags_per_shot[idx] = ae.tag_audio_segment(seg, top_k=5)
    except Exception as exc:
        log.warning("ingest:audio_events failed: %s — payload audio_tags will be empty", exc)

    # --- 5d. Visual NSFW + textual toxicity classifiers. Closes UC #14. ---
    nsfw_scores: list[float] = [0.0 for _ in shots]
    toxic_scores: list[float] = [0.0 for _ in shots]
    try:
        from jockey.open_source.moderation_encoder import NSFWClassifier
        nsfw = NSFWClassifier(device="cpu")
        for idx, (s_, e_) in enumerate(shots):
            mid_frames = extract_frames(local_video, (s_ + e_) / 2, (s_ + e_) / 2 + 0.5, max_frames=1)
            if mid_frames is not None and len(mid_frames) > 0:
                nsfw_scores[idx] = nsfw.score_frame(mid_frames[0])
    except Exception as exc:
        log.warning("ingest:nsfw failed: %s — payload nsfw_score will be 0", exc)

    # --- 5e. Per-shot VLM captions (Qwen3-VL via OpenRouter) ---
    # Reuses the same VLM endpoint the agent already uses for VQA. Captures
    # what's *visible* in the shot — critical for silent shots (B-roll,
    # animations, lecture slides) where ASR alone yields no semantic signal.
    chunk_captions: list[str] = ["" for _ in shots]
    try:
        from jockey.open_source.captioner import VLMCaptioner
        from jockey.open_source.config import config as _jockey_config
        vlm_cap = VLMCaptioner.from_config(_jockey_config)
        if vlm_cap.is_available():
            log.info("ingest:captioner running over %d shots", len(shots))
            chunk_captions = vlm_cap.caption_batch(frame_batches)
        else:
            log.info("ingest:captioner disabled (CAPTION_ENABLED or API key); skipping")
    except Exception as exc:
        log.warning("ingest:captioner failed: %s — chunk_caption will be empty", exc)

    # --- 6. Caption embeddings (text-embedding-3-large via OpenRouter/OpenAI) ---
    # Text-side input is transcript joined with VLM caption. Either alone is
    # OK; the join is what closes the silent-shot retrieval gap.
    try:
        from jockey.open_source.search import TextEmbedder
        from jockey.open_source.config import config
        if not config.openrouter_api_key:
            raise RuntimeError("no openrouter_api_key configured")
        text_embedder = TextEmbedder(
            api_key=config.openrouter_api_key,
            model=config.text_embedding_model,
            base_url=config.openrouter_base_url,
        )
        def _combine(t: str, c: str) -> str:
            parts = [p for p in (t, c) if p]
            return " | ".join(parts) if parts else " "
        caption_feats = np.stack([
            text_embedder.encode(_combine(asr_texts[i], chunk_captions[i]))
            for i in range(len(shots))
        ])
    except Exception as exc:
        log.warning("ingest:caption failed: %s — falling back to zeros", exc)
        caption_feats = np.zeros((len(shots), 3072), dtype=np.float32)

    # --- 6b. Per-shot toxic-text scores (depends on ASR being done). Closes UC #14 (text side). ---
    try:
        from jockey.open_source.moderation_encoder import ToxicTextClassifier
        toxic = ToxicTextClassifier(device="cpu")
        toxic_scores = [toxic.score_text(t or "") for t in asr_texts]
    except Exception as exc:
        log.warning("ingest:toxic failed: %s — payload toxic_score will be 0", exc)

    # --- 7. Qdrant upsert ---
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm
        client = QdrantClient(host=s.qdrant_host, port=s.qdrant_port)

        existing = {c.name for c in client.get_collections().collections}
        if s.qdrant_collection not in existing:
            client.create_collection(
                s.qdrant_collection,
                vectors_config=qm.VectorParams(size=visual_feats.shape[1], distance=qm.Distance.COSINE),
            )

        points = [
            qm.PointStruct(
                id=str(uuid5(NAMESPACE_OID, f"{video_id}:{idx}")),
                vector=visual_feats[idx].tolist(),
                payload={
                    "video_id": str(video_id),
                    "shot_idx": idx,
                    "t_start": float(s_),
                    "t_end": float(e_),
                    "asr_text": asr_texts[idx],
                    "ocr_text": ocr_texts[idx],
                    "chunk_caption": chunk_captions[idx],
                    "audio_tags": audio_tags_per_shot[idx],  # list of {label, score}
                    "nsfw_score": float(nsfw_scores[idx]),
                    "toxic_score": float(toxic_scores[idx]),
                },
            )
            for idx, (s_, e_) in enumerate(shots)
        ]
        client.upsert(collection_name=s.qdrant_collection, points=points)
    except Exception as exc:
        log.error("ingest:qdrant upsert failed: %s", exc)
        raise

    # --- 7b. Per-video metadata embedding (mean-pooled captions) for recommendations ---
    # Closes UC #11 — recommendations endpoint reads this collection by cosine.
    try:
        metadata_vec = caption_feats.mean(axis=0).astype(np.float32)
        meta_collection = "jockey_videos"
        if meta_collection not in {c.name for c in client.get_collections().collections}:
            client.create_collection(
                meta_collection,
                vectors_config=qm.VectorParams(size=int(metadata_vec.shape[0]), distance=qm.Distance.COSINE),
            )
        client.upsert(
            collection_name=meta_collection,
            points=[
                qm.PointStruct(
                    id=str(uuid5(NAMESPACE_OID, f"video:{video_id}")),
                    vector=metadata_vec.tolist(),
                    payload={
                        "video_id": str(video_id),
                        "user_id": str(user_id) if user_id else None,
                        "original_filename": original_filename or "",
                    },
                )
            ],
        )
        log.info("ingest:metadata_emb upserted to %s", meta_collection)
    except Exception as exc:
        log.warning("ingest:metadata_emb failed: %s — recommendations endpoint will skip this video", exc)

    # --- 8. Thumbnails to MinIO ---
    for idx, (s_, e_) in enumerate(shots):
        thumb_path = os.path.join(scratch, f"shot_{idx}.jpg")
        if _save_thumbnail(local_video, (s_ + e_) / 2, thumb_path):
            with open(thumb_path, "rb") as f:
                s3().upload_fileobj(f, s.minio_bucket_thumbs, f"{video_id}/{idx}.jpg",
                                    ExtraArgs={"ContentType": "image/jpeg"})

    # --- 9. Persist per-shot feature cache for grounding /ground endpoint ---
    npz_path = os.path.join(scratch, "features.npz")
    np.savez_compressed(
        npz_path,
        visual=visual_feats,
        audio=audio_feats,
        caption=caption_feats,
        shot_boundaries=np.array(shots, dtype=np.float32),
    )
    with open(npz_path, "rb") as f:
        s3().upload_fileobj(f, s.minio_bucket_videos, f"features/{video_id}.npz",
                            ExtraArgs={"ContentType": "application/octet-stream"})

    elapsed = time.time() - start
    log.info("ingest:done video_id=%s shots=%d elapsed=%.1fs", video_id, len(shots), elapsed)
    return {
        "video_id": str(video_id),
        "duration_s": duration,
        "shot_count": len(shots),
        "elapsed_s": elapsed,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
