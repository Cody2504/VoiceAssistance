"""Tool: compositional / sequential search (roadmap #5).

Finds an ordered set of events in one video and verifies they occur in that
order. The router decomposes "A then B then C" into the ordered `steps`; this
tool grounds each step via the video-service `/when` fan-out and checks the
temporal order. No new model — pure orchestration over existing retrieval.
"""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap
from main.app.core.tools._sequence_logic import build_sequence


@tool
async def find_sequence(video_id: str, steps: list[str]) -> dict[str, Any]:
    """Find an ordered sequence of events in ONE video and check they happen in
    that order. Use for compositional / sequential questions like "X then Y then
    Z", "does A happen before B", or "after the onions, when is the sauce added".

    Pass `steps` as the events in their intended order, e.g.
    ["onions added", "tomato sauce poured", "pasta added"]. Returns each step's
    best timestamp plus `ordered` (True iff all were found and occur in the
    listed order)."""
    per_step_top: list[dict | None] = []
    for q in steps:
        resp = await post_request(
            "video-service", f"/api/v1/videos/{video_id}/when",
            json={"query": q, "refine": False},
        )
        events = (_unwrap(resp) or {}).get("events", []) or []
        per_step_top.append(events[0] if events else None)
    return build_sequence(steps, per_step_top)
