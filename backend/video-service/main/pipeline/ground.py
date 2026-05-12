"""Online grounding inference — loads trained GroundingHead at process startup."""
import io
import logging
import os
from functools import lru_cache
from typing import Any

import numpy as np

from main.settings import get_settings
from main.storage.minio import s3

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model():
    """Load grounding head + config from `grounding_checkpoint` once per process."""
    import torch
    from jockey.open_source.training.grounding_head import GroundingConfig, GroundingHead

    s = get_settings()
    cfg = GroundingConfig(
        hidden_dim=s.grounding_hidden_dim,
        num_layers=s.grounding_num_layers,
        num_heads=s.grounding_num_heads,
    )
    model = GroundingHead(cfg)
    if os.path.exists(s.grounding_checkpoint):
        state = torch.load(s.grounding_checkpoint, map_location=s.grounding_device)
        model.load_state_dict(state.get("model", state))
        log.info("grounding:loaded checkpoint=%s", s.grounding_checkpoint)
    else:
        log.warning("grounding:no checkpoint at %s — using untrained weights (dev only)", s.grounding_checkpoint)
    model.eval().to(s.grounding_device)
    return model, cfg


@lru_cache(maxsize=64)
def _features_for(video_id: str) -> dict[str, np.ndarray]:
    """Pull the .npz feature cache for a video from MinIO."""
    s = get_settings()
    buf = io.BytesIO()
    s3().download_fileobj(s.minio_bucket_videos, f"features/{video_id}.npz", buf)
    buf.seek(0)
    arr = np.load(buf)
    return {k: arr[k] for k in arr.files}


def _embed_query(text: str) -> np.ndarray:
    """Embed the query in the same space the head was trained for (CLIP-text by default)."""
    try:
        from jockey.open_source.training.precompute_queries import embed_query_clip_text  # type: ignore
        return embed_query_clip_text(text)
    except Exception as exc:
        log.warning("ground:query embed failed: %s — using zeros (dev fallback)", exc)
        return np.zeros(_load_model()[1].query_dim, dtype=np.float32)


def run_grounding(video_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
    import torch
    model, cfg = _load_model()
    feats = _features_for(video_id)

    visual = torch.tensor(feats["visual"], dtype=torch.float32).unsqueeze(0)
    audio = torch.tensor(feats["audio"], dtype=torch.float32).unsqueeze(0)
    caption = torch.tensor(feats["caption"], dtype=torch.float32).unsqueeze(0)
    shot_boundaries = feats["shot_boundaries"]  # [N, 2]

    q = torch.tensor(_embed_query(query), dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        rel_logits, boundary = model(visual=visual, query=q, audio=audio, caption=caption)
        rel = torch.sigmoid(rel_logits)[0].cpu().numpy()
        b = boundary[0].cpu().numpy()

    duration = float(shot_boundaries[-1, 1]) if len(shot_boundaries) else 0.0
    span_lo = float(min(b)) * duration
    span_hi = float(max(b)) * duration

    order = np.argsort(-rel)
    top = order[:top_k]
    shots = [
        {
            "idx": int(i),
            "t_start": float(shot_boundaries[i, 0]),
            "t_end": float(shot_boundaries[i, 1]),
            "relevance": float(rel[i]),
        }
        for i in top
    ]
    spans = [{"t_start": span_lo, "t_end": span_hi, "score": float(rel.max())}]
    return {"video_id": video_id, "query": query, "shots": shots, "spans": spans}
