"""Cut 2 / Task 11.9 — speaker_diarization.

Runs pyannote/speaker-diarization-3.1 on the video's audio track and emits one
segment per speaker turn. Requires the pyannote.audio library + an HF token
with the gated-model license accepted on huggingface.co.

Deployment story
----------------
Under the current architecture, video-service runs on the rented vast.ai 4090
box. The GPU Dockerfile installs pyannote there, and the model loads into
VRAM. On a developer laptop without pyannote installed the import-guard below
returns an empty track so the rest of the playground keeps working.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition
from main.models.video import Video

from .video_io import fetch_video, stream_url

log = logging.getLogger(__name__)


def _format_turns(turns: list[dict[str, Any]], definition: SegmentDefinition) -> list[dict[str, Any]]:
    field_names = {f.name for f in definition.fields}
    out: list[dict[str, Any]] = []
    for turn in turns:
        meta: dict[str, Any] = {}
        if "speaker_label" in field_names:
            meta["speaker_label"] = turn.get("speaker", "")
        if "duration_s" in field_names:
            meta["duration_s"] = round(float(turn["t_end"]) - float(turn["t_start"]), 2)
        out.append({"t_start": float(turn["t_start"]), "t_end": float(turn["t_end"]), "metadata": meta})
    return out


def _run_pyannote(video: Video) -> list[dict[str, Any]] | None:
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except Exception:  # noqa: BLE001
        log.warning(
            "speaker_diarization:pyannote not installed in this image — empty track. "
            "Build with Dockerfile.gpu for the vast.ai deployment.",
        )
        return None

    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        log.warning("speaker_diarization:HF_TOKEN not set — empty track")
        return None

    url = stream_url(video, public=False)
    import urllib.request

    fd, video_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, video_path)
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-ar", "16000", "-ac", "1",
                 "-f", "wav", "-loglevel", "quiet", wav_path],
                check=True,
            )
            pipe = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", use_auth_token=hf_token,
            )
            try:
                import torch
                if torch.cuda.is_available():
                    pipe.to(torch.device("cuda"))
            except Exception:  # noqa: BLE001
                pass
            diarization = pipe(wav_path)
        finally:
            try: os.remove(wav_path)
            except OSError: pass
    finally:
        try: os.remove(video_path)
        except OSError: pass

    return [
        {"t_start": float(turn.start), "t_end": float(turn.end), "speaker": str(speaker)}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    video = fetch_video(video_id)
    if video is None:
        return []
    turns = _run_pyannote(video)
    if turns is None:
        return []
    return _format_turns(turns, definition)
