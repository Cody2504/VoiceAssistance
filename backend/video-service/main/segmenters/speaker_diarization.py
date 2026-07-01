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
from main.settings import get_settings
from main.storage.minio import download_to_path

from .qdrant_io import read_shots
from .video_io import fetch_video

log = logging.getLogger(__name__)


def _assign_transcripts(
    turns: list[dict[str, Any]], shots: list[dict[str, Any]], max_chars: int = 400
) -> dict[int, str]:
    """Assign each ASR shot to the ONE turn it overlaps most, then build that turn's
    transcript from its owned shots (time-ordered, dedup). Assigning each shot to a
    single owner (instead of copying a coarse shot's full text onto every turn it
    touches) is what removes the duplicated `transcript_summary` across turns/speakers.
    Returns {turn_index: transcript}."""
    owned: dict[int, list[tuple[float, str]]] = {i: [] for i in range(len(turns))}
    for sh in shots:
        text = (sh.get("asr_text") or "").strip()
        if not text:
            continue
        ts = float(sh.get("t_start", 0.0))
        te = float(sh.get("t_end", 0.0))
        best_i: int | None = None
        best_ov = 0.0
        for i, tn in enumerate(turns):
            ov = min(te, float(tn["t_end"])) - max(ts, float(tn["t_start"]))
            if ov > best_ov:
                best_ov, best_i = ov, i
        if best_i is not None and best_ov > 0:
            owned[best_i].append((ts, text))

    summaries: dict[int, str] = {}
    for i, items in owned.items():
        items.sort(key=lambda x: x[0])
        seen: set[str] = set()
        parts: list[str] = []
        for _ts, text in items:
            if text not in seen:
                seen.add(text)
                parts.append(text)
        joined = " ".join(parts).strip()
        summaries[i] = joined[:max_chars] + ("…" if len(joined) > max_chars else "")
    return summaries


def _format_turns(
    turns: list[dict[str, Any]],
    definition: SegmentDefinition,
    shots: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    field_names = {f.name for f in definition.fields}
    # Twelve Labs `speakers` schema: surface what was said in each turn from the
    # cached ASR shots — each shot assigned to a single owning turn (no duplication).
    # `speaking_context` enum (interview / narration / …) needs an LLM classification
    # we don't run yet — left empty.
    summaries: dict[int, str] = {}
    if "transcript_summary" in field_names and shots:
        summaries = _assign_transcripts(turns, shots)
    out: list[dict[str, Any]] = []
    for i, turn in enumerate(turns):
        t_start = float(turn["t_start"])
        t_end = float(turn["t_end"])
        meta: dict[str, Any] = {}
        if "speaker_label" in field_names:
            meta["speaker_label"] = turn.get("speaker", "")
        if "duration_s" in field_names:
            meta["duration_s"] = round(t_end - t_start, 2)
        if "transcript_summary" in field_names and shots:
            meta["transcript_summary"] = summaries.get(i, "")
        out.append({"t_start": t_start, "t_end": t_end, "metadata": meta})
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

    fd, video_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        s = get_settings()
        download_to_path(s.minio_bucket_videos, video.minio_key, video_path)
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
    # Clean raw pyannote output before formatting: merge adjacent same-speaker
    # turns + drop micro-turns (normalize_turns), resolve overlapped-speech to the
    # dominant speaker, then re-merge. Without this the raw itertracks output has
    # overlapping turns and sub-second fragments.
    from main.encoders.diarizer import normalize_turns, resolve_speaker_overlaps
    turns = normalize_turns(turns)
    turns = resolve_speaker_overlaps(turns)
    turns = normalize_turns(turns)
    if not turns:
        return []
    # Pull cached shots only if we'll need ASR for `transcript_summary` —
    # avoids a Qdrant round-trip for the minimal schema.
    field_names = {f.name for f in definition.fields}
    shots = read_shots(video_id, with_vectors=False) if "transcript_summary" in field_names else []
    return _format_turns(turns, definition, shots=shots)
