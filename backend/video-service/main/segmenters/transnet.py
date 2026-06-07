"""TransNetV2 shot detection — vendored pure-pytorch model (no TensorFlow at runtime).

Selected via ``settings.shot_detector == "transnet"``; ``pipeline/ingest.py`` falls
back to PySceneDetect on any error (missing weights, decode failure), so ingest is
never blocked on this.

Weights: a pytorch state-dict (``transnet_weights``) converted ONCE from the TF
release via the upstream ``convert_weights.py`` (needs TensorFlow at conversion
time only). Until that file is staged, ``detect_shots_transnet`` raises and ingest
uses PySceneDetect.

Inference replicates the upstream sliding window: pad 25 frames each side, run
100-frame windows at stride 50, keep the middle 50 cut-probabilities per window.
"""
from __future__ import annotations

import logging
import subprocess
from typing import List, Tuple

import numpy as np

log = logging.getLogger(__name__)

_MODEL = None

# TransNetV2 fixed input geometry.
_W, _H = 48, 27


def _load_model(weights: str, device: str):
    global _MODEL
    if _MODEL is None:
        import torch
        from main.vendor.transnetv2_pytorch import TransNetV2
        model = TransNetV2()
        sd = torch.load(weights, map_location="cpu", weights_only=True)
        model.load_state_dict(sd)
        _MODEL = model.to(device).eval()
    return _MODEL


def _read_frames(video_path: str) -> Tuple[np.ndarray, float]:
    """Decode the whole video to ``[N, 27, 48, 3]`` uint8 RGB + return fps."""
    import json
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=avg_frame_rate", "-of", "json", video_path],
        capture_output=True, text=True, check=True,
    )
    rate = json.loads(probe.stdout)["streams"][0]["avg_frame_rate"]
    num, den = (rate.split("/") + ["1"])[:2]
    fps = (float(num) / float(den)) if float(den) else 25.0

    raw = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vf", f"scale={_W}:{_H}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-loglevel", "quiet", "pipe:1"],
        capture_output=True, check=True,
    ).stdout
    arr = np.frombuffer(raw, np.uint8)
    n = arr.size // (_H * _W * 3)
    return arr[: n * _H * _W * 3].reshape(n, _H, _W, 3), fps


def _predict_cut_probs(model, frames: np.ndarray, device: str) -> np.ndarray:
    """Per-frame cut probability over the whole video (upstream windowing)."""
    import torch
    n = len(frames)
    end_pad = 25 + (50 - (n % 50) if n % 50 else 0)
    padded = np.concatenate(
        [frames[:1]] * 25 + [frames] + [frames[-1:]] * end_pad, axis=0
    )
    probs: List[np.ndarray] = []
    ptr = 0
    with torch.no_grad():
        while ptr + 100 <= len(padded):
            window = torch.from_numpy(padded[ptr:ptr + 100][None]).to(device)  # [1,100,27,48,3]
            single, _ = model(window)
            single = torch.sigmoid(single)[0, 25:75, 0].cpu().numpy()
            probs.append(single)
            ptr += 50
    return np.concatenate(probs)[:n] if probs else np.zeros(n, dtype=np.float32)


def _predictions_to_scenes(predictions: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Upstream helper: cut-prob array -> contiguous [start_frame, end_frame] scenes."""
    p = (predictions > threshold).astype(np.uint8)
    scenes, t, t_prev, start = [], -1, 0, 0
    for i, t in enumerate(p):
        if t_prev == 1 and t == 0:
            start = i
        if t_prev == 0 and t == 1 and i != 0:
            scenes.append([start, i])
        t_prev = t
    if t == 0:
        scenes.append([start, i])
    if not scenes:
        return np.array([[0, len(p) - 1]], dtype=np.int32)
    return np.array(scenes, dtype=np.int32)


def detect_shots_transnet(
    video_path: str,
    weights: str,
    device: str = "cpu",
    threshold: float = 0.5,
) -> List[Tuple[float, float]]:
    """Return ``[(start_sec, end_sec), ...]`` shot boundaries via TransNetV2."""
    model = _load_model(weights, device)
    frames, fps = _read_frames(video_path)
    if len(frames) == 0:
        raise RuntimeError(f"TransNetV2: decoded 0 frames from {video_path!r}")
    cut_probs = _predict_cut_probs(model, frames, device)
    scenes = _predictions_to_scenes(cut_probs, threshold)
    fps = fps or 25.0
    shots = [(float(s) / fps, float(e + 1) / fps) for s, e in scenes]
    log.info("transnet: %s -> %d shots (fps=%.2f, frames=%d)",
             video_path.rsplit("/", 1)[-1], len(shots), fps, len(frames))
    return shots
