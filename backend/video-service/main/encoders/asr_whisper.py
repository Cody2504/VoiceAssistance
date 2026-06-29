"""
Whisper ASR Engine — faster-whisper (CTranslate2) backend.

Same public API as the previous transformers-based ``WhisperASR`` so the
ingest pipeline doesn't change:

  - ``WhisperASR.transcribe(video, start, end) -> str``
  - ``WhisperASR.transcribe_batch(samples_list, sr) -> List[str]``
  - ``transcribe_segment(video, start, end) -> str``   (module-level singleton)

New, opt-in:

  - ``WhisperASR.transcribe_with_words(video, start, end) -> dict``
    Returns ``{"text", "segments": [{"start", "end", "text",
                                      "words": [{"word", "start", "end"}]}]}``
    Word-level timestamps come from faster-whisper's cross-attention DTW
    (``word_timestamps=True``). Timestamps are in the original video's
    reference frame (``start_sec`` is added to all model-relative times).

Why faster-whisper (vs the previous HF transformers Whisper):
  - CTranslate2 backend is ~3-4× faster at the same WER, on both GPU
    (fp16) and CPU (int8).
  - Silero VAD pre-filter (``vad_filter=True``) replaces the legacy RMS
    silence heuristic — silent windows are skipped before any decoder
    work runs, no manual threshold to tune.
  - Word-level timestamps via DTW — feeds the sentence-boundary chunk
    refinement in ``indexer.refine_long_shot``.

We use faster-whisper directly rather than the WhisperX wrapper because
WhisperX pulls in pyannote-audio for VAD chunking, and pyannote-audio
3.x is incompatible with torchaudio>=2.11 (uses removed
``torchaudio.AudioMetaData`` / ``torchaudio.info``). faster-whisper
brings its own Silero VAD + DTW word timestamps, so we don't lose
anything that matters for the ingest pipeline. WhisperX's main
remaining advantage — wav2vec2 forced alignment — is unnecessary for
sentence-boundary chunking at ~0.4s pause granularity.

Defaults tuned for the vast.ai 4090 deployment (with CPU as graceful fallback):
  - model: ``distil-large-v3`` — distilled Whisper-large-v3 from `distil-whisper`,
    ~6× faster than ``large-v3`` at near-identical WER and ~½ the VRAM. On a 4090
    it's ~real-time + comfortable batching; on CPU it's still tolerable for short
    clips. Override via ``WHISPER_MODEL``; the smaller ``base`` / ``tiny`` are
    available for the lightest-weight Colab path.
  - compute_type: ``float16`` on CUDA, ``int8`` on CPU
  - beam_size: 5
  - vad_filter: on
"""
import logging
import os
import subprocess
import tempfile
from typing import List, Optional

import numpy as np

log = logging.getLogger(__name__)


_UNAVAILABLE = "unavailable"


def _resolve_default_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _default_compute_type(device: str) -> str:
    return "float16" if device.startswith("cuda") else "int8"


