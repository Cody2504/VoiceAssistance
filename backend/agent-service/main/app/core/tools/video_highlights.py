"""Tool: QD-DETR saliency-ranked highlight reel (video-service /highlights)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import get_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def get_highlights(video_id: str, top_k: int = 10) -> dict[str, Any]:
    """Return the saliency-ranked highlight reel for a video. Includes ranked moments and per-shot saliency."""
    resp = await get_request(
        "video-service",
        f"/api/v1/videos/{video_id}/highlights",
        params={"top_k": top_k},
    )
    return _unwrap(resp)
