"""InternVideo2 grounding service — EXPERIMENTAL, behind a flag.

A parallel to ``lighthouse_service.LighthouseService`` that grounds queries with
the InternVideo2-1B towers (SG-DETR's released TorchScript encoders) instead of
CLIP+SlowFast + the CG-DETR head. It mirrors the same method names so callers
(see ``pipeline/ground_iv2.py``) can swap backends behind ``grounding_backend``.

WHAT IT DOES (zero-shot, NO trained head yet):
  Video clips and text queries land in the SAME L2-normalized 512-d space
  (validated on a 3090: video [n_clips,512], query out[0]=[1,512]). So we
  ground by cosine similarity: saliency(t) = <clip_t, query>, then group
  contiguous high-saliency clips into moments. This is a CLIP-similarity-style
  baseline. When the R2/CG-DETR-on-InternVideo2 head is trained, it drops in
  behind ``predict_moments`` at this same seam.

ISOLATION: additive. Imports nothing from the live CG-DETR path; the encoders
are self-contained (mirror jockey/open_source/training iv2_feature_extractor,
which is the validated reference). torch + the TorchScript .pt files + a BERT
tokenizer are the only heavy deps, all imported lazily.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Sequence

import numpy as np

log = logging.getLogger(__name__)

# Matches the validated SG-DETR / InterVidV2-1b setup.
CLIP_LENGTH_SEC = 2.0
FRAMES_PER_CLIP = 4
INPUT_SIZE = 224
FEATURE_DIM = 512                       # CLIP-aligned InternVideo2 width, L2-normed
TEXT_MAX_LEN = 40                       # bert-large-uncased, per SG-DETR
# VideoTransforms + VideoInference renorm constants (verbatim from sg-detr FE).
_VT_MEAN, _VT_STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
_IMEAN, _ISTD = 0.45, 0.225
_VMEAN, _VSTD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)

_LOCK = threading.Lock()
_INSTANCE: "IV2GroundingService | None" = None


def get_iv2_grounding() -> "IV2GroundingService":
    """Process-wide singleton wired to settings (real service path)."""
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                from main.settings import get_settings
                s = get_settings()
                _INSTANCE = IV2GroundingService(
                    video_ckpt=s.iv2_video_ckpt,
                    text_ckpt=s.iv2_text_ckpt,
                    device=s.iv2_device,
                    clip_length_sec=s.iv2_clip_length_sec,
                )
    return _INSTANCE


class IV2GroundingService:
    """InternVideo2 video+text encoders + cosine grounding.

    Constructor takes explicit ckpt paths (env fallback) so it is testable
    without the full settings / DB / MinIO stack.
    """

    def __init__(
        self,
        video_ckpt: str | None = None,
        text_ckpt: str | None = None,
        device: str = "cuda",
        clip_length_sec: float = CLIP_LENGTH_SEC,
    ) -> None:
        import torch
        self._torch = torch
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.clip_length = clip_length_sec

        video_ckpt = video_ckpt or os.environ.get("IV2_SGDETR_VIDEO_CKPT", "")
        text_ckpt = text_ckpt or os.environ.get("IV2_SGDETR_TEXT_CKPT", "")
        if not os.path.isfile(video_ckpt):
            raise RuntimeError(f"IV2 video_encoder not found: {video_ckpt!r}")
        if not os.path.isfile(text_ckpt):
            raise RuntimeError(f"IV2 text_encoder not found: {text_ckpt!r}")

        log.info("iv2:loading video=%s text=%s device=%s", video_ckpt, text_ckpt, self.device)
        self._vmodel = torch.jit.load(video_ckpt, map_location=self.device).to(self.device).eval()
        self._tmodel = torch.jit.load(text_ckpt, map_location=self.device).to(self.device).eval()
        from transformers import BertTokenizer
        self._tok = BertTokenizer.from_pretrained("bert-large-uncased")
        self._vt_m = torch.tensor(_VT_MEAN).view(1, -1, 1, 1)
        self._vt_s = torch.tensor(_VT_STD).view(1, -1, 1, 1)
        log.info("iv2:ready")

    # ------------------------------------------------------------------ ingest
    def encode_video_to_features(self, video_path: str) -> np.ndarray:
        """Whole video -> [n_clips, 512] L2-normalized features."""
        from jockey.open_source.training.iv2_feature_extractor import read_clips
        clips, _ = read_clips(video_path, self.clip_length, FRAMES_PER_CLIP, INPUT_SIZE)
        return np.stack([self._encode_clip(clips[i]) for i in range(clips.shape[0])], axis=0)

    def _encode_clip(self, frames: np.ndarray) -> np.ndarray:
        torch = self._torch
        with torch.no_grad():
            x = torch.from_numpy(frames).permute(0, 3, 1, 2).contiguous().float()
            x = x.div(255.0).sub(self._vt_m).div(self._vt_s)
            x = x.permute(1, 0, 2, 3).unsqueeze(0)             # [1,C,T,H,W]
            t = x.size(2); step = max(1, t // FRAMES_PER_CLIP)
            idx = torch.arange(0, t, step)[:FRAMES_PER_CLIP]
            x = torch.index_select(x, 2, idx.to(x.device))
            x = x.mul(_ISTD).add(_IMEAN)
            vm = torch.tensor(_VMEAN).view(1, -1, 1, 1, 1)
            vs = torch.tensor(_VSTD).view(1, -1, 1, 1, 1)
            x = x.sub(vm).div(vs)
            emb = self._vmodel(x.to(self.device)).float().cpu()
        return np.asarray(emb, dtype=np.float32).reshape(-1)

    # ------------------------------------------------------------------ query
    def embed_query(self, query: str) -> np.ndarray:
        """Query -> [512] pooled, L2-normalized (same space as clips)."""
        torch = self._torch
        t = self._tok(query, padding="max_length", truncation=True,
                      max_length=TEXT_MAX_LEN, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self._tmodel(t.input_ids, t.attention_mask)
        pooled = (out[0] if isinstance(out, (tuple, list)) else out).float().cpu().numpy().reshape(-1)
        return pooled

    def predict_moments(
        self,
        query: str,
        features: np.ndarray,
        time_offset: float = 0.0,
        top_n: int = 10,
    ) -> list[tuple[float, float, float]]:
        """Cosine-similarity grounding: high-saliency contiguous clips -> moments.

        Same return contract as LighthouseService.predict_moments:
        list of (start_sec, end_sec, score) with time_offset applied.
        """
        if features.shape[0] == 0:
            return []
        sims = self._saliency(query, features)                 # [N] cosine in [-1,1]
        thr = float(sims.mean() + 0.5 * sims.std())
        spans = _contiguous_spans(sims >= thr)
        if not spans:                                          # fall back to the single best clip
            i = int(sims.argmax()); spans = [(i, i)]
        moments = [
            (time_offset + s * self.clip_length,
             time_offset + (e + 1) * self.clip_length,
             float(sims[s:e + 1].max()))
            for s, e in spans
        ]
        moments.sort(key=lambda m: -m[2])
        return moments[:top_n]

    def predict_saliency(
        self,
        features: np.ndarray,
        query: str | None = None,
        time_offset: float = 0.0,
    ) -> list[tuple[float, float, float]]:
        """Per-clip (start, end, cosine-score). Generic highlight query if none."""
        q = query or "an interesting key moment or highlight from the video"
        sims = self._saliency(q, features)
        return [
            (time_offset + i * self.clip_length, time_offset + (i + 1) * self.clip_length, float(s))
            for i, s in enumerate(sims)
        ]

    # ---------------------------------------------------------------- helpers
    def _saliency(self, query: str, features: np.ndarray) -> np.ndarray:
        q = _l2(self.embed_query(query).astype(np.float32))
        V = _l2(features.astype(np.float32))
        return V @ q                                           # [N]


def _l2(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


def _contiguous_spans(mask: Sequence[bool]) -> list[tuple[int, int]]:
    """Indices of contiguous True runs as (start_idx, end_idx) inclusive."""
    spans: list[tuple[int, int]] = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            spans.append((start, i - 1)); start = None
    if start is not None:
        spans.append((start, len(mask) - 1))
    return spans
