"""
Moment Localizer — runtime wrapper for the trained QDDETRHead.

Loads a trained checkpoint produced by `qd_detr_train.py` and predicts
`(start_sec, end_sec)` for a `(query, video_id)` pair using precomputed
feature `.npz` files.

This is the "what does the trained head actually do at inference time?"
entry point. The training loop emits IoU metrics on a held-out test set;
this module lets you run the head on arbitrary (query, video) pairs and
inspect its predictions directly.

Reuses ViCLIP's CLIP-text tower for query encoding so the query lives in
the same 768-d space as the precomputed visual features — same alignment
the head was trained on.

Usage:
    loc = MomentLocalizer(
        checkpoint_path="runs/qd_detr_clip/best.pt",
        features_dir="features/charades/",
        device="cuda",
    )
    pred = loc.localize("person opening a door", video_id="001YG")
    print(pred.start_sec, pred.end_sec, pred.confidence)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch

from jockey.open_source.training.feature_extractor import ShotFeatures
from jockey.open_source.training.qd_detr_head import QDDETRConfig, QDDETRHead

log = logging.getLogger(__name__)


@dataclass
class MomentPrediction:
    video_id: str
    query: str
    start_sec: float
    end_sec: float
    confidence: float           # mean saliency over shots overlapping predicted span
    duration: float
    # Optional: per-shot relevance for debugging. QDDETRHead populates this;
    # LLM-based grounders (TRACE) leave it None.
    saliency: Optional[np.ndarray] = None


class MomentLocalizer:
    """Predicts (start, end) for (query, video) using a trained QDDETRHead.

    Frozen at inference. Features must have been precomputed with the SAME
    encoder used during training — for Variant 2 runs that's CLIP-L (or
    whatever your `features_dir` contains).
    """

    def __init__(
        self,
        checkpoint_path: str,
        features_dir: str,
        viclip_embedder=None,         # lazy-loads from config if None
        device: str = "cpu",
    ):
        if not os.path.isfile(checkpoint_path):
            raise FileNotFoundError(
                f"Checkpoint not found: {checkpoint_path}. "
                f"Finish a qd_detr_train.py run first — it writes best.pt to --out-dir."
            )

        self.features_dir = features_dir
        self.device = device
        self._viclip = viclip_embedder

        ckpt = torch.load(checkpoint_path, map_location=device)
        if ckpt.get("head_class") != "QDDETRHead":
            log.warning(
                f"checkpoint head_class={ckpt.get('head_class')!r} (expected 'QDDETRHead') — "
                f"proceeding but verify this is the right checkpoint."
            )

        cfg_fields = QDDETRConfig.__dataclass_fields__
        cfg = QDDETRConfig(**{k: v for k, v in ckpt["config"].items() if k in cfg_fields})
        self.cfg = cfg
        self.head = QDDETRHead(cfg).to(device).eval()
        self.head.load_state_dict(ckpt["model"])

        log.info(
            f"loaded QDDETRHead ({self.head.num_trainable_params()/1e6:.2f}M params) "
            f"from {checkpoint_path}"
        )
        log.info(
            f"  epoch={ckpt.get('epoch')} best_val_R@0.5={ckpt.get('best_r05', 'n/a')}"
        )

    @property
    def viclip(self):
        """Lazy-load ViCLIP/CLIP-text on first use."""
        if self._viclip is None:
            from jockey.open_source.config import config
            from jockey.open_source.viclip_embedder import ViCLIPEmbedder
            self._viclip = ViCLIPEmbedder(
                model_name_or_path=config.viclip_model_name,
                device=self.device,
            )
        return self._viclip

    def _feature_path(self, video_id: str) -> str:
        return os.path.join(self.features_dir, f"{video_id}.npz")

    @torch.no_grad()
    def localize(self, query: str, video_id: str) -> MomentPrediction:
        """Predict moment span for (query, video). All times in seconds."""
        fpath = self._feature_path(video_id)
        if not os.path.isfile(fpath):
            raise FileNotFoundError(
                f"No feature file at {fpath}. Run feature extraction for this "
                f"video_id first, or check the path."
            )
        feats = ShotFeatures.load(fpath)

        # Query → CLIP-text 768-d, aligned with the visual features.
        query_emb = self.viclip.encode_text(query)                              # [Q]

        visual = (
            torch.from_numpy(feats.visual_features).float()
            .unsqueeze(0).to(self.device)                                       # [1, N, V]
        )
        query_t = torch.from_numpy(query_emb).float().unsqueeze(0).to(self.device)  # [1, Q]

        sal_logits, boundary = self.head(visual=visual, query=query_t, shot_mask=None)
        # boundary is [1, 2] in [0, 1] — head outputs sigmoid'd.
        start_n, end_n = boundary[0].tolist()
        if end_n < start_n:
            start_n, end_n = end_n, start_n

        start_sec = float(start_n * feats.duration)
        end_sec   = float(end_n   * feats.duration)

        saliency = torch.sigmoid(sal_logits)[0].cpu().numpy()                   # [N]
        sb = feats.shot_boundaries
        overlap = (sb[:, 0] < end_sec) & (sb[:, 1] > start_sec)
        confidence = float(saliency[overlap].mean()) if overlap.any() else float(saliency.max())

        return MomentPrediction(
            video_id=video_id, query=query,
            start_sec=start_sec, end_sec=end_sec,
            confidence=confidence, saliency=saliency,
            duration=float(feats.duration),
        )

    def localize_batch(self, queries_and_video_ids):
        """Convenience: list of (query, video_id) → list of MomentPrediction."""
        return [self.localize(q, v) for q, v in queries_and_video_ids]
