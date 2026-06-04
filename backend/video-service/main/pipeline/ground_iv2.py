"""Ground tile — InternVideo2 cosine grounding (EXPERIMENTAL, behind a flag).

Parallel to ``ground_v2`` but simpler: InternVideo2 puts clips and queries in one
512-d space, and cosine has no 150-second head cap, so we skip the dense-retrieval
+ window-merge dance and just score every clip against the query in one pass.

Reads cached IV2 features at ``features/{video_id}/iv2/visual.npy`` (produced at
ingest by the IV2 path, or by the offline extractor). Returns the same shape as
``ground_v2.GroundResult`` so the API/agent can consume either backend.

Selected when ``settings.grounding_backend == "iv2"``. The live CG-DETR path
(``ground_v2``) is untouched.
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


def run_grounding_iv2(
    video_id: str,
    query: str,
    modality: str | None = None,
    top_n: int | None = None,
) -> GroundResult:
    s = get_settings()
    top_n = top_n or s.ground_top_n_moments

    features = _load_npy(s.minio_bucket_videos, f"features/{video_id}/iv2/visual.npy")
    if features.shape[0] == 0:
        log.warning("ground_iv2:no cached IV2 features for video=%s", video_id)
        return GroundResult(video_id, query, [], "visual", 0)

    from main.services.iv2_grounding_service import get_iv2_grounding
    svc = get_iv2_grounding()
    moments_raw = svc.predict_moments(query, features, time_offset=0.0, top_n=top_n)
    log.info("ground_iv2:video=%s clips=%d moments=%d", video_id, features.shape[0], len(moments_raw))

    moments = [
        {"t_start": float(t0), "t_end": float(t1), "score": float(sc)}
        for t0, t1, sc in moments_raw
    ]
    return GroundResult(
        video_id=video_id,
        query=query,
        moments=moments,
        modality_used="visual",
        candidate_windows=0,
    )


def _load_npy(bucket: str, key: str) -> np.ndarray:
    buf = io.BytesIO()
    try:
        s3().download_fileobj(bucket, key, buf)
    except Exception as exc:
        log.warning("ground_iv2:feature cache miss bucket=%s key=%s: %s", bucket, key, exc)
        return np.zeros((0, 0), dtype=np.float32)
    buf.seek(0)
    return np.load(buf)
