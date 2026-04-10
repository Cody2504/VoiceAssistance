"""
ASR module using ZipFormer-30M-RNNT via sherpa-onnx.

Lightweight speech-to-text for extracting transcripts from video audio tracks.
30M params, runs on CPU in real-time.

Usage:
    asr = ASREngine()
    transcript = asr.transcribe("video.mp4", start_sec=10.0, end_sec=25.0)
"""
import logging
import os
import subprocess
import tempfile
from typing import Optional

log = logging.getLogger(__name__)


class ASREngine:
    """ZipFormer-30M-RNNT ASR engine via sherpa-onnx.

    Falls back to returning empty string if sherpa-onnx is not installed
    or models are not downloaded — allows the pipeline to work without ASR.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir
        self._recognizer = None

    def _lazy_load(self):
        if self._recognizer is not None:
            return

        try:
            import sherpa_onnx

            # Auto-discover model directory — handle extracted tar structure
            model_dir = self.model_dir
            if model_dir and os.path.isdir(model_dir):
                # Check if there's a subdirectory (from tar extraction)
                subdirs = [d for d in os.listdir(model_dir)
                           if os.path.isdir(os.path.join(model_dir, d)) and "zipformer" in d.lower()]
                if subdirs:
                    model_dir = os.path.join(model_dir, subdirs[0])

                # Auto-find ONNX files — prefer int8 variants for CPU speed
                def find_file(pattern_list):
                    for pattern in pattern_list:
                        for f in os.listdir(model_dir):
                            if pattern in f and f.endswith(".onnx"):
                                return os.path.join(model_dir, f)
                    return None

                encoder = find_file(["encoder", "encoder-epoch"]) 
                decoder = find_file(["decoder", "decoder-epoch"])
                joiner = find_file(["joiner", "joiner-epoch"])
                tokens = os.path.join(model_dir, "tokens.txt")

                # Prefer int8 versions if available
                encoder_int8 = find_file(["encoder-epoch-99-avg-1.int8"])
                decoder_int8 = find_file(["decoder-epoch-99-avg-1.int8"])
                joiner_int8 = find_file(["joiner-epoch-99-avg-1.int8"])
                if encoder_int8:
                    encoder = encoder_int8
                if decoder_int8:
                    decoder = decoder_int8
                if joiner_int8:
                    joiner = joiner_int8

                if all([encoder, decoder, joiner, os.path.isfile(tokens)]):
                    self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                        tokens=tokens,
                        encoder=encoder,
                        decoder=decoder,
                        joiner=joiner,
                        num_threads=2,
                        sample_rate=16000,
                    )
                    log.info(f"Loaded ZipFormer ASR from {model_dir}")
                    log.info(f"  encoder: {os.path.basename(encoder)}")
                    log.info(f"  decoder: {os.path.basename(decoder)}")
                    log.info(f"  joiner:  {os.path.basename(joiner)}")
                else:
                    log.warning(
                        f"ZipFormer model files not found in {model_dir}. "
                        f"Found: encoder={encoder}, decoder={decoder}, joiner={joiner}. "
                        "ASR will return empty transcripts."
                    )
                    self._recognizer = "unavailable"
            else:
                log.warning(
                    f"ZipFormer model dir not found at {self.model_dir}. "
                    "ASR will return empty transcripts. "
                    "Download models from: https://github.com/k2-fsa/sherpa-onnx"
                )
                self._recognizer = "unavailable"

        except ImportError:
            log.warning("sherpa-onnx not installed. ASR will return empty transcripts. pip install sherpa-onnx")
            self._recognizer = "unavailable"

    def _extract_audio(self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None) -> str:
        """Extract audio from video as WAV using ffmpeg."""
        audio_path = tempfile.mktemp(suffix=".wav")
        cmd = ["ffmpeg", "-y", "-i", video_path, "-ss", str(start_sec)]
        if end_sec is not None:
            cmd.extend(["-t", str(end_sec - start_sec)])
        cmd.extend([
            "-ar", "16000",  # 16kHz for ASR
            "-ac", "1",      # mono
            "-f", "wav",
            "-loglevel", "quiet",
            audio_path,
        ])
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            log.warning(f"Failed to extract audio: {e}")
            return ""
        return audio_path

    def transcribe(self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None) -> str:
        """Transcribe audio from a video segment.

        Args:
            video_path: Path to video file.
            start_sec: Start time of segment in seconds.
            end_sec: End time of segment in seconds (None = until end).

        Returns:
            Transcript text string. Empty string if ASR is unavailable.
        """
        self._lazy_load()

        if self._recognizer == "unavailable":
            return ""

        # Extract audio segment
        audio_path = self._extract_audio(video_path, start_sec, end_sec)
        if not audio_path or not os.path.isfile(audio_path):
            return ""

        try:
            import wave
            import numpy as np

            with wave.open(audio_path, "rb") as wf:
                sample_rate = wf.getframerate()
                num_samples = wf.getnframes()
                audio_data = wf.readframes(num_samples)
                samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            stream = self._recognizer.create_stream()
            stream.accept_waveform(sample_rate, samples)
            self._recognizer.decode_stream(stream)
            transcript = stream.result.text.strip()

            return transcript

        except Exception as e:
            log.warning(f"ASR transcription failed: {e}")
            return ""
        finally:
            if os.path.isfile(audio_path):
                os.remove(audio_path)
