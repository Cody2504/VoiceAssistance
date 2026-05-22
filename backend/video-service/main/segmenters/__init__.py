"""Segmenter registry for the Segment Builder.

Each segmenter is a callable that takes (video_id, SegmentDefinition) and
returns a list of `{t_start, t_end, metadata}` dicts. The registry decouples
the HTTP endpoint from the per-preset implementation — adding a new preset
means dropping a new module in this package and registering it below.

Cut tags
--------
Cut 1 (frozen data + LLM): shot_detection, topic_changes, sports_highlights,
write_my_own.

Cut 2 (frozen data + GPU model via toggle, with LLM-only editorial):
speaker_diarization, ocr, editorial_segment.

Cut 3 (GPU model via toggle): person_of_focus.

The toggle in `main.inference.config` decides whether Cut 2/3 segmenters
run their local fallback (mostly stubbed to empty for heavy deps) or call
the remote inference-service.
"""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from main.api.segments_types import SegmentDefinition

from . import (
    editorial_segment,
    ocr,
    person_of_focus,
    shot_detection,
    speaker_diarization,
    sports_highlights,
    topic_changes,
    write_my_own,
)

SegmenterFn = Callable[[UUID, "SegmentDefinition"], list[dict[str, Any]]]

REGISTRY: dict[str, SegmenterFn] = {
    # Cut 1
    "shot_detection": shot_detection.segment,
    "topic_changes": topic_changes.segment,
    "sports_highlights": sports_highlights.segment,
    "write_my_own": write_my_own.segment,
    # Cut 2
    "speaker_diarization": speaker_diarization.segment,
    "ocr": ocr.segment,
    "editorial_segment": editorial_segment.segment,
    # Cut 3
    "person_of_focus": person_of_focus.segment,
}


def run_definition(video_id: UUID, definition: "SegmentDefinition") -> list[dict[str, Any]]:
    fn = REGISTRY.get(definition.id)
    if fn is None:
        return []
    raw = fn(video_id, definition)
    return _apply_definition_time_ranges(raw, definition.time_ranges)


def is_implemented(preset_id: str) -> bool:
    return preset_id in REGISTRY


def _parse_time_ranges(specs: list[str] | None) -> list[tuple[float, float]]:
    """Parse `["0-10", "30-45"]` → `[(0,10), (30,45)]`. Skips malformed entries."""
    if not specs:
        return []
    out: list[tuple[float, float]] = []
    for spec in specs:
        if not isinstance(spec, str):
            continue
        for piece in spec.split(","):
            piece = piece.strip()
            if not piece or "-" not in piece:
                continue
            try:
                a, b = piece.split("-", 1)
                start = float(a.strip())
                end = float(b.strip())
                if end > start:
                    out.append((start, end))
            except ValueError:
                continue
    return out


def _apply_definition_time_ranges(
    segs: list[dict[str, Any]], specs: list[str] | None
) -> list[dict[str, Any]]:
    ranges = _parse_time_ranges(specs)
    if not ranges:
        return segs
    keep = []
    for s in segs:
        ts = s.get("t_start")
        te = s.get("t_end")
        if ts is None or te is None:
            continue
        for r_start, r_end in ranges:
            if ts < r_end and te > r_start:
                keep.append(s)
                break
    return keep
