"""CLAP encoder (roadmap #2) — text↔audio aligned embeddings for the
audio-event vector index.

Unlike purely acoustic encoders (no text side), CLAP (`msclap`) embeds audio and
text into one 1024-d space, so a text query ("crowd cheering", "whistle",
"music") can retrieve matching audio segments. Used both at ingest (per-segment
audio embeddings → `jockey_audio_events`) and at query time (text → vector).
"""
from __future__ import annotations

import logging
import os
import tempfile

import numpy as np

log = logging.getLogger(__name__)

_UNAVAILABLE = "unavailable"
_CLAP_DIM = 1024


class CLAPEncoder:
    def __init__(self, version: str = "2023", use_cuda: bool = False):
        self.version = version
        self.use_cuda = use_cuda
        self._model = None

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            from msclap import CLAP
            self._model = CLAP(version=self.version, use_cuda=self.use_cuda)
            log.info("CLAPEncoder ready (version=%s, cuda=%s)", self.version, self.use_cuda)
        except Exception as exc:  # noqa: BLE001
            log.warning("CLAPEncoder unavailable: %s", exc)
            self._model = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._model not in (None, _UNAVAILABLE)

    @staticmethod
    def _to_np(t) -> np.ndarray:
        a = t.detach().cpu().numpy() if hasattr(t, "detach") else np.asarray(t)
        return np.asarray(a, dtype=np.float32)

    @staticmethod
    def _l2(a: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(a, axis=-1, keepdims=True)
        return a / np.where(n > 0, n, 1.0)

    def encode_text(self, query: str) -> np.ndarray | None:
        """Encode a text query into the shared CLAP space (1024-d, L2-normed)."""
        self._lazy_load()
        if self._model in (None, _UNAVAILABLE):
            return None
        a = self._l2(self._to_np(self._model.get_text_embeddings([query])))
        return a[0]

    def encode_audio_segments(self, local_path, segments) -> np.ndarray | None:
        """Per-segment CLAP audio embeddings [N, 1024], L2-normed. Slices the
        video's audio per segment (32 kHz mono) and writes a temp wav per slice
        (msclap reads files). Empty/silent slices get a zero vector."""
        self._lazy_load()
        if self._model in (None, _UNAVAILABLE):
            return None
        import soundfile as sf
        from main.encoders.audio_event_encoder import _load_full_audio_32k_mono, slice_samples
        full = _load_full_audio_32k_mono(local_path)
        out: list[np.ndarray] = []
        for s_, e_ in segments:
            seg = slice_samples(full, float(s_), float(e_), sr=32000)
            if seg is None or len(seg) == 0:
                out.append(np.zeros(_CLAP_DIM, np.float32))
                continue
            path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    path = tf.name
                sf.write(path, seg, 32000)
                vec = self._l2(self._to_np(self._model.get_audio_embeddings([path])))[0]
                out.append(vec.astype(np.float32))
            except Exception as exc:  # noqa: BLE001
                log.warning("CLAP audio embed failed for [%s,%s]: %s", s_, e_, exc)
                out.append(np.zeros(_CLAP_DIM, np.float32))
            finally:
                if path and os.path.exists(path):
                    os.unlink(path)
        return np.stack(out) if out else None
