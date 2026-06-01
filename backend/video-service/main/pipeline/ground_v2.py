"""Ground tile — coarse-then-fine moment retrieval.

Lighthouse's CG-DETR head caps at 150 seconds of feature context per inference.
For 1–2 hour videos we cannot just feed everything in; instead:

  1. Dense retrieval finds the top-K candidate segments (caption+transcript
     similarity, same `jockey_segments_text` collection used by Analyze).
  2. Adjacent candidates are greedily merged into ≤150-second windows with
     ±15-second padding so the DETR head has enough surrounding context.
  3. For each window: slice the cached `clip_slowfast.npy` feature tensor,
     call `LighthouseService.predict_moments(query, slice, time_offset)`.
  4. Results from all windows are merged, deduped by 1-D IoU, and returned
     sorted by score.

For audio-only videos the same flow uses the cached `clap.npy` tensor and
QD-DETR. Visual-with-audio videos default to the visual path; the response
shape includes `modality_used` so the frontend can render accordingly.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from main.settings import get_settings
from main.storage.minio import s3

log = logging.getLogger(__name__)


@dataclass
class GroundResult:
    video_id: str
    query: str
    moments: list[dict[str, Any]]
    modality_used: str
    candidate_windows: int


def run_grounding_v2(
    video_id: str,
    query: str,
    modality: str | None = None,
    top_n: int | None = None,
) -> GroundResult:
    s = get_settings()
    top_n = top_n or s.ground_top_n_moments

    use_audio_path = (modality == "audio_only")
    candidates = _dense_candidates(video_id, query, s.ground_top_k_candidates)
    windows = _greedy_merge(candidates, s.ground_window_pad_sec, s.lighthouse_max_window_sec)
    log.info(
        "ground_v2:video=%s candidates=%d windows=%d modality_path=%s",
        video_id, len(candidates), len(windows), "audio" if use_audio_path else "visual",
    )

    feature_key, predict_fn = _select_backend(video_id, use_audio_path)
    if feature_key is None:
        log.warning("ground_v2:no cached features for video=%s", video_id)
        return GroundResult(video_id, query, [], "audio" if use_audio_path else "visual", 0)

    features = _load_npy(s.minio_bucket_videos, feature_key)
    moments_all: list[tuple[float, float, float]] = []

    if windows:
        for w in windows:
            clip_start = int(w["t_start"] / s.lighthouse_clip_length_sec)
            clip_end = int(np.ceil(w["t_end"] / s.lighthouse_clip_length_sec))
            slice_ = features[clip_start:clip_end]
            if slice_.shape[0] == 0:
                continue
            offset = clip_start * s.lighthouse_clip_length_sec
            moments_all.extend(predict_fn(query, slice_, offset))
    else:
        # No candidates from dense retrieval — fall back to scanning the full
        # video in sliding windows. Slower but ensures recall when retrieval
        # itself fails (e.g. very short transcripts, no captions).
        from main.services.lighthouse_service import get_lighthouse
        lh = get_lighthouse()
        for i_lo, i_hi, offset in lh.iter_windows(features.shape[0], overlap_ratio=0.25):
            moments_all.extend(predict_fn(query, features[i_lo:i_hi], offset))

    moments_all.sort(key=lambda m: -m[2])
    deduped = _iou_dedupe(moments_all, threshold=s.ground_iou_dedup_threshold)
    moments = [
        {"t_start": float(t0), "t_end": float(t1), "score": float(sc)}
        for t0, t1, sc in deduped[:top_n]
    ]
    return GroundResult(
        video_id=video_id,
        query=query,
        moments=moments,
        modality_used="audio" if use_audio_path else "visual",
        candidate_windows=len(windows),
    )


# ---------------------------------------------------------------------------
# Coarse retrieval
# ---------------------------------------------------------------------------


def _dense_candidates(video_id: str, query: str, k: int) -> list[dict]:
    """Top-K segment payloads ordered by text similarity to the query."""
    s = get_settings()
    try:
        from main.encoders.search import TextEmbedder
        from main.encoders.config import config
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm

        embedder = TextEmbedder(
            api_key=config.openrouter_api_key,
            model=config.text_embedding_model,
            base_url=config.openrouter_base_url,
        )
        client = QdrantClient(host=s.qdrant_host, port=s.qdrant_port, timeout=60)
        q_vec = embedder.encode(query)
        hits = client.search(
            collection_name="jockey_segments_text",
            query_vector=q_vec.tolist() if hasattr(q_vec, "tolist") else list(q_vec),
            query_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=video_id)),
            ]),
            limit=k,
            with_payload=True,
        )
        return [h.payload for h in hits if h.payload]
    except Exception as exc:
        log.warning("ground_v2:dense retrieval failed: %s — falling back to full-video scan", exc)
        return []


def _greedy_merge(candidates: list[dict], pad_sec: float, max_window_sec: float) -> list[dict]:
    """Cluster adjacent candidates into ≤max_window_sec windows."""
    if not candidates:
        return []
    intervals = sorted(
        [(float(c["t_start"]) - pad_sec, float(c["t_end"]) + pad_sec) for c in candidates],
        key=lambda x: x[0],
    )
    intervals = [(max(0.0, lo), hi) for lo, hi in intervals]
    merged: list[list[float]] = [list(intervals[0])]
    for lo, hi in intervals[1:]:
        last = merged[-1]
        if lo <= last[1]:
            last[1] = max(last[1], hi)
        else:
            merged.append([lo, hi])
    # Split any merged window that exceeds max_window_sec.
    out: list[dict] = []
    for lo, hi in merged:
        if hi - lo <= max_window_sec:
            out.append({"t_start": lo, "t_end": hi})
            continue
        cur = lo
        while cur < hi:
            seg_hi = min(cur + max_window_sec, hi)
            out.append({"t_start": cur, "t_end": seg_hi})
            cur = seg_hi
    return out


# ---------------------------------------------------------------------------
# Backend selection (visual CG-DETR vs audio QD-DETR)
# ---------------------------------------------------------------------------


def _select_backend(video_id: str, use_audio: bool):
    """Resolve which cached feature file + Lighthouse method to use."""
    from main.services.lighthouse_service import get_lighthouse
    lh = get_lighthouse()
    if use_audio:
        key = f"features/{video_id}/lighthouse/clap.npy"
        predict = lambda q, f, off: lh.predict_audio_moments(q, f, off)
    else:
        key = f"features/{video_id}/lighthouse/clip_slowfast.npy"
        predict = lambda q, f, off: lh.predict_moments(q, f, off)
    return key, predict


def _load_npy(bucket: str, key: str) -> np.ndarray:
    buf = io.BytesIO()
    try:
        s3().download_fileobj(bucket, key, buf)
    except Exception as exc:
        log.warning("ground_v2:feature cache miss bucket=%s key=%s: %s", bucket, key, exc)
        return np.zeros((0, 0), dtype=np.float32)
    buf.seek(0)
    return np.load(buf)


# ---------------------------------------------------------------------------
# IoU dedupe
# ---------------------------------------------------------------------------


def _iou_dedupe(moments: list[tuple[float, float, float]], threshold: float) -> list[tuple[float, float, float]]:
    """Greedy NMS over 1-D spans — input must be sorted by score desc."""
    kept: list[tuple[float, float, float]] = []
    for m in moments:
        if all(_iou(m, k) < threshold for k in kept):
            kept.append(m)
    return kept


def _iou(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0
