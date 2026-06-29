"""DINOv2 instance-embedding encoder for image search.

DINOv2 (self-supervised, no text guidance) captures pixel/patch-level detail
that distinguishes one specific video from another of the same category — where
CLIP's category-level vector fails (e.g. two different tennis videos). Used as a
parallel retrieval channel to CLIP-L. Mirrors CLIPLEmbedder's interface +
offline ``"placeholder"`` fallback so the test suite runs without weights/GPU.
"""
from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger(__name__)

_DEFAULT_DIM = 1024  # facebook/dinov2-large hidden_size


class DINOv2Embedder:
    def __init__(self, model_name_or_path: str = "facebook/dinov2-large", device: str = "cuda"):
        self.model_name_or_path = model_name_or_path
        self.device = device
        self._model = None
        self._processor = None
        self.embedding_dim = _DEFAULT_DIM
        self._hf_token = os.environ.get("HF_TOKEN") or None

    def _resolve_device(self) -> str:
        if self.device.startswith("cuda"):
            try:
                import torch
                if not torch.cuda.is_available():
                    log.warning("CUDA requested for DINOv2 but unavailable; using CPU.")
                    self.device = "cpu"
            except ImportError:
                self.device = "cpu"
        return self.device

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        device = self._resolve_device()
        try:
            from transformers import AutoImageProcessor, AutoModel
            self._model = AutoModel.from_pretrained(self.model_name_or_path, token=self._hf_token)
            self._model = self._model.to(device).eval()
            self._processor = AutoImageProcessor.from_pretrained(self.model_name_or_path, token=self._hf_token)
            try:
                self.embedding_dim = int(self._model.config.hidden_size)
            except AttributeError:
                pass
            log.info("Loaded DINOv2 %s (dim=%d, device=%s)", self.model_name_or_path, self.embedding_dim, device)
        except Exception as e:  # noqa: BLE001
            log.warning("Could not load DINOv2 (%s); using placeholder embeddings.", e)
            self._model = "placeholder"

    def _pool(self, frames: np.ndarray) -> np.ndarray:
        import torch
        from PIL import Image
        with torch.no_grad():
            pil = [Image.fromarray(f) for f in frames]
            inputs = self._processor(images=pil, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            out = self._model(**inputs)
            feats = out.pooler_output  # [N, dim] CLS token
            emb = feats.mean(dim=0).cpu().numpy().astype(np.float32)
        n = np.linalg.norm(emb)
        return emb / max(n, 1e-12)

    def encode_video(self, frames: np.ndarray) -> np.ndarray:
        """One L2-normalized [dim] vector for a set of frames (mean-pooled)."""
        self._lazy_load()
        if self._model == "placeholder":
            r = np.random.randn(self.embedding_dim).astype(np.float32)
            return r / max(np.linalg.norm(r), 1e-12)
        return self._pool(frames)

    def encode_video_batch(self, frames_list):
        """[N, dim] L2-normalized per-segment embeddings. None/empty shots → zero."""
        self._lazy_load()
        n = len(frames_list)
        out = np.zeros((n, self.embedding_dim), dtype=np.float32)
        for i, frames in enumerate(frames_list):
            if frames is None or getattr(frames, "size", 0) == 0:
                continue
            if self._model == "placeholder":
                r = np.random.randn(self.embedding_dim).astype(np.float32)
                out[i] = r / max(np.linalg.norm(r), 1e-12)
            else:
                out[i] = self._pool(frames)
        return out
