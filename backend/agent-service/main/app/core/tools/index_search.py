"""Tool: text-similarity search scoped to an Index (whole or a subset)."""
from typing import Any, Literal

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def search_index(
    index_id: str,
    query: str,
    video_ids: list[str] | None = None,
    top_n: int = 5,
    group_by: Literal["clip", "video"] = "video",
) -> dict[str, Any]:
    """Search shots within an Index (a collection of related videos — e.g. a lecture series).

    Pass `video_ids` to restrict the search to a subset of the index's videos. Leave it
    empty to search every video in the index ("Whole index" mode). Use this tool when the
    user's question references a series of videos, a course, a collection, or a "previous"
    or "earlier" video. `group_by="video"` returns one row per matching video; switch to
    `group_by="clip"` only when the user explicitly asks for multiple moments.
    """
    resp = await post_request(
        "video-service",
        f"/api/v1/indexes/{index_id}/search",
        json={
            "query": query,
            "video_ids": video_ids or [],
            "top_n": top_n,
            "group_by": group_by,
        },
    )
    return _unwrap(resp)
