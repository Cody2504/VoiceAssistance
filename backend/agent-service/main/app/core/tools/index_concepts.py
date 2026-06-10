"""Tool: find KG entities in an Index relevant to a topic.

Pure KG retrieval — semantic match against `jockey_entities` filtered to the
attached index. Use this when the user asks WHAT concepts are covered, or
which entities exist in the course, rather than where they're discussed.
"""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def find_index_concepts(
    index_id: str,
    topic: str,
    top_k: int = 5,
    entity_types: list[str] | None = None,
) -> dict[str, Any]:
    """Return the top-k knowledge-graph entities in an Index that match `topic`.

    Use this when the user is asking about CONCEPTS / TOPICS covered in a
    course rather than asking to find specific videos. Triggers: "what
    concepts are in this course", "list the topics about X", "which ideas does
    this lecture series cover", "khái niệm chính là gì".

    Pass `entity_types` to filter (e.g. ["method", "tool"]). Leave it empty
    to consider all types. The response includes `mention_count` and
    `video_count` per concept so the reflect LLM can judge how central each
    one is to the course.

    Returns `{"concepts": [...], "kg_available": bool}`. If `kg_available`
    is False, the Index has no populated knowledge graph yet — fall back to
    `search_index` for the same query.
    """
    resp = await post_request(
        "video-service",
        f"/api/v1/indexes/{index_id}/concepts/search",
        json={
            "query": topic,
            "top_k": top_k,
            "entity_types": entity_types,
        },
    )
    return _unwrap(resp)
