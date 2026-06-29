"""Cut 3 — person_of_focus (holistic, caption-driven).

Emits one segment per change in the primary person of focus, with TwelveLabs-
parity fields (person / activity / screen_position / speaking). Driven by the
holistic core over per-shot captions + speech; the old InsightFace face-cluster
path was removed (never installed in the image and produced anonymous person_N
clusters, not this schema). Phase-2 vision-refine fills person/position/speaking
from frames. See docs/superpowers/specs/2026-06-26-holistic-segmenter-design.md.
"""
from __future__ import annotations

from uuid import UUID

from main.api.segments_types import SegmentDefinition, SegmentField

from ._holistic import holistic_segments

_POSITIONS = ["center", "left", "right", "background"]
_DEFAULT_FIELDS = [
    SegmentField(name="person", description="Description of the person (appearance, role, name if known)"),
    SegmentField(name="activity", description="What the person is doing"),
    SegmentField(name="screen_position", type="string", enum=_POSITIONS),
    SegmentField(name="speaking", type="boolean", description="Whether the person is speaking"),
]


def _empty(video_id: UUID, definition: SegmentDefinition) -> list:
    return []


def segment(video_id, definition):
    return holistic_segments(
        video_id, definition,
        guidance="the primary PERSON of focus changes",
        target_hint="One segment per person-of-focus change",
        primary_signal="caption",
        default_fields=_DEFAULT_FIELDS,
        fallback=_empty,
        vision_fields=["person", "screen_position", "speaking"],
        vision_guidance=(
            "Describe the primary person of focus (appearance, team/jersey number, and name if "
            "recognizable), their screen_position, and whether they appear to be speaking."
        ),
    )
