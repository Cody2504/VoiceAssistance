"""Tool: cut + concatenate clips into a new video via ffmpeg (video-service /edit).

`segments` may be explicit {t_start, t_end} ranges OR {"description": "..."} moments
to locate. Descriptions are resolved to spans via the same /when grounding the
ground_video tool uses, so the router can call this directly from a request like
"combine the dunk and the celebration" WITHOUT already knowing the timestamps.
"""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


async def _resolve_span(video_id: str, description: str) -> dict | None:
    """Ground a natural-language moment to a single {t_start, t_end} span."""
    resp = await post_request(
        "video-service", f"/api/v1/videos/{video_id}/when", json={"query": description}
    )
    spans = [e for e in (_unwrap(resp).get("events") or []) if "t_start" in e and "t_end" in e]
    if not spans:
        return None
    best = max(spans, key=lambda e: float(e.get("score", 0.0)))
    return {"t_start": best["t_start"], "t_end": best["t_end"]}


@tool
async def combine_clips(video_id: str, segments: list[dict]) -> dict[str, Any]:
    """Cut and concatenate moments from ONE source video into a NEW edited video.

    Use this whenever the user wants to PRODUCE or EDIT a video by joining moments —
    "cut", "combine", "stitch", "merge", "make a clip out of …". Each item in
    `segments` is EITHER an explicit range `{"t_start": <sec>, "t_end": <sec>}` OR a
    moment to locate `{"description": "the dunk"}`. You do NOT need to know the
    timestamps first — pass descriptions and they are resolved to spans automatically.
    """
    clips: list[dict] = []
    for seg in segments or []:
        if seg.get("t_start") is not None and seg.get("t_end") is not None:
            clips.append({"t_start": seg["t_start"], "t_end": seg["t_end"]})
        elif seg.get("description"):
            span = await _resolve_span(video_id, seg["description"])
            if span:
                clips.append(span)
    if not clips:
        return {"error": "No segments could be resolved to time ranges.", "video_id": video_id}
    resp = await post_request(
        "video-service", f"/api/v1/videos/{video_id}/edit", json={"clips": clips}
    )
    return _unwrap(resp)
