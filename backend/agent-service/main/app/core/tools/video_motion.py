"""Tool: motion search — temporal action/movement retrieval (research A)."""
from typing import Any, Literal

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def search_motion(query: str, top_n: int = 5, group_by: Literal["clip", "video"] = "clip") -> dict[str, Any]:
    """Search the user's videos by MOTION — actions and movement over time
    (ViCLIP temporal embeddings), not just appearance.

    Use for queries about something HAPPENING — "a player blocks the punt",
    "someone adds tomato to the pan", "the dog jumps off the couch" — where
    regular search would also match clips that merely SHOW the object. Falls
    back gracefully: if motion search is disabled on the deployment this tool
    errors; use `search_corpus` instead for plain appearance/topic queries.
    """
    resp = await post_request(
        "video-service",
        "/api/v1/videos/search/motion",
        json={"query": query, "top_n": top_n, "group_by": group_by},
    )
    return _unwrap(resp)
