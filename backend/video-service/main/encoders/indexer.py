"""Shot detection + frame extraction helpers.

Consumed by `backend/video-service/main/pipeline/ingest.py`. Exposes:
  - `detect_shots(...)`        — PySceneDetect-based shot boundaries with speech-aware refinement
  - `_get_video_duration(...)` — duration probe
  - `extract_frames(...)`      — uniform-sampled frames within a [start, end] range
"""
import logging
import os
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


def uniform_windows(duration: float, window_sec: float) -> List[Tuple[float, float]]:
    """Split `duration` into fixed-length windows of `window_sec` seconds.

    Used for continuous footage (lecture, ego-centric, single-camera) where
    PySceneDetect collapses the whole video into one shot. The trailing
    partial window is merged into the previous one if shorter than half the
    target — avoids 0.3-second tail windows that confuse downstream tools.
    """
    if duration <= 0:
        return [(0.0, max(0.1, duration))]
    windows: List[Tuple[float, float]] = []
    t = 0.0
    while t < duration - 1e-3:
        end = min(t + window_sec, duration)
        windows.append((float(t), float(end)))
        t = end
    if len(windows) >= 2:
        last_dur = windows[-1][1] - windows[-1][0]
        if last_dur < window_sec / 2.0:
            prev_start = windows[-2][0]
            last_end = windows[-1][1]
            windows = windows[:-2] + [(prev_start, last_end)]
    return windows


def _subdivide_uniform(start: float, end: float, max_shot_s: float) -> List[Tuple[float, float]]:
    """Equal-length subdivision of ``[start, end]`` into pieces ≤ ``max_shot_s``."""
    import math
    length = end - start
    n = max(1, math.ceil(length / max_shot_s))
    step = length / n
    return [(start + i * step, start + (i + 1) * step) for i in range(n)]


def refine_long_shot(
    start: float,
    end: float,
    words: List[dict],
    max_shot_s: float = 10.0,
    min_shot_s: float = 0.75,
    pause_threshold_s: float = 0.4,
) -> List[Tuple[float, float]]:
    """Split ``[start, end]`` at sentence boundaries / long pauses.

    Walks the word list and emits a cut at any of:
      - End-of-sentence punctuation in the word (".", "!", "?")
      - Inter-word pause ≥ ``pause_threshold_s`` after the word

    Then greedily groups boundaries into sub-shots that prefer the latest
    boundary inside ``[current + max_shot_s/2, current + max_shot_s]``,
    relaxes to ``≤ 1.5 × max_shot_s`` if no comfortable boundary exists,
    and falls back to uniform subdivision if no usable boundary exists at
    all (silent shot, lecture cutaway).

    Args:
        start, end: Outer shot bounds (absolute video time).
        words: List of ``{"word", "start", "end"}`` from
            ``WhisperASR.transcribe_with_words``. Times must be in the same
            (absolute video) reference frame as ``start`` / ``end``.
        max_shot_s: Target maximum sub-shot length.
        min_shot_s: Drop boundary candidates that would leave a sub-shot
            shorter than this on either side of the cut.
        pause_threshold_s: Inter-word gap that counts as a cut-worthy pause.

    Returns:
        List of contiguous ``(s, e)`` covering ``[start, end]``. Always
        non-empty.
    """
    import bisect

    length = end - start
    if length <= max_shot_s:
        return [(start, end)]

    in_window = [
        w for w in words
        if w.get("start") is not None and start <= float(w["start"]) < end
    ]
    if not in_window:
        return _subdivide_uniform(start, end, max_shot_s)

    boundaries: List[float] = []
    for i, w in enumerate(in_window):
        wt = (w.get("word") or "").strip()
        ends_sentence = bool(wt) and wt[-1] in ".!?"
        gap_after = (
            i + 1 < len(in_window)
            and (float(in_window[i + 1]["start"]) - float(w["end"])) >= pause_threshold_s
        )
        if ends_sentence or gap_after:
            boundaries.append(float(w["end"]))

    boundaries = [
        b for b in boundaries
        if (b - start) >= min_shot_s and (end - b) >= min_shot_s
    ]
    boundaries.sort()

    if not boundaries:
        return _subdivide_uniform(start, end, max_shot_s)

    cuts: List[float] = [start]
    while end - cuts[-1] > max_shot_s:
        cur = cuts[-1]
        lo, hi = cur + max_shot_s * 0.5, cur + max_shot_s
        lo_idx = bisect.bisect_left(boundaries, lo)
        hi_idx = bisect.bisect_right(boundaries, hi) - 1
        if lo_idx <= hi_idx:
            cuts.append(boundaries[hi_idx])
            continue
        # Relax: accept slight overflow up to 1.5 × max for a clean boundary.
        relax_hi = cur + max_shot_s * 1.5
        relax_idx = bisect.bisect_right(boundaries, relax_hi) - 1
        if relax_idx >= 0 and boundaries[relax_idx] > cur:
            cuts.append(boundaries[relax_idx])
            continue
        # No usable boundary anywhere in range — uniform cut and continue.
        cuts.append(cur + max_shot_s)
    if cuts[-1] < end - 1e-3:
        cuts.append(end)
    return list(zip(cuts[:-1], cuts[1:]))


