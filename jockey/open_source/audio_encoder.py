"""
Audio Encoder — wav2vec2-based acoustic embedding for video segments.

Extracts audio from video, encodes with wav2vec2, pools into a fixed-dim vector.
This replaces the ASR-transcript-as-proxy approach with direct acoustic features,
capturing music, tone, sound effects, and speech prosody.

Usage:
    encoder = AudioEncoder()
    emb = encoder.encode_audio("video.mp4", start_sec=10.0, end_sec=25.0)  # [768]
"""
import logging
import os
import subprocess
import tempfile
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class AudioEncoder:
    """wav2vec2 audio encoder for extracting acoustic embeddings.

    Uses facebook/wav2vec2-base-960h by default (95M params, 768-dim output).
    Falls back to random embeddings if the model can't be loaded.
    """

    def __init__(self, model_name: str = "facebook/wav2vec2-base-960h", device: str = "cuda"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None
        self._embedding_dim = 768

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _lazy_load(self):
        """Lazy-load the wav2vec2 model only when first needed."""
        if self._model is not None:
            return

        log.info(f"Loading audio encoder from {self.model_name}...")
        try:
            from transformers import Wav2Vec2Model, Wav2Vec2Processor

            self._processor = Wav2Vec2Processor.from_pretrained(self.model_name)
            self._model = Wav2Vec2Model.from_pretrained(self.model_name)
            self._model = self._model.to(self.device).eval()
            self._embedding_dim = self._model.config.hidden_size
            log.info(f"Loaded wav2vec2 audio encoder (dim={self._embedding_dim}).")
        except (ImportError, Exception) as e:
            log.warning(f"Could not load wav2vec2 model: {e}. Using random embeddings.")
            self._model = "placeholder"

    def _extract_audio_wav(
        self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> Optional[str]:
        """Extract audio from video as 16kHz mono WAV using ffmpeg."""
        audio_path = tempfile.mktemp(suffix=".wav")
        cmd = ["ffmpeg", "-y", "-i", video_path, "-ss", str(start_sec)]
        if end_sec is not None:
            cmd.extend(["-t", str(end_sec - start_sec)])
        cmd.extend([
            "-ar", "16000",   # 16kHz for wav2vec2
            "-ac", "1",       # mono
            "-f", "wav",
            "-loglevel", "quiet",
            audio_path,
        ])
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            log.warning(f"Failed to extract audio: {e}")
            return None

    def encode_audio(
        self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> np.ndarray:
        """Encode audio from a video segment into a normalized embedding vector.

        Args:
            video_path: Path to video file.
            start_sec: Start time in seconds.
            end_sec: End time in seconds (None = until end).

        Returns:
            Normalized embedding vector [D] (default D=768).
        """
        self._lazy_load()

        if self._model == "placeholder":
            emb = np.random.randn(self._embedding_dim).astype(np.float32)
            return emb / np.linalg.norm(emb)

        # Extract audio segment
        audio_path = self._extract_audio_wav(video_path, start_sec, end_sec)
        if not audio_path or not os.path.isfile(audio_path):
            log.warning("Audio extraction failed, returning random embedding.")
            emb = np.random.randn(self._embedding_dim).astype(np.float32)
            return emb / np.linalg.norm(emb)

        try:
            import torch
            import wave

            # Read WAV
            with wave.open(audio_path, "rb") as wf:
                sample_rate = wf.getframerate()
                num_samples = wf.getnframes()
                audio_data = wf.readframes(num_samples)
                samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            if len(samples) == 0:
                log.warning("Empty audio, returning random embedding.")
                emb = np.random.randn(self._embedding_dim).astype(np.float32)
                return emb / np.linalg.norm(emb)

            # Process through wav2vec2
            inputs = self._processor(
                samples, sampling_rate=16000, return_tensors="pt", padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)
                # Mean-pool over time dimension: [1, T, D] → [D]
                hidden_states = outputs.last_hidden_state  # [1, T, 768]
                emb = hidden_states.mean(dim=1).squeeze(0)  # [768]

            emb = emb.cpu().numpy().astype(np.float32)
            emb = emb / np.linalg.norm(emb)
            return emb

        except Exception as e:
            log.warning(f"Audio encoding failed: {e}. Returning random embedding.")
            emb = np.random.randn(self._embedding_dim).astype(np.float32)
            return emb / np.linalg.norm(emb)

        finally:
            if audio_path and os.path.isfile(audio_path):
                os.remove(audio_path)
