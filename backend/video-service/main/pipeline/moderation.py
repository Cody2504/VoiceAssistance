"""Content-moderation verdict — the guardrail's decision step.

Pure function over the per-segment scores already on IngestArtifacts (nsfw +
violence + toxic). No model loading, no torch — so it is cheap and unit-testable.
Called at the end of ingest, before the Qdrant upsert: a flagged video is
quarantined (status='flagged', never indexed). See
docs/superpowers/specs/2026-06-27-content-moderation-guardrail-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_CATEGORIES = ("nsfw", "violence", "toxic")


@dataclass
class ModerationVerdict:
    flagged: bool
    labels: list[str]
    nsfw_max: float
    violence_max: float
    toxic_max: float
    detail: list[dict] = field(default_factory=list)  # flagged segments: t_start, t_end, scores

    def as_dict(self) -> dict:
        return {
            "flagged": self.flagged,
            "labels": self.labels,
            "nsfw_max": self.nsfw_max,
            "violence_max": self.violence_max,
            "toxic_max": self.toxic_max,
            "detail": self.detail,
        }


def _at(scores, i: int) -> float:
    """Defensive per-segment lookup — missing/short arrays read as 0.0."""
    if scores is None or i >= len(scores):
        return 0.0
    try:
        return float(scores[i])
    except (TypeError, ValueError):
        return 0.0


def evaluate_moderation(artifacts, settings) -> ModerationVerdict:
    """Decide whether a video should be quarantined.

    A category trips when at least ``moderation_min_flagged_segments`` segments
    exceed its threshold; the video is flagged if any category trips.
    """
    segments = artifacts.segments or []
    thresholds = {
        "nsfw": settings.moderation_nsfw_threshold,
        "violence": settings.moderation_violence_threshold,
        "toxic": settings.moderation_toxic_threshold,
    }
    scores = {
        "nsfw": artifacts.nsfw_scores,
        "violence": getattr(artifacts, "violence_scores", None),
        "toxic": artifacts.toxic_scores,
    }
    min_flagged = max(1, int(settings.moderation_min_flagged_segments))

    maxes = {c: 0.0 for c in _CATEGORIES}
    exceed_counts = {c: 0 for c in _CATEGORIES}
    detail: list[dict] = []
    for i, (t0, t1) in enumerate(segments):
        row = {c: _at(scores[c], i) for c in _CATEGORIES}
        tripped_here = False
        for c in _CATEGORIES:
            maxes[c] = max(maxes[c], row[c])
            if row[c] >= thresholds[c]:
                exceed_counts[c] += 1
                tripped_here = True
        if tripped_here:
            detail.append({
                "idx": i,
                "t_start": float(t0),
                "t_end": float(t1),
                "nsfw_score": row["nsfw"],
                "violence_score": row["violence"],
                "toxic_score": row["toxic"],
            })

    labels = [c for c in _CATEGORIES if exceed_counts[c] >= min_flagged]
    return ModerationVerdict(
        flagged=bool(labels),
        labels=labels,
        nsfw_max=maxes["nsfw"],
        violence_max=maxes["violence"],
        toxic_max=maxes["toxic"],
        detail=detail,
    )
