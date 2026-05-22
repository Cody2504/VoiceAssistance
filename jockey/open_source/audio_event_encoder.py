"""PANN CNN14 audio-event tagger — closes UC #15 (specific sounds).

Wraps `panns_inference` (Kong et al., pre-trained on AudioSet 527 classes).
First load downloads ~600MB. CPU-runnable.

Per-shot top-K tags are stored in Qdrant payload as `audio_tags`.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
import wave
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


def _load_full_audio_32k_mono(video_path: str) -> Optional[np.ndarray]:
    """ffmpeg → 32kHz mono float32 array (PANN's expected sample rate)."""
    import os
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-ar", "32000", "-ac", "1", "-f", "wav",
             "-loglevel", "quiet", wav_path],
            check=True, capture_output=True,
        )
        with wave.open(wav_path, "rb") as wf:
            n = wf.getnframes()
            raw = wf.readframes(n)
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except (subprocess.CalledProcessError, FileNotFoundError, wave.Error) as exc:
        log.warning("audio_event_encoder: ffmpeg extract failed: %s", exc)
        return None
    finally:
        try: os.remove(wav_path)
        except OSError: pass


class AudioEventEncoder:
    """Lazy wrapper around PANN AudioTagging."""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._tagger = None
        self._labels: Optional[list[str]] = None

    def _load(self):
        if self._tagger is not None:
            return
        # panns_inference is the lightest packaging of CNN14
        from panns_inference import AudioTagging, labels  # type: ignore
        log.info("audio_event_encoder: loading PANN CNN14 (device=%s)", self.device)
        self._tagger = AudioTagging(checkpoint_path=None, device=self.device)
        self._labels = list(labels)
        log.info("audio_event_encoder: ready (%d labels)", len(self._labels))

    def tag_audio_segment(self, samples_32k_mono: np.ndarray, top_k: int = 5) -> list[dict]:
        """Return top-K AudioSet tags for a mono 32kHz waveform.

        Returns list of {label: str, score: float}, sorted desc. Empty list on
        failure or empty input.
        """
        if samples_32k_mono is None or samples_32k_mono.size == 0:
            return []
        try:
            self._load()
        except Exception as exc:
            log.warning("audio_event_encoder: load failed (%s) — returning empty tags", exc)
            return []
        try:
            # PANN expects shape (batch, time)
            x = samples_32k_mono.reshape(1, -1).astype(np.float32)
            clipwise, _ = self._tagger.inference(x)  # clipwise: (1, 527)
        except Exception as exc:
            log.warning("audio_event_encoder: inference failed: %s", exc)
            return []
        scores = np.asarray(clipwise[0])
        top_idx = np.argsort(-scores)[:top_k]
        return [
            {"label": (self._labels[i] if self._labels else f"class_{i}"),
             "score": float(scores[i])}
            for i in top_idx
        ]


def slice_samples(samples: Optional[np.ndarray], start_sec: float, end_sec: float, sr: int = 32000) -> Optional[np.ndarray]:
    if samples is None:
        return None
    a = max(0, int(start_sec * sr))
    b = min(samples.shape[0], int(end_sec * sr))
    if b <= a:
        return None
    return samples[a:b]
