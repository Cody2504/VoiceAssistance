"""QD-DETR grounding backend — wraps the official Moon et al. QDDETRPredictor.

Loads the CLIP-only pretrained checkpoint from third_party/qd_detr/ (mounted
into the container at /third_party/qd_detr) and runs end-to-end inference:

    video.mp4 → CLIP-B image features per 2-sec clip → QDDETR → (start, end)

Differences from the legacy GroundingHead path:
  * Features are extracted INLINE from the video file (no MinIO .npz cache).
  * Uses CLIP-B/32 (514-d = CLIP 512 + TEF 2), not ViCLIP-768.
  * Max input length is 75 clips × 2 sec = 150 sec — videos longer than that
    will be truncated by the official predictor's internal slicing.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from functools import lru_cache
from typing import Any

from main.settings import get_settings
from main.storage.minio import s3

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _predictor():
    """Lazy-load the official QDDETRPredictor exactly once per process."""
    # third_party/qd_detr is mounted at /third_party/qd_detr in container
    sys.path.insert(0, "/third_party/qd_detr")
    from run_on_video.run import QDDETRPredictor

    s = get_settings()
    log.info("ground_qddetr:loading ckpt=%s clip=%s device=%s",
             s.qddetr_checkpoint, s.qddetr_clip_model, s.grounding_device)
    if not os.path.isfile(s.qddetr_checkpoint):
        raise FileNotFoundError(
            f"QDDETR checkpoint not found at {s.qddetr_checkpoint}. "
            f"Ensure third_party/qd_detr is mounted into the container."
        )
    p = QDDETRPredictor(
        ckpt_path=s.qddetr_checkpoint,
        clip_model_name_or_path=s.qddetr_clip_model,
        device=s.grounding_device,
    )
    log.info("ground_qddetr:predictor ready")
    return p


def _download_video(minio_key: str) -> str:
    """Pull the source video from MinIO to a temp file. Caller deletes."""
    s = get_settings()
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    with open(path, "wb") as fh:
        s3().download_fileobj(s.minio_bucket_videos, minio_key, fh)
    return path


def run_grounding_qddetr(video_id: str, minio_key: str, query: str, top_k: int = 5) -> dict[str, Any]:
    """Run QD-DETR grounding inline on the source video. Returns the same
    response shape as the legacy backend so the frontend doesn't need to change."""
    predictor = _predictor()
    local_path = _download_video(minio_key)
    try:
        preds = predictor.localize_moment(video_path=local_path, query_list=[query])
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass

    if not preds:
        return {"video_id": video_id, "query": query, "shots": [], "spans": []}
    pred = preds[0]

    # pred_relevant_windows: List[[start, end, score]] sorted by score desc, top 10
    windows = pred.get("pred_relevant_windows", [])[:top_k]
    spans = [
        {"t_start": float(w[0]), "t_end": float(w[1]), "score": float(w[2])}
        for w in windows
    ]

    # pred_saliency_scores: List[float] per 2-sec clip — use to surface ranked shots
    saliency = pred.get("pred_saliency_scores", [])
    clip_len = 2.0  # QDDETRPredictor.clip_len; matches its internal config
    indexed = [(i, float(s_)) for i, s_ in enumerate(saliency)]
    indexed.sort(key=lambda x: -x[1])
    shots = [
        {
            "idx": int(i),
            "t_start": float(i * clip_len),
            "t_end": float((i + 1) * clip_len),
            "relevance": float(s_),
        }
        for i, s_ in indexed[:top_k]
    ]

    return {"video_id": video_id, "query": query, "shots": shots, "spans": spans}