def _subdivide_with_speech(
    video_path: str,
    start: float,
    end: float,
    max_shot_s: float,
    min_shot_s: float,
    pause_threshold_s: float = 0.4,
) -> List[Tuple[float, float]]:
    """Sentence-boundary subdivision via WhisperASR word timestamps.

    Falls back to ``_subdivide_uniform`` if ASR is unavailable or returns
    no words for this segment.
    """
    try:
        from main.encoders.asr_whisper import transcribe_segment_with_words
    except Exception as exc:
        log.warning(f"refine: cannot import asr_whisper ({exc}); uniform subdivide.")
        return _subdivide_uniform(start, end, max_shot_s)

    out = transcribe_segment_with_words(video_path, start, end)
    words: List[dict] = []
    for seg in out.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            words.append(w)
    return refine_long_shot(start, end, words, max_shot_s, min_shot_s, pause_threshold_s)


def detect_shots(
    video_path: str,
    threshold: float = 27.0,
    max_shot_s: float = 10.0,
    min_shot_s: float = 0.75,
    refine_with_speech: bool = False,
) -> List[Tuple[float, float]]:
    """Detect shot boundaries; enforce ``max_shot_s`` to avoid single-shot videos.

    Static tutorial-style videos often produce no scenedetect cuts at all (one shot
    covering the whole video). That makes corpus retrieval useless: every query hits
    the one giant shot regardless of relevance. We post-process the detector output so
    every shot is no longer than ``max_shot_s`` (subdividing as needed) and no shorter
    than ``min_shot_s`` (merging trailing residuals into the previous shot).

    Args:
        video_path: Path to video file.
        threshold: PySceneDetect ContentDetector threshold (lower = more sensitive).
        max_shot_s: Maximum allowed shot length. Anything longer is split.
            Default 10s.
        min_shot_s: Minimum allowed shot length. Anything shorter is merged into
            the previous shot. Default 0.75s.
        refine_with_speech: When True, long shots are split at sentence
            boundaries / pauses inferred from word-level ASR instead of
            equal-length windows. One extra Whisper pass per long shot.
            Falls back to uniform subdivision for shots without speech.

    Returns:
        List of (start_sec, end_sec) tuples covering ``[0, duration]``.
    """
    try:
        from scenedetect import detect, ContentDetector
        scene_list = detect(video_path, ContentDetector(threshold=threshold))
        shots: List[Tuple[float, float]] = [(s.get_seconds(), e.get_seconds()) for s, e in scene_list]
    except ImportError:
        log.warning("scenedetect not installed; using fixed-window chunking only.")
        shots = []

    duration = _get_video_duration(video_path)
    if not shots:
        shots = [(0.0, duration)]

    # Subdivide any shot longer than max_shot_s.
    subdivided: List[Tuple[float, float]] = []
    for s_, e_ in shots:
        if (e_ - s_) <= max_shot_s:
            subdivided.append((s_, e_))
        elif refine_with_speech:
            subdivided.extend(_subdivide_with_speech(video_path, s_, e_, max_shot_s, min_shot_s))
        else:
            subdivided.extend(_subdivide_uniform(s_, e_, max_shot_s))

    # Merge tiny residuals (e.g. a 67ms trailing shot from scenedetect rounding).
    cleaned: List[Tuple[float, float]] = []
    for s_, e_ in subdivided:
        if cleaned and (e_ - s_) < min_shot_s:
            prev_s, _ = cleaned[-1]
            cleaned[-1] = (prev_s, e_)
        else:
            cleaned.append((s_, e_))

    return cleaned


def _get_video_duration(video_path: str) -> float:
    """Get video duration using available libraries (decord or cv2)."""
    try:
        import decord
        vr = decord.VideoReader(video_path, num_threads=1, ctx=decord.cpu(0))
        return len(vr) / vr.get_avg_fps()
    except Exception:
        pass
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            return frame_count / fps
    except Exception:
        pass
    log.warning("Cannot determine video duration, defaulting to 300s")
    return 300.0


def extract_frames(video_path: str, start_sec: float, end_sec: float, max_frames: int = 8) -> np.ndarray:
    """Extract uniformly sampled frames from a video segment.

    Args:
        video_path: Path to video file.
        start_sec: Start time in seconds.
        end_sec: End time in seconds.
        max_frames: Maximum number of frames to extract.

    Returns:
        Frames as numpy array [N, H, W, 3] (uint8, RGB).
    """
    try:
        import decord
        from decord import VideoReader, cpu

        vr = VideoReader(video_path, num_threads=1, ctx=cpu(0))
        fps = vr.get_avg_fps()

        start_frame = int(start_sec * fps)
        end_frame = min(int(end_sec * fps), len(vr))
        total_frames = end_frame - start_frame

        if total_frames <= 0:
            total_frames = len(vr)
            start_frame = 0
            end_frame = total_frames

        n_frames = min(max_frames, total_frames)
        indices = np.linspace(start_frame, end_frame - 1, n_frames, dtype=int)
        frames = vr.get_batch(indices).asnumpy()  # [N, H, W, 3]
        return frames

    except ImportError:
        log.warning("decord not installed. Returning placeholder frames. pip install decord")
        return np.zeros((max_frames, 224, 224, 3), dtype=np.uint8)


