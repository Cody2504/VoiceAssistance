"""Motion encoder (research item A) — real ViCLIP (vendored, temporal) for the
`jockey_motion` retrieval stream.

Unlike CLIPLEmbedder (per-frame CLIP-L mean-pooled — appearance only), ViCLIP
attends across frames, so "adding tomato to the pan" ranks the clip where the
adding HAPPENS above clips where a tomato is merely visible. Used at ingest
(per-segment video embeddings → `jockey_motion`) and at query time (text →
same 768-d space) by the `when` motion stream + POST /videos/search/motion.

Weights are NOT bundled: `ViClip-InternVid-10M-FLT.pth` (HF OpenGVLab/ViCLIP)
must sit at `settings.motion_weights`. Lazy `_UNAVAILABLE` pattern throughout.
"""
from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger(__name__)

_UNAVAILABLE = "unavailable"

# ImageNet mean/std — what ViCLIP trained with (upstream __init__.normalize).
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)


def _install_easydict_shim() -> None:
    """The official ViCLIP checkpoint pickles `utils.easydict.EasyDict` (a
    module from OpenGVLab's training repo we don't vendor). Register a minimal
    stand-in so torch.load can unpickle the metadata. setdefault-only — never
    shadows a real `utils` package if one ever appears."""
    import sys
    import types

    if "utils.easydict" in sys.modules:
        return

    class EasyDict(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

        def __setattr__(self, name, value):
            self[name] = value

    ez = types.ModuleType("utils.easydict")
    ez.EasyDict = EasyDict
    utils_mod = sys.modules.setdefault("utils", types.ModuleType("utils"))
    setattr(utils_mod, "easydict", ez)
    sys.modules["utils.easydict"] = ez


def sample_uniform(n_have: int, n_want: int) -> list[int]:
    """Uniformly spread n_want indices over [0, n_have) (repeats when short)."""
    if n_have <= 0:
        return []
    return [int(round(i)) for i in np.linspace(0, n_have - 1, n_want)]


class MotionEncoder:
    def __init__(self, weights_path: str, embedding_dim: int = 768, num_frames: int = 8):
        self.weights_path = weights_path
        self.embedding_dim = embedding_dim
        self.num_frames = num_frames
        self._model = None
        self._tokenizer = None
        self._device = "cpu"

    @classmethod
    def from_settings(cls, settings) -> "MotionEncoder":
        return cls(
            weights_path=settings.motion_weights,
            embedding_dim=settings.motion_embedding_dim,
            num_frames=settings.motion_frames_per_segment,
        )

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        if not os.path.exists(self.weights_path):
            log.warning("MotionEncoder unavailable: weights not found at %s", self.weights_path)
            self._model = _UNAVAILABLE
            return
        try:
            import torch
            from main.encoders.viclip.simple_tokenizer import SimpleTokenizer
            from main.encoders.viclip.viclip import ViCLIP
            _install_easydict_shim()
            self._tokenizer = SimpleTokenizer()
            model = ViCLIP(tokenizer=self._tokenizer, size="l", pretrain=self.weights_path)
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = model.to(self._device).eval()
            log.info("MotionEncoder ready (ViCLIP-L, device=%s)", self._device)
        except Exception as exc:  # noqa: BLE001
            log.warning("MotionEncoder unavailable: %s", exc)
            self._model = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._model not in (None, _UNAVAILABLE)

    def _frames_to_tensor(self, frames: np.ndarray):
        """[N, H, W, 3] uint8 RGB → ViCLIP input [1, num_frames, 3, 224, 224].
        (Upstream frames2tensor assumes BGR cv2 frames; ours are already RGB.)"""
        import cv2
        import torch
        idxs = sample_uniform(len(frames), self.num_frames)
        resized = [
            (cv2.resize(np.asarray(frames[i], dtype=np.uint8), (224, 224)).astype(np.float32)
             / 255.0 - _MEAN) / _STD
            for i in idxs
        ]
        tube = np.stack(resized)[None, ...]              # [1, T, H, W, 3]
        tube = np.transpose(tube, (0, 1, 4, 2, 3))       # [1, T, 3, H, W]
        return torch.from_numpy(tube).float().to(self._device)

    def encode_video(self, frames: np.ndarray) -> np.ndarray | None:
        """Temporal clip embedding [embedding_dim], L2-normed. None on failure."""
        self._lazy_load()
        if self._model in (None, _UNAVAILABLE):
            return None
        if frames is None or len(frames) == 0:
            return None
        try:
            feat = self._model.get_vid_features(self._frames_to_tensor(frames))
            return feat.cpu().numpy()[0].astype(np.float32)
        except Exception as exc:  # noqa: BLE001
            log.warning("MotionEncoder: video encode failed: %s", exc)
            return None

    def encode_text(self, query: str) -> np.ndarray | None:
        """Text embedding in the same space [embedding_dim], L2-normed."""
        self._lazy_load()
        if self._model in (None, _UNAVAILABLE) or not (query or "").strip():
            return None
        try:
            feat = self._model.get_text_features(query.strip(), self._tokenizer, {})
            return feat.cpu().numpy()[0].astype(np.float32)
        except Exception as exc:  # noqa: BLE001
            log.warning("MotionEncoder: text encode failed: %s", exc)
            return None
