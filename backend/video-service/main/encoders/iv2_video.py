"""IV2 clip frame-reader — vendored so the video-service has no `jockey` dependency.

Decodes a video into ``[n_clips, frames_per_clip, H, W, 3]`` uint8 clips: each clip
spans ``clip_length_sec`` of wall-clock, sampling ``frames_per_clip`` evenly-spaced
frames center-cropped/resized to ``input_size``. decord-first, OpenCV fallback.
Verbatim from the validated thesis extractor (read_clips), now owned by the service.
"""
from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger(__name__)

# IV2-1b clip-feature defaults (SG-DETR / lighthouse convention: 2-second clips,
# 4 frames/clip, 224px). Keep in sync with the encoder the features feed.
DEFAULT_CLIP_LENGTH_SEC = 2.0
DEFAULT_FRAMES_PER_CLIP = 4
DEFAULT_INPUT_SIZE = 224


def read_clips(
    video_path: str,
    clip_length_sec: float,
    frames_per_clip: int,
    input_size: int,
) -> tuple[np.ndarray, float]:
    """Decode ``video_path`` into ``[n_clips, frames_per_clip, H, W, 3]`` uint8.

    Returns (clips, true_fps).
    """
    try:
        from decord import VideoReader, cpu  # type: ignore
        vr = VideoReader(video_path, ctx=cpu(0))
        fps = float(vr.get_avg_fps()) or 30.0
        n_frames = len(vr)
        get_batch = lambda idxs: vr.get_batch(idxs).asnumpy()  # noqa: E731
        backend = "decord"
    except ImportError:
        get_batch, fps, n_frames = _cv2_reader(video_path)
        backend = "opencv"

    duration = n_frames / fps
    n_clips = max(1, int(duration // clip_length_sec))
    log.info("decode[%s]: %s fps=%.2f frames=%d dur=%.1fs -> %d clips",
             backend, os.path.basename(video_path), fps, n_frames, duration, n_clips)

    clips = np.empty((n_clips, frames_per_clip, input_size, input_size, 3), dtype=np.uint8)
    for c in range(n_clips):
        t0, t1 = c * clip_length_sec, (c + 1) * clip_length_sec
        idxs = np.linspace(t0 * fps, min(t1 * fps, n_frames - 1),
                           frames_per_clip).astype(int).tolist()
        batch = get_batch(idxs)                             # [T, H, W, 3] uint8 RGB
        clips[c] = _resize_center_crop(batch, input_size)
    return clips, fps


def _cv2_reader(video_path: str):
    """OpenCV fallback: returns (get_batch(idxs)->[T,H,W,3] RGB uint8, fps, n_frames)."""
    import cv2  # type: ignore
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video_path!r}")
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    def get_batch(idxs):
        out = []
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
            ok, frame = cap.read()
            if not ok or frame is None:
                if out:
                    out.append(out[-1])
                    continue
                raise RuntimeError(f"OpenCV failed to read frame {i} of {video_path!r}")
            out.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return np.stack(out, axis=0)

    return get_batch, fps, n_frames


def _resize_center_crop(batch: np.ndarray, size: int) -> np.ndarray:
    """Resize shorter side to ``size`` then center-crop to size×size."""
    import cv2  # type: ignore
    out = np.empty((batch.shape[0], size, size, 3), dtype=np.uint8)
    for i, frame in enumerate(batch):
        h, w = frame.shape[:2]
        scale = size / min(h, w)
        rw, rh = max(size, int(round(w * scale))), max(size, int(round(h * scale)))
        r = cv2.resize(frame, (rw, rh), interpolation=cv2.INTER_AREA)
        y0, x0 = (rh - size) // 2, (rw - size) // 2
        out[i] = r[y0:y0 + size, x0:x0 + size]
    return out
