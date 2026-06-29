"""Cut 1 / Task 11.5 — shot_detection segmenter.

Reads the per-shot boundaries already written to Qdrant by the indexing
pipeline (PySceneDetect output, no new compute). The user's `fields` schema
drives what metadata is surfaced per segment — known fields are filled, the
rest pass through empty.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition, SegmentField

from ._holistic import holistic_segments
from .qdrant_io import read_shots


def _legacy(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    field_names = {f.name for f in definition.fields}
    out: list[dict[str, Any]] = []
    for sh in shots:
        meta: dict[str, Any] = {}
        if "shot_idx" in field_names:
            meta["shot_idx"] = sh["idx"]
        if "asr_text" in field_names:
            meta["asr_text"] = sh["asr_text"]
        if "ocr_text" in field_names:
            meta["ocr_text"] = sh["ocr_text"]
        if "chunk_caption" in field_names:
            meta["chunk_caption"] = sh["chunk_caption"]
        # Twelve Labs `shot_changes` schema: surface the per-shot caption as
        # `description`. `angle_type` / `shot_type` enums require a vision pass
        # we don't run at index time — left empty for now.
        if "description" in field_names:
            meta["description"] = (sh.get("chunk_caption") or "").strip()
        out.append({"t_start": sh["t_start"], "t_end": sh["t_end"], "metadata": meta})
    return out


_ANGLES = ["wide", "medium", "close_up", "extreme_close_up", "overhead", "aerial"]
_SHOT_TYPES = ["clean", "dirty_single", "over_the_shoulder", "point_of_view", "insert", "master"]
_DEFAULT_FIELDS = [
    SegmentField(name="angle_type", type="string", enum=_ANGLES),
    SegmentField(name="shot_type", type="string", enum=_SHOT_TYPES),
    SegmentField(name="description", description="Brief description of the shot content"),
]


def segment(video_id, definition):
    return holistic_segments(
        video_id, definition,
        guidance=(
            "a hard cut or SIGNIFICANT change in camera angle / shot type occurs; "
            "MERGE consecutive shots that share the same angle and framing into one segment"
        ),
        target_hint="One segment per distinct camera setup",
        primary_signal="caption",
        default_fields=_DEFAULT_FIELDS,
        fallback=_legacy,
        vision_fields=["angle_type", "shot_type"],
        vision_guidance="Determine the camera angle_type and shot_type from the framing in these frames.",
    )
