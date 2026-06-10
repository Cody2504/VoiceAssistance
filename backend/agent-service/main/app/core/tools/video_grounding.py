"""Tool: temporal grounding via trained QD-DETR head (video-service /ground)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def ground_video(video_id: str, query: str) -> dict[str, Any]:
    """Locate the precise span in a video matching a natural-language description.

    Returns ranked relevant shots and a predicted (t_start, t_end) span.
    """
    resp = await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/ground",
        json={"query": query},
    )
    return _unwrap(resp)
