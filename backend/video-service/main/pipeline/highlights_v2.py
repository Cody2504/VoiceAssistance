"""Highlights tile — saliency-ranked moments across the entire video.

Run Lighthouse's CG-DETR (or QD-DETR-CLAP for audio-only) on overlapping
150-second windows that tile the full video; per-clip saliency scores are
max-pooled across overlapping windows so the regions covered twice get the
benefit of both contexts. Non-maximum suppression on overlapping high-saliency
moments yields a final ranked list.

The query is a fixed generic prompt ("an interesting key moment or highlight")
so the saliency head — trained on QVHighlights — surfaces what humans tend to
mark as a highlight, not what matches any specific user query.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import numpy as np

from main.settings import get_settings
from main.storage.minio import s3

log = logging.getLogger(__name__)


@dataclass
class HighlightsResult:
    video_id: str
    duration_s: float
    moments: list[dict]
    modality_used: str
    query_used: str


def run_highlights_v2(
    video_id: str,
    duration_s: float,
    modality: str | None = None,
    top_k: int = 10,
    query: str | None = None,
) -> HighlightsResult:
    s = get_settings()
    use_audio = (modality == "audio_only")
    q = query or s.lighthouse_highlight_query

    # InternVideo2 + trained SG-DETR saliency for VISUAL highlights. Audio-only
    # uploads stay on the CLAP/QD-DETR path below (IV2 is visual-only).
    if s.grounding_backend == "iv2" and not use_audio:
        return _highlights_iv2(video_id, duration_s, q, top_k, s)

    from main.services.lighthouse_service import get_lighthouse
    lh = get_lighthouse()

    if use_audio:
        feature_key = f"features/{video_id}/lighthouse/clap.npy"
        predict = lambda f, off: _saliency_audio(lh, q, f, off)
    else:
        feature_key = f"features/{video_id}/lighthouse/clip_slowfast.npy"
        predict = lambda f, off: lh.predict_saliency(f, q, off)

    features = _load_npy(s.minio_bucket_videos, feature_key)
    if features.size == 0:
        log.warning("highlights_v2:no cached features for video=%s", video_id)
        return HighlightsResult(video_id, duration_s, [], "audio" if use_audio else "visual", q)

    n_clips = features.shape[0]
    clip_len = s.lighthouse_clip_length_sec

    # Per-clip saliency, max-pooled across overlapping windows.
    saliency = np.full(n_clips, -np.inf, dtype=np.float32)
    for i_lo, i_hi, offset in lh.iter_windows(n_clips, overlap_ratio=s.lighthouse_window_overlap_ratio):
        slice_ = features[i_lo:i_hi]
        if slice_.shape[0] == 0:
            continue
        per_clip = predict(slice_, offset)
        for clip_idx, (_, _, score) in enumerate(per_clip):
            global_idx = i_lo + clip_idx
            if global_idx < n_clips and score > saliency[global_idx]:
                saliency[global_idx] = score

    moments = _peaks_to_moments(saliency, clip_len, top_k=top_k)
    return HighlightsResult(
        video_id=video_id,
        duration_s=duration_s,
        moments=moments,
        modality_used="audio" if use_audio else "visual",
        query_used=q,
    )


def _highlights_iv2(video_id: str, duration_s: float, q: str, top_k: int, s) -> HighlightsResult:
    """Visual highlights via the IV2 + SG-DETR head. The service handles ≤76-clip
    windowing internally and returns per-clip saliency for the whole video."""
    from main.services.iv2_grounding_service import get_iv2_grounding
    feats = _load_npy(s.minio_bucket_videos, f"features/{video_id}/iv2/visual.npy")
    if feats.size == 0:
        log.warning("highlights_v2:no cached IV2 features for video=%s", video_id)
        return HighlightsResult(video_id, duration_s, [], "visual", q)
    per_clip = get_iv2_grounding().predict_saliency(feats, query=q)
    saliency = np.asarray([score for _, _, score in per_clip], dtype=np.float32)
    moments = _peaks_to_moments(saliency, s.iv2_clip_length_sec, top_k=top_k)
    return HighlightsResult(video_id, duration_s, moments, "visual", q)


def _saliency_audio(lh, query: str, slice_: np.ndarray, offset: float):
    """QD-DETR-CLAP doesn't return per-clip saliency; we run a moment query
    with the generic highlight prompt and broadcast the top-window score to
    every clip inside it. Lower precision than the visual path but works as
    a Highlights surface for audio-only uploads."""
    moments = lh.predict_audio_moments(query, slice_, offset, top_n=3)
    out: list[tuple[float, float, float]] = []
    clip_len = get_settings().lighthouse_clip_length_sec
    for c_idx in range(slice_.shape[0]):
        clip_start = offset + c_idx * clip_len
        clip_end = clip_start + clip_len
        best = 0.0
        for t0, t1, score in moments:
            if t0 < clip_end and t1 > clip_start:
                best = max(best, score)
        out.append((clip_start, clip_end, best))
    return out


def _peaks_to_moments(saliency: np.ndarray, clip_len: float, top_k: int) -> list[dict]:
    """Greedy non-max suppression on per-clip saliency.

    The QD-DETR saliency signal is noisy clip-to-clip; we smooth with a 3-clip
    moving average (≈6 seconds) before picking peaks, then expand each peak
    into the contiguous run of above-mean-saliency clips around it."""
    if saliency.size == 0:
        return []
    s = saliency.copy()
    s[np.isinf(s)] = 0.0
    if s.size >= 3:
        kernel = np.ones(3, dtype=np.float32) / 3.0
        smoothed = np.convolve(s, kernel, mode="same")
    else:
        smoothed = s

    mean = float(smoothed.mean())
    moments: list[dict] = []
    used = np.zeros_like(smoothed, dtype=bool)
    order = np.argsort(-smoothed)
    for idx in order:
        if used[idx] or smoothed[idx] < mean:
            continue
        lo = idx
        while lo > 0 and smoothed[lo - 1] >= mean and not used[lo - 1]:
            lo -= 1
        hi = idx
        while hi + 1 < len(smoothed) and smoothed[hi + 1] >= mean and not used[hi + 1]:
            hi += 1
        used[lo:hi + 1] = True
        moments.append({
            "t_start": float(lo * clip_len),
            "t_end": float((hi + 1) * clip_len),
            "score": float(smoothed[lo:hi + 1].max()),
        })
        if len(moments) >= top_k:
            break
    moments.sort(key=lambda m: -m["score"])
    return moments


def _load_npy(bucket: str, key: str) -> np.ndarray:
    buf = io.BytesIO()
    try:
        s3().download_fileobj(bucket, key, buf)
    except Exception as exc:
        log.warning("highlights_v2:feature cache miss bucket=%s key=%s: %s", bucket, key, exc)
        return np.zeros((0, 0), dtype=np.float32)
    buf.seek(0)
    return np.load(buf)
