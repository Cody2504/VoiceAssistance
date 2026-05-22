"""Pydantic schemas shared between the HTTP layer and segmenter modules.

Lives outside `segments.py` so segmenter modules can import the types without
pulling in FastAPI route handlers (avoids circular imports).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SegmentField(BaseModel):
    name: str
    type: str = "string"
    description: str | None = None
    enum: list[str] | None = None


class SegmentDefinition(BaseModel):
    id: str
    description: str
    fields: list[SegmentField] = Field(default_factory=list)
    time_ranges: list[str] | None = None
    # Optional base64 data: URL of an image attached to the description.
    # Currently accepted at the API boundary so the frontend round-trips
    # cleanly; surfaced to segmenters that opt in (e.g. write_my_own can
    # forward it to the VLM as a visual reference).
    image_attachment: str | None = None


class SegmentRunRequest(BaseModel):
    definitions: list[SegmentDefinition]
    start_s: float | None = None
    end_s: float | None = None
    min_duration_s: float | None = None
    max_duration_s: float | None = None
