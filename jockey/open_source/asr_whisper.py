"""
Whisper ASR Engine — drop-in replacement for the ZipFormer/sherpa-onnx ASR.

Same `transcribe(video_path, start_sec, end_sec) -> str` interface as the existing
`ASREngine` in `asr.py`, so it slots into the feature extractor without code changes
to the caller.

Why Whisper instead of ZipFormer for this thesis:
  - No separate model-dir to host (transformers handles caching automatically)
  - More accurate on noisy/conversational audio, multilingual
  - GPU-friendly via `transformers`; Whisper-base (~74M) is ~3-5× realtime on T4

**Defense against silence-induced hallucinations**: pre-Whisper RMS-energy check.
If the segment is below `silence_rms_threshold`, skip Whisper entirely (returns "").
This is the principled fix — no heuristic keyword filtering of the output, which
would risk false-positives on real short utterances ("Okay", "Mm", etc.).

Usage:
    asr = WhisperASR(model_name="openai/whisper-base", device="cuda")
    text = asr.transcribe("video.mp4", start_sec=4.0, end_sec=8.0)
"""
import logging
import os
import subprocess
import tempfile
import wave
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class WhisperASR:
    """Whisper-based ASR via HuggingFace transformers."""

    def __init__(
        self,
        model_name: str = "openai/whisper-base",
        device: str = "cuda",
        language: str = "en",
        silence_rms_threshold: float = 0.005,
    ):
        self.model_name = model_name
        self.device = device
        self.language = language
        self.silence_rms_threshold = silence_rms_threshold
        self._model = None
        self._processor = None
        self._n_silent = 0
        self._n_transcribed = 0

    def _resolve_device(self) -> str:
        if self.device.startswith("cuda"):
            try:
                import torch
                if not torch.cuda.is_available():
                    log.warning("Whisper: CUDA requested but unavailable; falling back to CPU.")
                    self.device = "cpu"
            except ImportError:
                self.device = "cpu"
        return self.device

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        device = self._resolve_device()
        log.info(f"Loading Whisper ASR from {self.model_name} on {device}...")
        try:
            from transformers import WhisperProcessor, WhisperForConditionalGeneration

            self._processor = WhisperProcessor.from_pretrained(self.model_name)
            self._model = WhisperForConditionalGeneration.from_pretrained(self.model_name)
            self._model = self._model.to(device).eval()
            n_params = sum(p.numel() for p in self._model.parameters())
            log.info(f"Loaded Whisper ASR ({n_params/1e6:.1f}M params, device={device})")
        except Exception as e:
            log.warning(f"Could not load Whisper: {e}. ASR will return empty transcripts.")
            self._model = "unavailable"

    def _extract_audio_wav(
        self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> Optional[str]:
        """Pull a 16kHz mono WAV segment via ffmpeg. (Kept for backward-compat;
        batched path uses pre-loaded sample arrays via transcribe_batch.)"""
        fd, out = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        cmd = ["ffmpeg", "-y", "-i", video_path, "-ss", str(start_sec)]
        if end_sec is not None:
            cmd.extend(["-t", str(end_sec - start_sec)])
        cmd.extend([
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            "-loglevel", "quiet",
            out,
        ])
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return out
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            log.debug(f"Whisper: ffmpeg audio extraction failed: {e}")
            return None

    def transcribe(
        self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> str:
        """Transcribe an audio segment from a video. Returns "" on any failure."""
        self._lazy_load()
        if self._model == "unavailable":
            return ""

        audio_path = self._extract_audio_wav(video_path, start_sec, end_sec)
        if not audio_path or not os.path.isfile(audio_path):
            return ""

        try:
            import torch

            with wave.open(audio_path, "rb") as wf:
                num_samples = wf.getnframes()
                if num_samples < 1600:  # < 0.1s of audio
                    return ""
                raw = wf.readframes(num_samples)

            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if samples.size == 0:
                return ""

            # Silence check — skip Whisper entirely for silent windows.
            # Major speedup + eliminates the "Thank you" / "Mm" hallucinations.
            rms = float(np.sqrt(np.mean(samples ** 2)))
            if rms < self.silence_rms_threshold:
                self._n_silent += 1
                return ""

            inputs = self._processor(
                samples, sampling_rate=16000, return_tensors="pt"
            )
            input_features = inputs.input_features.to(self.device)

            with torch.no_grad():
                ids = self._model.generate(
                    input_features,
                    max_new_tokens=128,
                    language=self.language,
                    task="transcribe",
                )
            text = self._processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
            if not text:
                return ""
            self._n_transcribed += 1
            return text
        except Exception as e:
            log.warning(f"Whisper transcription failed: {e}")
            return ""
        finally:
            if audio_path and os.path.isfile(audio_path):
                try:
                    os.remove(audio_path)
                except OSError:
                    pass

    def transcribe_batch(self, samples_list, sampling_rate: int = 16000):
        """Transcribe multiple pre-loaded audio clips in a single Whisper forward.

        Per-item silence detection (RMS) skips silent clips before any GPU work.
        Empty / silent clips return "" at their index.

        Args:
            samples_list: List of N 1D float32 arrays (16kHz mono).

        Returns:
            List[str] of length N. Empty strings for silent / failed clips.
        """
        self._lazy_load()
        n = len(samples_list)
        results = [""] * n
        if self._model == "unavailable" or n == 0:
            return results

        # Pre-filter by silence — skip Whisper entirely on silent windows.
        non_silent_idx, non_silent = [], []
        for i, s in enumerate(samples_list):
            if s is None or len(s) < 1600:
                continue
            arr = np.asarray(s, dtype=np.float32)
            rms = float(np.sqrt(np.mean(arr ** 2)))
            if rms < self.silence_rms_threshold:
                self._n_silent += 1
                continue
            non_silent_idx.append(i)
            non_silent.append(arr)

        if not non_silent:
            return results

        try:
            import torch
            inputs = self._processor(
                non_silent, sampling_rate=sampling_rate, return_tensors="pt"
            )
            input_features = inputs.input_features.to(self.device)
            with torch.no_grad():
                ids = self._model.generate(
                    input_features,
                    max_new_tokens=128,
                    language=self.language,
                    task="transcribe",
                )
            texts = self._processor.batch_decode(ids, skip_special_tokens=True)
            for idx, text in zip(non_silent_idx, texts):
                text = text.strip()
                if text:
                    results[idx] = text
                    self._n_transcribed += 1
        except Exception as e:
            log.warning(f"transcribe_batch failed: {e}")
        return results

    def stats(self) -> dict:
        """Per-instance counters: how many windows were silent / transcribed."""
        total = self._n_silent + self._n_transcribed
        return {
            "silent": self._n_silent,
            "transcribed": self._n_transcribed,
            "total": total,
        }
