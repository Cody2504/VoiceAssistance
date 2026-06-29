"""Phase-2 vision-refine for the holistic Segment Builder.

After the holistic core picks segments (boundaries + text-derived fields), the
*visual* presets (shot_detection, person_of_focus, ocr) run this pass: sample a
few frames inside each segment and ask the VLM (qwen3-vl) to fill ONLY the
visual fields (camera angle, person appearance, on-screen text, position) from
the pixels — overwriting the text-approximated values. Gated by
`settings.segment_vision_refine`. Best-effort: any failure keeps the
text-derived segments unchanged. See
docs/superpowers/specs/2026-06-26-holistic-segmenter-design.md (§5).

Heavy deps (the VLM client, ffmpeg frame extraction, MinIO download) are reached
through the module-level seams `_refine_one`, `_extract_segment_frames`,
`_fetch_video`, `_download_video` so they can be lazily imported and unit-tested
with fakes.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition
from main.settings import get_settings

from ._holistic import _build_schema_prompt, _validate_metadata

log = logging.getLogger(__name__)


# lazily-imported seams (patched in tests)
def _fetch_video(video_id: UUID):
    from main.segmenters.video_io import fetch_video

    return fetch_video(video_id)


def _download_video(bucket: str, key: str, dest: str) -> None:
    from main.storage.minio import download_to_path

    download_to_path(bucket, key, dest)


def _extract_segment_frames(path: str, t_start: float, t_end: float, n: int):
    from main.encoders.indexer import extract_frames

    return extract_frames(path, t_start, t_end, max_frames=n)


def _refine_one(api_key: str, model: str, frames, schema_prompt: str, guidance: str) -> dict | None:
    """One VLM call over a segment's frames → JSON of the visual fields. Returns
    None on any failure. The only network seam — tests patch this."""
    try:
        from main.encoders.video_qa import _frames_to_base64_images
        from openai import OpenAI

        images = _frames_to_base64_images(frames, max_images=8)
        if not images:
            return None
        prompt = (
            "You are shown frames sampled from ONE segment of a video. "
            f"{guidance}\n"
            "Reply with ONLY a JSON object containing exactly these fields "
            "(respect enum constraints):\n"
            f"{schema_prompt}"
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for b64 in images:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=400,
            temperature=0.0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        lo, hi = raw.find("{"), raw.rfind("}")
        if lo == -1 or hi <= lo:
            return None
        return json.loads(raw[lo : hi + 1])
    except Exception as exc:  # noqa: BLE001
        log.warning("vision_refine:_refine_one failed: %s", exc)
        return None


def _merge(seg: dict[str, Any], refined: dict | None, refine_def: SegmentDefinition) -> dict[str, Any]:
    """Overwrite only the (validated) visual fields onto the segment's metadata."""
    if not refined:
        return seg
    fields = _validate_metadata(refined, refine_def)
    if not fields:
        return seg
    return {**seg, "metadata": {**seg.get("metadata", {}), **fields}}


def vision_refine(
    video_id: UUID,
    definition: SegmentDefinition,
    segments: list[dict[str, Any]],
    *,
    vision_fields: list[str],
    guidance: str,
) -> list[dict[str, Any]]:
    """Overwrite the `vision_fields` of each segment from sampled frames via the
    VLM. Best-effort: returns the input unchanged on no segments / no matching
    fields / no API key / no video / any I/O failure."""
    if not segments:
        return segments
    want = set(vision_fields)
    fields = [f for f in definition.fields if f.name in want]
    if not fields:
        return segments

    s = get_settings()
    api_key = (s.openrouter_api_key or "").strip()
    if not api_key:
        return segments

    video = _fetch_video(video_id)
    if video is None:
        return segments

    refine_def = definition.model_copy(update={"fields": fields})
    schema_prompt = _build_schema_prompt(refine_def)
    model = s.segment_vision_model
    n_frames = s.segment_vision_frames

    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        _download_video(s.minio_bucket_videos, video.minio_key, path)

        def _do(seg: dict[str, Any]) -> dict[str, Any]:
            try:
                frames = _extract_segment_frames(path, seg["t_start"], seg["t_end"], n_frames)
            except Exception as exc:  # noqa: BLE001
                log.warning("vision_refine: frame extract failed: %s", exc)
                return seg
            refined = _refine_one(api_key, model, frames, schema_prompt, guidance)
            return _merge(seg, refined, refine_def)

        with ThreadPoolExecutor(max_workers=8) as pool:
            return list(pool.map(_do, segments))
    except Exception as exc:  # noqa: BLE001
        log.warning("vision_refine failed: %s — keeping text-derived segments", exc)
        return segments
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
