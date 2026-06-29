"""Tool: 'when does X happen' via the multi-stream /when fan-out (video-service).

Repointed from /ground to /when for the conversational agent (2026-06-13 demo):
/when fuses the trained SG-DETR grounding stream with vlm_actions, segment
captions and OCR/audio events, yielding tighter action-level windows than the
raw grounding head alone. The bare /ground endpoint is reserved for the
Playground Ground / Analyze (sports-highlight) surface, which calls it directly
via the frontend api client — NOT through this agent tool.

The /when `events` are reshaped into a compact `moments` list — the shape the
chat UI already renders (frontend extractClips keys on the tool name containing
'ground' and on `r.moments`), so NO frontend change is needed; the tool keeps the
name `ground_video`. We return ONLY `moments` (each: t_start/t_end/score/label) —
the raw `events` (internal scores, metadata, also_matched) are dropped to keep the
tool log small, like the old /ground tool. Scores are normalized so the best match
is 100% and the rest are relative (the fan-out up-weights action streams ×1.2, so
raw fused scores exceed 1.0).
"""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def ground_video(video_id: str, query: str) -> dict[str, Any]:
    """Locate WHEN something happens in a video — the time span(s) matching a
    natural-language description, e.g. "when is the tomato sauce added?".

    Returns ranked candidate moments, each with a (t_start, t_end) span and a
    relevance score (0..1).
    """
    resp = await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/when",
        json={"query": query},
    )
    data = _unwrap(resp)
    events = data.get("events") or []
    valid = [e for e in events if "t_start" in e and "t_end" in e]
    # The /when fan-out up-weights action streams (×1.2) and max-normalizes WITHIN
    # each stream, so several top events land ABOVE 1.0. A hard clamp (min(.,1.0))
    # then made them all render as a flat 100%. Normalize by the top score instead
    # so the best match is 100% and the rest are scored RELATIVE to it — the
    # ranking spread (e.g. 100% / 95% / 92%) survives.
    top = max((float(e.get("score", 0.0)) for e in valid), default=0.0) or 1.0
    moments = [
        {
            "t_start": e["t_start"],
            "t_end": e["t_end"],
            "score": round(float(e.get("score", 0.0)) / top, 4),
            "label": e.get("label"),
        }
        for e in valid
    ]
    return {
        "video_id": data.get("video_id", video_id),
        "query": data.get("query", query),
        "moments": moments,
    }
