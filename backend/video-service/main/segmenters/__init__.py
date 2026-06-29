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
    _enrich,
    editorial_segment,
    ocr,
    person_of_focus,
    shot_detection,
    speaker_diarization,
    sports_highlights,
    topic_changes,
    write_my_own,
)
from .qdrant_io import read_shots

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

# Twelve Labs default-builder ids intentionally NOT aliased to our
# specialised segmenters — they fall through to `write_my_own`'s ~60s
# LLM-per-window rollup so users get the Pegasus-style granular behavior
# (e.g. ~5 segments on a 2-3 min clip with per-window metadata) rather
# than 1-2 collapsed segments from our visual-similarity boundary logic.
# If you want specialised dispatch for a TL id, add it explicitly above.

# Presets that fill their fields inside the holistic core call — they must NOT
# be re-run through the post-hoc `_enrich` pass (it would waste a call and could
# overwrite the core's values). Non-core presets that still need enrichment
# (currently `speaker_diarization`) are deliberately absent from this set.
_CORE_PRESETS = {
    "topic_changes", "editorial_segment", "shot_detection",
    "ocr", "person_of_focus", "sports_highlights",
}


def run_definition(video_id: UUID, definition: "SegmentDefinition") -> list[dict[str, Any]]:
    # Built-in presets dispatch to their specialised segmenter; any other (custom)
    # id falls back to the generic LLM rollup (`write_my_own`), which is driven
    # entirely by the definition's description + fields/enums. This lets a user
    # author arbitrary definitions (e.g. "scoring_plays", "camera_cut") and get
    # structured segments back, instead of an empty track.
    fn = REGISTRY.get(definition.id, write_my_own.segment)
    raw = fn(video_id, definition)
    # LLM enrichment: fill any `definition.fields` the segmenter didn't natively
    # populate (Twelve Labs schema parity). Skipped for `write_my_own` which
    # already does its own LLM call per segment; skipped if no API key set.
    if (
        definition.id != "write_my_own"
        and definition.id not in _CORE_PRESETS
        and raw
        and definition.fields
    ):
        shots = read_shots(video_id, with_vectors=False)
        raw = _enrich.enrich_segments(raw, definition, shots)
    return _apply_definition_time_ranges(raw, definition.time_ranges)


def is_implemented(preset_id: str) -> bool:
    # Every definition is now handled: known presets by their segmenter, custom
    # ids by the generic `write_my_own` fallback in run_definition().
    return True


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
