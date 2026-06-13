"""Tool: compositional / sequential search (roadmap #5).

Finds an ordered set of events in one video and verifies they occur in that
order. The router decomposes "A then B then C" into the ordered `steps`; this
tool grounds each step and checks the temporal order. No new model — pure
orchestration over existing retrieval.

Per-step grounding uses the lightweight `/ground` endpoint (single cached
SG-DETR head on IV2 features), NOT the `/when` fan-out: `/when` instantiates
3-4 heavy encoders (CLIP-L, CLAP, Motion, OpenRouter embed) inline per query
AND is synchronous inside its async endpoint, so N steps serialize on the
server and a 7-step sequence took >1 min. `/ground` is one cached model →
seconds. The calls also run concurrently via asyncio.gather (2026-06-13 demo
latency fix v2).
"""
import asyncio
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap
from main.app.core.tools._sequence_logic import build_sequence


async def _ground_step(video_id: str, query: str) -> dict | None:
    """Top-1 /ground moment for a single step (None if nothing found)."""
    resp = await post_request(
        "video-service", f"/api/v1/videos/{video_id}/ground",
        json={"query": query},
    )
    moments = (_unwrap(resp) or {}).get("moments", []) or []
    return moments[0] if moments else None


@tool
async def find_sequence(video_id: str, steps: list[str]) -> dict[str, Any]:
    """Find an ordered sequence of events in ONE video and check they happen in
    that order. Use for compositional / sequential questions like "X then Y then
    Z", "does A happen before B", or "after the onions, when is the sauce added".

    Pass `steps` as the events in their intended order, e.g.
    ["onions added", "tomato sauce poured", "pasta added"]. Returns each step's
    best timestamp plus `ordered` (True iff all were found and occur in the
    listed order)."""
    per_step_top = await asyncio.gather(*(_ground_step(video_id, q) for q in steps))
    return build_sequence(steps, list(per_step_top))
