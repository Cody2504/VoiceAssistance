"""Factory that dispatches the find_moment tool to the configured grounding backend.

Two backends today:
  - "trace":   `TraceLocalizer` wrapping `Yongxin-Guo/trace-uni` (pretrained,
               ~15 GB, 4-bit quant on T4). Inference-only validation backend.
  - "qd_detr": `MomentLocalizer` wrapping the user's fine-tuned QDDETRHead
               (~3-5M params, ~50ms/query). Requires `config.qd_detr_checkpoint`
               + precomputed features in `config.features_dir`.

Both expose `.localize(query: str, video_path_or_video_id: str) -> MomentPrediction`
so the find_moment tool body is backend-agnostic. Note: TRACE takes a raw
video file path; QDDETRHead takes a video_id that resolves to a .npz feature
file. The stirrup passes a `video_path`; for the qd_detr backend we adapt
the path to a video_id by stripping the directory + extension.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from jockey.open_source.moment_localizer import MomentPrediction

log = logging.getLogger(__name__)


class _GrounderAdapter:
    """Wraps a backend so `localize(query, video_path)` works for both TRACE
    (raw video) and QDDETRHead (precomputed .npz keyed by video_id)."""

    def __init__(self, backend: str, inner: Any):
        self.backend = backend
        self.inner = inner

    def localize(self, query: str, video_path: str) -> MomentPrediction:
        if self.backend == "qd_detr":
            # MomentLocalizer expects video_id, not a full path. Strip dir + ext.
            video_id = os.path.splitext(os.path.basename(video_path))[0]
            return self.inner.localize(query=query, video_id=video_id)
        # TRACE takes the full video path directly.
        return self.inner.localize(query=query, video_path=video_path)


def build_grounder(config) -> _GrounderAdapter:
    """Construct the configured grounding backend.

    Reads `config.grounding_backend` ∈ {"trace", "qd_detr", "off"}. Raises
    `ValueError` for unknown backends and when the chosen backend is missing
    a required setting (e.g. `qd_detr_checkpoint` for QDDETRHead).
    """
    backend = (getattr(config, "grounding_backend", "trace") or "trace").lower()

    if backend == "off":
        raise ValueError(
            "find_moment is disabled (config.grounding_backend == 'off')."
        )

    if backend == "trace":
        from jockey.open_source.trace_localizer import TraceLocalizer
        log.info("Building TraceLocalizer grounder")
        inner = TraceLocalizer(
            model_path=config.trace_model_name,
            device=getattr(config, "viclip_device", "cuda"),
            load_in_4bit=config.trace_load_in_4bit,
            num_frames=config.trace_frames_per_clip,
        )
        return _GrounderAdapter("trace", inner)

    if backend == "qd_detr":
        from jockey.open_source.moment_localizer import MomentLocalizer
        if not config.qd_detr_checkpoint or not os.path.isfile(config.qd_detr_checkpoint):
            raise ValueError(
                f"grounding_backend='qd_detr' requires a valid `qd_detr_checkpoint`. "
                f"Got: {config.qd_detr_checkpoint!r}"
            )
        if not config.features_dir or not os.path.isdir(config.features_dir):
            raise ValueError(
                f"grounding_backend='qd_detr' requires `features_dir` with precomputed "
                f".npz files. Got: {config.features_dir!r}"
            )
        log.info("Building MomentLocalizer (QDDETRHead) grounder")
        inner = MomentLocalizer(
            checkpoint_path=config.qd_detr_checkpoint,
            features_dir=config.features_dir,
            device=getattr(config, "viclip_device", "cuda"),
        )
        return _GrounderAdapter("qd_detr", inner)

    raise ValueError(
        f"Unknown grounding_backend: {backend!r}. Expected 'trace', 'qd_detr', or 'off'."
    )
