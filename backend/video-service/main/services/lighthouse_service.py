"""Lighthouse wrapper — visual + audio moment retrieval and highlight saliency.

Wraps the official `lighthouse` library so the rest of the service can call
`get_lighthouse().predict_moments(query, features, time_offset)` without worrying
about model loading, device placement, or the 150-second per-inference cap.

Two model heads are loaded once per process and kept on the same device:

  visual_mr  : CG-DETR pretrained on QVHighlights, CLIP+SlowFast features
  audio_mr   : QD-DETR pretrained on Clotho-Moment, CLAP features

The full-video CLIP+SlowFast / CLAP feature tensors are precomputed at ingest
time (see pipeline/ingest.py) and cached to MinIO; at query time we slice the
relevant window out and run only the DETR head.
"""
from __future__ import annotations

import logging
import threading
from typing import Sequence

import numpy as np

from main.settings import get_settings

log = logging.getLogger(__name__)

_LOCK = threading.Lock()
_INSTANCE: "LighthouseService | None" = None


def _patch_torch_load_for_legacy_ckpts() -> None:
    """PyTorch 2.6 flipped `torch.load`'s default to `weights_only=True`, which
    refuses to unpickle non-tensor classes for safety. Lighthouse's pretrained
    `.ckpt` files include the training `opt` as `argparse.Namespace`, so
    loading them under the new default raises:

        UnpicklingError: ... argparse.Namespace was not an allowed global by default

    The QD-DETR fork hit the same issue yesterday (migration log 2026-05-23
    problem 20) and was patched in-tree (`weights_only=False`). We can't edit
    `lighthouse` (pip dep), so we monkey-patch `torch.load` to default to
    `weights_only=False` at process start. Safe because the only checkpoints
    loaded in this process are ours (CG-DETR, QD-DETR-CLAP, SlowFast, PANN —
    all downloaded by `scripts/download_lighthouse_weights.sh`).

    Idempotent: subsequent imports of this module won't re-wrap an already-
    wrapped `torch.load`.
    """
    try:
        import torch
    except ImportError:
        return
    if getattr(torch.load, "_voiceassistant_legacy_compat", False):
        return
    import functools
    _orig_load = torch.load

    @functools.wraps(_orig_load)
    def _load_compat(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        result = _orig_load(*args, **kwargs)
        # CG-DETR on QVHighlights was trained visual-only and saved
        # `opt.a_feat_dim = None`. lighthouse.common.cg_detr.build_model
        # falls back to 0 via `args.a_feat_dim if "a_feat_dim" in args else 0`,
        # but that branch only triggers when the key is missing — a present
        # `None` propagates and crashes `LinearLayer(vid_dim + aud_dim, ...)`
        # with "unsupported operand type(s) for +: 'int' and 'NoneType'".
        if isinstance(result, dict) and "opt" in result:
            opt = result["opt"]
            if hasattr(opt, "a_feat_dim") and opt.a_feat_dim is None:
                opt.a_feat_dim = 0
        return result

    _load_compat._voiceassistant_legacy_compat = True  # type: ignore[attr-defined]
    torch.load = _load_compat  # type: ignore[assignment]


_patch_torch_load_for_legacy_ckpts()


def get_lighthouse() -> "LighthouseService":
    """Process-wide singleton. First call loads the heavy models."""
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = LighthouseService()
    return _INSTANCE


class LighthouseService:
    """Thin wrapper around `lighthouse.models.CGDETRPredictor` + `QDDETRPredictor`.

    Methods are split so the caller can pre-compute features once and run the
    DETR head many times on different query/window combinations.
    """

    def __init__(self) -> None:
        # Imports deferred — only the worker / API process pays the cost.
        from lighthouse.models import CGDETRPredictor, QDDETRPredictor

        s = get_settings()
        self.device = s.lighthouse_device
        self.clip_length = s.lighthouse_clip_length_sec
        self.max_window_sec = s.lighthouse_max_window_sec
        log.info(
            "lighthouse:loading visual_ckpt=%s audio_ckpt=%s device=%s feature=%s",
            s.lighthouse_cg_detr_ckpt,
            s.lighthouse_clap_qd_detr_ckpt,
            self.device,
            s.lighthouse_visual_feature_name,
        )

        self.visual = CGDETRPredictor(
            ckpt_path=s.lighthouse_cg_detr_ckpt,
            device=self.device,
            feature_name=s.lighthouse_visual_feature_name,
            slowfast_path=s.lighthouse_slowfast_ckpt,
            pann_path=None,
        )
        self.audio = QDDETRPredictor(
            ckpt_path=s.lighthouse_clap_qd_detr_ckpt,
            device=self.device,
            feature_name=s.lighthouse_audio_feature_name,
            slowfast_path=None,
            pann_path=None,
        )
        log.info("lighthouse:ready")

    # ------------------------------------------------------------------ ingest

    def encode_video_to_features(self, video_path: str) -> np.ndarray:
        """Encode the WHOLE video — no 150-second cap.

        The library's official `encode_video()` raises for n_clips > 75; it
        also bakes in a temporal-position encoding (TEF) normalized to the
        full video length, which would be wrong after we slice the cached
        tensor at query time. We call the underlying vision encoder directly
        to get raw `[n_clips, dim]` features (no TEF, no batch dim, no length
        check) and reconstruct the TEF per query window.
        """
        feats, _ = self.visual._vision_encoder.encode(video_path)
        arr = _to_numpy(feats)
        log.info("lighthouse:encode_video clips=%d dim=%d", arr.shape[0], arr.shape[1])
        return arr

    def encode_audio_to_features(self, audio_path: str) -> np.ndarray:
        """Encode the whole audio file via CLAP; return raw `[n_clips, dim]`."""
        feats, _ = self.audio._audio_encoder.encode(audio_path)
        arr = _to_numpy(feats)
        log.info("lighthouse:encode_audio clips=%d dim=%d", arr.shape[0], arr.shape[1])
        return arr

    # ------------------------------------------------------------------ query

    def predict_moments(
        self,
        query: str,
        features: np.ndarray,
        time_offset: float = 0.0,
        top_n: int = 10,
    ) -> list[tuple[float, float, float]]:
        """Run CG-DETR on a ≤150s slice of pre-cached visual features.

        `features` shape: `[n_clips, dim]`. `time_offset` is added to every
        returned start/end so callers can pass a feature slice from anywhere
        in a long video and still get absolute timestamps back.
        """
        clips = self._enforce_window(features)
        inputs = self._wrap_for_visual_predictor(clips)
        out = self.visual.predict(query, inputs)
        return self._extract_windows(out, time_offset=time_offset, top_n=top_n)

    def predict_audio_moments(
        self,
        query: str,
        audio_features: np.ndarray,
        time_offset: float = 0.0,
        top_n: int = 10,
    ) -> list[tuple[float, float, float]]:
        """QD-DETR audio moment retrieval (CLAP features). Same contract as
        predict_moments but for `.mp3`/`.wav`/audio-only `.mp4` inputs."""
        clips = self._enforce_window(audio_features)
        inputs = self._wrap_for_audio_predictor(clips)
        out = self.audio.predict(query, inputs)
        return self._extract_windows(out, time_offset=time_offset, top_n=top_n)

    def predict_saliency(
        self,
        features: np.ndarray,
        query: str | None = None,
        time_offset: float = 0.0,
    ) -> list[tuple[float, float, float]]:
        """Per-clip saliency scan over a ≤150s window. Returns one
        `(clip_start, clip_end, score)` tuple per clip in the window.

        For the Highlights tile we pass a generic 'interesting moment' query so
        QVHighlights-trained saliency surfaces what humans tend to mark as
        highlights — not what matches any specific user query.
        """
        q = query or get_settings().lighthouse_highlight_query
        clips = self._enforce_window(features)
        inputs = self._wrap_for_visual_predictor(clips)
        out = self.visual.predict(q, inputs)
        saliency = list(out.get("pred_saliency_scores", []))
        return [
            (
                time_offset + i * self.clip_length,
                time_offset + (i + 1) * self.clip_length,
                float(s),
            )
            for i, s in enumerate(saliency)
        ]

    # ---------------------------------------------------------------- helpers

    def _enforce_window(self, features: np.ndarray) -> np.ndarray:
        """Lighthouse's DETR head was trained with at most 75 clips of 2s each.
        Larger slices are silently truncated rather than chunked here so the
        caller is forced to split correctly via `iter_windows()`."""
        max_clips = int(self.max_window_sec / self.clip_length)
        if features.shape[0] > max_clips:
            log.warning(
                "lighthouse:slice truncated %d → %d clips (caller should chunk before this)",
                features.shape[0], max_clips,
            )
            return features[:max_clips]
        return features

    def _wrap_for_visual_predictor(self, features: np.ndarray) -> dict:
        """Reconstruct the same input dict the library's `encode_video` would
        produce: raw `[1, L, D]` features concatenated with a 2-D TEF per
        clip, plus a `video_mask` of ones. TEF is normalized to the WINDOW
        length (0 → 1 across the slice), matching `_normalize_and_concat_with_timestamps`.
        """
        import torch
        feats = torch.from_numpy(features).float().to(self.device)              # [L, D]
        n = feats.shape[0]
        tef_st = torch.arange(0, n, dtype=torch.float32, device=self.device) / max(n, 1)
        tef_ed = tef_st + 1.0 / max(n, 1)
        tef = torch.stack([tef_st, tef_ed], dim=1)                              # [L, 2]
        timestamped = torch.cat([feats, tef], dim=1).unsqueeze(0)               # [1, L, D+2]
        mask = torch.ones((1, n), dtype=torch.float32, device=self.device)
        return {"video_feats": timestamped, "video_mask": mask, "audio_feats": None}

    def _wrap_for_audio_predictor(self, features: np.ndarray) -> dict:
        """QD-DETR/CLAP audio MR expects `video_feats` to carry the TEF alone
        (no visual features) and `audio_feats` to carry the raw CLAP tensor."""
        import torch
        feats = torch.from_numpy(features).float().to(self.device)              # [L, D]
        n = feats.shape[0]
        tef_st = torch.arange(0, n, dtype=torch.float32, device=self.device) / max(n, 1)
        tef_ed = tef_st + 1.0 / max(n, 1)
        tef = torch.stack([tef_st, tef_ed], dim=1).unsqueeze(0)                 # [1, L, 2]
        audio_feats = feats.unsqueeze(0)                                        # [1, L, D]
        mask = torch.ones((1, n), dtype=torch.float32, device=self.device)
        return {"video_feats": tef, "video_mask": mask, "audio_feats": audio_feats}

    @staticmethod
    def _extract_windows(out: dict, time_offset: float, top_n: int) -> list[tuple[float, float, float]]:
        windows = out.get("pred_relevant_windows", []) if out else []
        moments: list[tuple[float, float, float]] = []
        for w in windows[:top_n]:
            start, end, score = float(w[0]), float(w[1]), float(w[2])
            moments.append((start + time_offset, end + time_offset, score))
        return moments

    # ------------------------------------------------- long-video chunking

    def iter_windows(
        self,
        n_clips: int,
        overlap_ratio: float | None = None,
    ) -> list[tuple[int, int, float]]:
        """Yield `(clip_start_idx, clip_end_idx, time_offset_sec)` tuples that
        cover all `n_clips` with ≤75-clip windows and `overlap_ratio` overlap.

        Used by Highlights (full-video saliency scan) and Ground (when a
        coarse-retrieved candidate window spans more than 150s)."""
        if overlap_ratio is None:
            overlap_ratio = get_settings().lighthouse_window_overlap_ratio
        max_clips = int(self.max_window_sec / self.clip_length)
        stride = max(1, int(max_clips * (1.0 - overlap_ratio)))
        out: list[tuple[int, int, float]] = []
        i = 0
        while i < n_clips:
            end = min(i + max_clips, n_clips)
            out.append((i, end, i * self.clip_length))
            if end == n_clips:
                break
            i += stride
        return out


def _to_numpy(x) -> np.ndarray:
    """Tensor / list / ndarray → ndarray on CPU."""
    if isinstance(x, np.ndarray):
        return x
    try:
        import torch
        if isinstance(x, torch.Tensor):
            return x.detach().cpu().numpy()
    except ImportError:
        pass
    return np.asarray(x)


def iou_1d(a: Sequence[float], b: Sequence[float]) -> float:
    """1-D IoU for `(start, end)` spans — used by Ground v2 to dedupe overlap."""
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0
