"""
Whisper ASR Engine — drop-in replacement for the ZipFormer/sherpa-onnx ASR.

Same `transcribe(video_path, start_sec, end_sec) -> str` interface as the existing
`ASREngine` in `asr.py`, so it slots into the feature extractor without code changes
to the caller.

Why Whisper instead of ZipFormer for this thesis:
  - No separate model-dir to host (transformers handles caching automatically)
  - More accurate on noisy/conversational audio, multilingual
  - GPU-friendly via `transformers`; Whisper-base (~74M) is ~3-5× realtime on T4

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
    ):
        self.model_name = model_name
        self.device = device
        self.language = language
        self._model = None
        self._processor = None

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
        """Pull a 16kHz mono WAV segment via ffmpeg."""
        out = tempfile.mktemp(suffix=".wav")
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
            # Whisper hallucinates "Thanks for watching!" on silence — filter common artifacts.
            artifacts = {"thanks for watching!", "thanks for watching.", "you", "."}
            if text.lower() in artifacts:
                return ""
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
