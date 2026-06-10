"""Tool: PANN AudioSet tag filter (video-service /sounds)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import get_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def find_sounds(video_id: str, tag: str | None = None) -> dict[str, Any]:
    """Find shots in a video tagged with a specific audio event (e.g. Laughter, Music, Cheering).

    `tag` should be an AudioSet-style label. Omit only when the user truly wants ALL audio events.
    """
    params: dict[str, Any] = {}
    if tag is not None:
        params["tag"] = tag
    resp = await get_request(
        "video-service",
        f"/api/v1/videos/{video_id}/sounds",
        params=params or None,
    )
    return _unwrap(resp)
