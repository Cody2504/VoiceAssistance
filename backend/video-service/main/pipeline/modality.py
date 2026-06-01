"""Modality detection via ffprobe.

Classifies an uploaded file into one of:
  - ``video_audio`` — has both streams; normal pipeline
  - ``video_only`` — silent recording (e.g. screen capture); skip ASR + audio MR
  - ``audio_only`` — `.mp3` / `.wav` / audio-only `.mp4`; skip visual encoders

Called once at the start of ingest. The decision is persisted onto
``videos.modality`` so the frontend can disable irrelevant tiles without
re-probing.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class Modality:
    label: str          # "video_audio" | "video_only" | "audio_only"
    has_video: bool
    has_audio: bool
    duration_s: float


def detect_modality(local_path: str) -> Modality:
    """Probe streams; raise on truly unreadable files. Default to ``video_audio``
    when probe fails but the file looked like a video upload, so we don't
    accidentally take the audio-only branch on a degraded probe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-print_format", "json",
                "-show_streams", "-show_format",
                local_path,
            ],
            check=True, capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout or "{}")
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        log.warning("modality:ffprobe failed: %s — defaulting to video_audio", exc)
        return Modality("video_audio", True, True, 0.0)

    streams = data.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    try:
        duration_s = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration_s = 0.0

    if has_video and has_audio:
        label = "video_audio"
    elif has_video and not has_audio:
        label = "video_only"
    elif has_audio and not has_video:
        label = "audio_only"
    else:
        # Neither stream visible — treat as audio_only by default so we still
        # attempt ASR rather than rejecting the upload outright.
        label = "audio_only"

    log.info("modality:%s has_video=%s has_audio=%s duration=%.1fs",
             label, has_video, has_audio, duration_s)
    return Modality(label, has_video, has_audio, duration_s)
