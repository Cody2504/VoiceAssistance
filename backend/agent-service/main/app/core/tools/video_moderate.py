"""Tool: NSFW ViT + toxic-bert moderation report (video-service /moderate)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import get_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def moderate_video(video_id: str, threshold: float = 0.5) -> dict[str, Any]:
    """Run a moderation report on a video. Returns per-shot NSFW + toxicity aggregates plus the flagged-shot list."""
    resp = await get_request(
        "video-service",
        f"/api/v1/videos/{video_id}/moderate",
        params={"threshold": threshold},
    )
    return _unwrap(resp)
