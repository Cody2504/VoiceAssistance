"""Cut 1 / Task 11.7 — sports_highlights segmenter.

Detects key sports moments by reading the PANN AudioSet tags already cached
in each shot's payload (`audio_tags` from `pipeline/ingest.py`). No new
compute — pure filter + group over indexed data.

Highlight tags
--------------
Any AudioSet label whose lowercase form contains one of the
`HIGHLIGHT_KEYWORDS` triggers the shot. The set covers three signal families:
crowd reaction ("cheer", "applause", "crowd", "shout", "yell"), refereeing
sounds ("whistle", "horn", "siren"), and scoring / impact action ("slam",
"dunk"). The action sounds matter because broadcast sports audio is dominated
by commentary + music, so the play itself (a dunk) is often the only highlight
cue PANN surfaces above `MIN_SCORE` — crowd roar rarely makes the cached
top-k on a commentated clip. Score-weighted to ignore noise: a shot has to
clear `MIN_SCORE` on at least one matching tag to count.

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
    # crowd / reaction
    "cheer", "applause", "crowd", "shout", "yell",
    # referee / stoppage
    "whistle", "horn", "siren",
    # scoring / impact action — broadcast audio is commentary-dominated, so the
    # play itself (a slam dunk) is often the only highlight cue above MIN_SCORE
    "slam", "dunk",
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
    # Twelve Labs `plays` schema aliases.
    want_play_type = "play_type" in field_names
    want_excitement = "excitement_level" in field_names
    want_description = "description" in field_names

    # First pass — flag highlight shots.
    flags: list[tuple[str, float] | None] = [
        _shot_highlight(sh.get("audio_tags", [])) for sh in shots
    ]

    # Second pass — emit ONE segment per highlight shot (a distinct play).
    # We deliberately do NOT merge contiguous highlight shots: each play should
    # be its own scene. The old merge collapsed every adjacent highlight into a
    # single whole-video segment. Shots without highlight audio are skipped, so
    # non-play moments naturally fall into the gaps between plays.
    out: list[dict[str, Any]] = []
    for sh, fl in zip(shots, flags):
        if fl is None:
            continue
        peak_label, peak_score = fl
        event = _normalize_event(peak_label)
        intensity = _intensity(peak_score)
        caption = sh.get("chunk_caption", "")

        meta: dict[str, Any] = {}
        if want_event:
            meta["event_type"] = event
        if want_intensity:
            meta["intensity"] = intensity
        if want_caption:
            meta["caption"] = caption
        # Twelve Labs aliases (`play_type`, `excitement_level`, `description`,
        # `scoring_play`, `key_players`) are LEFT EMPTY so the shared `_enrich`
        # LLM pass derives them PER PLAY from the shot context — caption + ASR
        # commentary + the raw PANN audio tags (carried by `_format_context`).
        # That lets the LLM name the play ("Three point shot" / "Turnover") and
        # judge excitement from the crowd/commentary audio, instead of a coarse
        # audio-score bucket that collapsed everything to one value.
        out.append({"t_start": sh["t_start"], "t_end": sh["t_end"], "metadata": meta})

    return out
