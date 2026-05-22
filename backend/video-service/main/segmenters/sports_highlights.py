"""Cut 1 / Task 11.7 — sports_highlights segmenter.

Detects key sports moments by reading the PANN AudioSet tags already cached
in each shot's payload (`audio_tags` from `pipeline/ingest.py`). No new
compute — pure filter + group over indexed data.

Highlight tags
--------------
Any AudioSet label whose lowercase form contains one of the
`HIGHLIGHT_KEYWORDS` triggers the shot. The default set covers crowd reaction
("cheer", "applause", "crowd", "shout") and refereeing sounds ("whistle",
"horn"). Score-weighted to ignore noise: a shot has to clear `MIN_SCORE` on
at least one matching tag to count.

Grouping
--------
Contiguous highlight shots merge into one segment. The dominant tag (max
score) becomes `event_type`; intensity is bucketed from that score.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition

from .qdrant_io import read_shots

HIGHLIGHT_KEYWORDS = (
    "cheer", "applause", "crowd", "shout", "whistle", "horn", "siren", "yell",
)
MIN_SCORE = 0.15
# Intensity bucketing from peak score for the segment.
INTENSITY_BUCKETS = (("low", 0.0), ("medium", 0.35), ("high", 0.6))


def _shot_highlight(audio_tags: list[dict[str, Any]]) -> tuple[str, float] | None:
    """Pick the highest-scoring highlight tag in this shot's tag list.

    Returns (label, score) or None if no tag matches the highlight vocabulary
    above MIN_SCORE.
    """
    best: tuple[str, float] | None = None
    for t in audio_tags or []:
        label = str(t.get("label", "")).lower()
        score = float(t.get("score", 0.0))
        if score < MIN_SCORE:
            continue
        if any(kw in label for kw in HIGHLIGHT_KEYWORDS):
            if best is None or score > best[1]:
                best = (label, score)
    return best


def _intensity(score: float) -> str:
    out = "low"
    for label, th in INTENSITY_BUCKETS:
        if score >= th:
            out = label
    return out


def _normalize_event(label: str) -> str:
    """Map raw AudioSet label to a short event_type token."""
    label = label.lower()
    for kw in HIGHLIGHT_KEYWORDS:
        if kw in label:
            return kw
    return label


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    if not shots:
        return []

    field_names = {f.name for f in definition.fields}
    want_event = "event_type" in field_names
    want_intensity = "intensity" in field_names
    want_caption = "caption" in field_names

    # First pass — flag highlight shots.
    flags: list[tuple[str, float] | None] = [
        _shot_highlight(sh.get("audio_tags", [])) for sh in shots
    ]

    # Second pass — group contiguous flagged shots.
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(shots):
        if flags[i] is None:
            i += 1
            continue
        j = i
        peak_label, peak_score = flags[i]
        while j + 1 < len(shots) and flags[j + 1] is not None:
            lbl, sc = flags[j + 1]  # type: ignore[misc]
            if sc > peak_score:
                peak_label, peak_score = lbl, sc
            j += 1

        meta: dict[str, Any] = {}
        if want_event:
            meta["event_type"] = _normalize_event(peak_label)
        if want_intensity:
            meta["intensity"] = _intensity(peak_score)
        if want_caption:
            caps = [sh.get("chunk_caption", "") for sh in shots[i : j + 1] if sh.get("chunk_caption")]
            meta["caption"] = caps[0] if caps else ""

        out.append({"t_start": shots[i]["t_start"], "t_end": shots[j]["t_end"], "metadata": meta})
        i = j + 1

    return out
