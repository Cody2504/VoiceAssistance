"""Tool: caption-embedding cosine similarity recommender (video-service /similar)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import get_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def find_similar(video_id: str, top_k: int = 5) -> dict[str, Any]:
    """Find videos similar to a source video within the user's corpus. Returns ranked candidates with scores.

    May return fewer than `top_k` if the corpus is small — that is a terminal result, not an error.
    """
    resp = await get_request(
        "video-service",
        f"/api/v1/videos/{video_id}/similar",
        params={"top_k": top_k},
    )
    return _unwrap(resp)
