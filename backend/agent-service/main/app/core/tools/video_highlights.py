"""Tool: QD-DETR saliency-ranked highlight reel (video-service /highlights)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import get_request


def _unwrap(resp: Any) -> Any:
    if isinstance(resp, dict) and "data" in resp and "success" in resp:
        return resp.get("data")
    return resp


@tool
async def get_highlights(video_id: str, top_k: int = 10) -> dict[str, Any]:
    """Return the saliency-ranked highlight reel for a video. Includes ranked moments and per-shot saliency."""
    resp = await get_request(
        "video-service",
        f"/api/v1/videos/{video_id}/highlights",
        params={"top_k": top_k},
    )
    return _unwrap(resp)