class WhisperASR:
    """faster-whisper-backed ASR with the original WhisperASR public API.

    The ``silence_rms_threshold`` ctor arg is kept for back-compat but no
    longer drives behavior — Silero VAD inside faster-whisper handles
    silence. The ``_n_silent`` counter is populated from segments that VAD
    drops (transcribe returns no segments).
    """

    def __init__(
        self,
        model_name: str = "distil-large-v3",
        device: Optional[str] = None,
        language: str = "en",
        silence_rms_threshold: float = 0.005,   # back-compat, unused
        compute_type: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
    ):
        self.model_name = model_name
        self.device = device or _resolve_default_device()
        self.language = language
        self.silence_rms_threshold = silence_rms_threshold
        self.compute_type = compute_type or _default_compute_type(self.device)
        self.beam_size = beam_size
        self.vad_filter = vad_filter

        self._model = None
        self._n_silent = 0
        self._n_transcribed = 0

    # lazy loader

    def _resolve_device(self) -> str:
        if self.device.startswith("cuda"):
            try:
                import torch
                if not torch.cuda.is_available():
                    log.warning("Whisper: CUDA requested but unavailable; falling back to CPU.")
                    self.device = "cpu"
                    self.compute_type = "int8"
            except ImportError:
                self.device = "cpu"
                self.compute_type = "int8"
        return self.device

    def _lazy_load_model(self) -> None:
        if self._model is not None:
            return
        device = self._resolve_device()
        log.info(
            f"Loading faster-whisper model='{self.model_name}' device={device} "
            f"compute_type={self.compute_type} ..."
        )
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=self.compute_type,
            )
            log.info(f"Loaded faster-whisper model='{self.model_name}' on {device}.")
        except Exception as e:
            log.warning(f"Could not load faster-whisper: {e}. ASR will return empty transcripts.")
            self._model = _UNAVAILABLE

    # audio extraction

    def _extract_audio_wav(
        self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> Optional[str]:
        """Pull a 16 kHz mono WAV segment via ffmpeg. Returns path or None."""
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

    @staticmethod
    def _cleanup(audio_path: Optional[str]) -> None:
        if audio_path and os.path.isfile(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass

    # internal: one transcribe call against an audio input

    def _run_transcribe(self, audio, word_timestamps: bool = False):
        """Single faster-whisper invocation. Returns (segments_list, info).

        ``audio`` may be a file path or a 1-D float32 numpy array (16 kHz mono).
        Materializes the segments generator into a list so the caller can
        traverse it multiple times safely.
        """
        segments, info = self._model.transcribe(
            audio,
            beam_size=self.beam_size,
            language=self.language,
            task="transcribe",
            vad_filter=self.vad_filter,
            word_timestamps=word_timestamps,
        )
        return list(segments), info

    # public API

    def transcribe(
        self, video_path: str, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> str:
        """Transcribe an audio segment. Returns "" on any failure / silence."""
        self._lazy_load_model()
        if self._model == _UNAVAILABLE:
            return ""

        audio_path = self._extract_audio_wav(video_path, start_sec, end_sec)
        if not audio_path or not os.path.isfile(audio_path):
            return ""

        try:
            segs, _info = self._run_transcribe(audio_path, word_timestamps=False)
            if not segs:
                self._n_silent += 1
                return ""
            text = " ".join((s.text or "").strip() for s in segs).strip()
            if not text:
                self._n_silent += 1
                return ""
            self._n_transcribed += 1
            return text
        except Exception as e:
            log.warning(f"faster-whisper transcription failed: {e}")
            return ""
        finally:
            self._cleanup(audio_path)

    def transcribe_batch(self, samples_list, sampling_rate: int = 16000) -> List[str]:
        """Transcribe N pre-loaded float32 mono audio arrays (16 kHz).

        faster-whisper doesn't batch across separate clips — we loop
        per-clip. The speedup vs the old transformers path comes from CT2
        plus VAD-driven silence skip, not cross-clip batching.

        Args:
            samples_list: List of N 1-D float32 arrays (16 kHz mono).

        Returns:
            ``List[str]`` of length N. "" for silent / failed clips.
        """
        self._lazy_load_model()
        n = len(samples_list)
        results: List[str] = [""] * n
        if self._model == _UNAVAILABLE or n == 0:
            return results

        for i, s in enumerate(samples_list):
            if s is None:
                continue
            arr = np.asarray(s, dtype=np.float32)
            if arr.size < 1600:   # < 0.1 s
                continue
            try:
                segs, _info = self._run_transcribe(arr, word_timestamps=False)
                if not segs:
                    self._n_silent += 1
                    continue
                text = " ".join((seg.text or "").strip() for seg in segs).strip()
                if text:
                    results[i] = text
                    self._n_transcribed += 1
                else:
                    self._n_silent += 1
            except Exception as e:
                log.warning(f"transcribe_batch item {i} failed: {e}")
        return results

    def transcribe_with_words(
        self,
        video_path: str,
        start_sec: float = 0.0,
        end_sec: Optional[float] = None,
    ) -> dict:
        """Transcribe with word-level timestamps (faster-whisper DTW).

        Timestamps are returned in the original video's reference frame —
        ``start_sec`` is added to every segment/word ``start`` and ``end``.
        Returns ``{"text": "", "segments": []}`` on any failure / silence.
        """
        empty = {"text": "", "segments": []}
        self._lazy_load_model()
        if self._model == _UNAVAILABLE:
            return empty

        audio_path = self._extract_audio_wav(video_path, start_sec, end_sec)
        if not audio_path or not os.path.isfile(audio_path):
            return empty

        try:
            segs, _info = self._run_transcribe(audio_path, word_timestamps=True)
            if not segs:
                self._n_silent += 1
                return empty

            offset = float(start_sec)
            out_segments = []
            for seg in segs:
                s_start = float(seg.start) + offset
                s_end = float(seg.end) + offset
                s_text = (seg.text or "").strip()
                words_out = []
                for w in (seg.words or []):
                    if w.start is None or w.end is None:
                        continue
                    words_out.append({
                        "word": (w.word or "").strip(),
                        "start": float(w.start) + offset,
                        "end": float(w.end) + offset,
                    })
                out_segments.append({
                    "start": s_start,
                    "end": s_end,
                    "text": s_text,
                    "words": words_out,
                })

            full_text = " ".join(s["text"] for s in out_segments).strip()
            if full_text:
                self._n_transcribed += 1
            return {"text": full_text, "segments": out_segments}
        except Exception as e:
            log.warning(f"transcribe_with_words failed: {e}")
            return empty
        finally:
            self._cleanup(audio_path)

    def stats(self) -> dict:
        """Per-instance counters: how many windows were silent vs transcribed."""
        total = self._n_silent + self._n_transcribed
        return {
            "silent": self._n_silent,
            "transcribed": self._n_transcribed,
            "total": total,
        }


# Process-singleton convenience for the ingest pipeline.

_singleton: Optional[WhisperASR] = None


def _get_singleton() -> WhisperASR:
    global _singleton
    if _singleton is None:
        device = os.environ.get("WHISPER_DEVICE", _resolve_default_device())
        _singleton = WhisperASR(
            model_name=os.environ.get("WHISPER_MODEL", "distil-large-v3"),
            device=device,
            language=os.environ.get("WHISPER_LANGUAGE", "en"),
            compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", _default_compute_type(device)),
            beam_size=int(os.environ.get("WHISPER_BEAM_SIZE", "5")),
            vad_filter=os.environ.get("WHISPER_VAD", "true").lower() in ("true", "1", "yes"),
        )
    return _singleton


def transcribe_segment(video_path: str, start_sec: float, end_sec: float) -> str:
    """Top-level convenience for the ingest pipeline.

    Lazily builds a process-singleton ``WhisperASR`` (model loads once per
    worker process) and transcribes a single ``[start_sec, end_sec]`` window.
    Returns ``""`` on any failure or silence — never raises, so the caller's
    try/except doesn't blanket-skip ASR for the rest of the shots.
    """
    try:
        return _get_singleton().transcribe(video_path, start_sec, end_sec)
    except Exception as exc:
        log.warning("transcribe_segment failed (%s); returning empty", exc)
        return ""


def transcribe_segment_with_words(
    video_path: str, start_sec: float, end_sec: float
) -> dict:
    """Word-level variant. Used by the sentence-boundary chunker."""
    try:
        return _get_singleton().transcribe_with_words(video_path, start_sec, end_sec)
    except Exception as exc:
        log.warning("transcribe_segment_with_words failed (%s); returning empty", exc)
        return {"text": "", "segments": []}
