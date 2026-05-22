"""Cut 1 / Task 11.5 — shot_detection segmenter.

Reads the per-shot boundaries already written to Qdrant by the indexing
pipeline (PySceneDetect output, no new compute). The user's `fields` schema
drives what metadata is surfaced per segment — known fields are filled, the
rest pass through empty.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition

from .qdrant_io import read_shots


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
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
        out.append({"t_start": sh["t_start"], "t_end": sh["t_end"], "metadata": meta})
    return out
