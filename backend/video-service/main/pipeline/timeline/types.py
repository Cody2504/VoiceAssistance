from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TimelineEvent:
    t_start: float
    t_end: float
    label: str
    source: str
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class GeneratedTrack:
    kind: str
    label: str
    events: list[TimelineEvent]


def merge_consecutive(
    spans: list[tuple[float, float, str, float]],
    *,
    source: str,
    gap_tolerance: float = 1.0,
) -> list[TimelineEvent]:
    """Merge consecutive spans that share a label and are adjacent (gap ≤
    gap_tolerance) into single events. `spans` = (t_start, t_end, label, score),
    assumed sorted by t_start. Score of a merged event = max over its spans."""
    events: list[TimelineEvent] = []
    for t0, t1, label, score in spans:
        if (
            events
            and events[-1].label == label
            and t0 <= events[-1].t_end + gap_tolerance
        ):
            events[-1].t_end = max(events[-1].t_end, t1)
            events[-1].score = max(events[-1].score, score)
        else:
            events.append(TimelineEvent(t_start=t0, t_end=t1, label=label, source=source, score=score))
    return events
