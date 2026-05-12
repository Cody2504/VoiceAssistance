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
from uuid import UUID

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


def run_indexing(video_id: UUID, minio_key: str) -> dict[str, Any]:
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
    from jockey.open_source.indexer import detect_shots, _get_video_duration  # type: ignore
    shots = detect_shots(local_video)
    duration = _get_video_duration(local_video)
    log.info("ingest:shots count=%d duration=%.1fs", len(shots), duration)

    # --- 3. Per-shot visual embeddings (ViCLIP) ---
    try:
        from jockey.open_source.viclip_embedder import ViCLIPEmbedder
        visual_embedder = ViCLIPEmbedder()
        visual_feats = np.stack([visual_embedder.embed_clip(local_video, s_, e_) for s_, e_ in shots])
    except Exception as exc:
        log.warning("ingest:viclip failed: %s — falling back to zeros", exc)
        visual_feats = np.zeros((len(shots), 768), dtype=np.float32)

    # --- 4. Per-shot audio embeddings (wav2vec2) ---
    try:
        from jockey.open_source.audio_encoder import AudioEncoder
        audio_encoder = AudioEncoder()
        audio_feats = np.stack([audio_encoder.embed_segment(local_video, s_, e_) for s_, e_ in shots])
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

    # --- 6. Caption embeddings (text-embedding-3-large via OpenRouter/OpenAI) ---
    try:
        from jockey.open_source.metadata_encoder import MetadataEncoder
        meta = MetadataEncoder()
        caption_feats = np.stack([meta.embed_text(t or " ") for t in asr_texts])
    except Exception as exc:
        log.warning("ingest:caption failed: %s — falling back to zeros", exc)
        caption_feats = np.zeros((len(shots), 3072), dtype=np.float32)

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
                id=f"{video_id}:{idx}",
                vector=visual_feats[idx].tolist(),
                payload={
                    "video_id": str(video_id),
                    "shot_idx": idx,
                    "t_start": float(s_),
                    "t_end": float(e_),
                    "asr_text": asr_texts[idx],
                },
            )
            for idx, (s_, e_) in enumerate(shots)
        ]
        client.upsert(collection_name=s.qdrant_collection, points=points)
    except Exception as exc:
        log.error("ingest:qdrant upsert failed: %s", exc)
        raise

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
