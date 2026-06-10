"""Tool: cut + concatenate clips into a new video via ffmpeg (video-service /edit)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def combine_clips(video_id: str, clips: list[dict]) -> dict[str, Any]:
    """Cut and concatenate clips from a source video. `clips` is a list of {t_start, t_end} dicts (seconds)."""
    resp = await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/edit",
        json={"clips": clips},
    )
    return _unwrap(resp)
