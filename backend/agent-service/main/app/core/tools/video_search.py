"""Tool: corpus-wide search and single-video shot search."""
from typing import Any, Literal

from langchain.tools import tool

from cm_shared.internal import post_request


def _unwrap(resp: Any) -> Any:
    if isinstance(resp, dict) and "data" in resp and "success" in resp:
        return resp.get("data")
    return resp


@tool
async def search_corpus(query: str, top_n: int = 3, group_by: Literal["clip", "video"] = "video") -> dict[str, Any]:
    """Search across all of the user's indexed videos.

    `group_by="video"` returns one row per distinct video — the default and right choice for
    "find the video about X" / "find videos about X". Use `group_by="clip"` only when the
    user explicitly asks for multiple clips/moments/scenes.
    """
    resp = await post_request(
        "video-service",
        "/api/v1/videos/search",
        json={"query": query, "top_n": top_n, "group_by": group_by},
    )
    return _unwrap(resp)


@tool
async def search_video_local(video_id: str, query: str) -> dict[str, Any]:
    """Search shots within a single video by id."""
    resp = await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/search",
        json={"query": query},
    )
    return _unwrap(resp)
