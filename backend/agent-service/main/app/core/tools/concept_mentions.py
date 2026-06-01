"""Tool: locate where a named concept appears across an Index.

Two-step under the hood:
  1. Semantic lookup against `jockey_entities` to resolve `concept_name`
     to a canonical entity_id in the attached index.
  2. Pull every `entity_mentions` row for that entity, ordered by the
     video's position in the index, then by segment index.

Use this when the user wants timestamps — "where does X come up", "when did
the professor first introduce Y", "find scenes that talk about Z".
"""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import get_request, post_request


def _unwrap(resp: Any) -> Any:
    if isinstance(resp, dict) and "data" in resp and "success" in resp:
        return resp.get("data")
    return resp


@tool
async def find_concept_mentions(
    index_id: str,
    concept_name: str,
    video_ids: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Find every segment in an Index that mentions a named concept.

    Resolves the concept name to the closest canonical entity in this index
    (semantic match), then returns the segments where it was mentioned —
    ordered by the video's position in the course, then by time within the
    video. Each result has `video_title`, `video_position`, `t_start`,
    `t_end`, `transcript`, and `caption` so the reflect LLM can compose
    answers with citations.

    Pass `video_ids` to restrict to a subset of the index's videos. Especially
    useful for "previous video" semantics — pass the IDs of videos with
    position < current.position to constrain to prior lectures.

    Returns `{"resolved_concept": {...}, "mentions": [...]}`. If the
    concept can't be matched (empty KG or no entity close enough),
    `resolved_concept` is None and `mentions` is empty — fall back to
    `search_index`.

    Triggers: "where does X come up", "when does the professor introduce Y",
    "find scenes about Z", "tìm những đoạn nói về X", "professor mentions Y".
    """
    # Step 1: resolve concept name to the closest entity.
    resolved = await post_request(
        "video-service",
        f"/api/v1/indexes/{index_id}/concepts/search",
        json={"query": concept_name, "top_k": 1},
    )
    data = _unwrap(resolved) or {}
    concepts = data.get("concepts") or []
    if not concepts:
        return {"resolved_concept": None, "mentions": []}
    top = concepts[0]
    entity_id = top["entity_id"]

    # Step 2: fetch mentions for that entity, optionally scoped to a subset of videos.
    params: dict[str, Any] = {"limit": limit}
    if video_ids:
        params["video_ids"] = ",".join(video_ids)

    mentions_resp = await get_request(
        "video-service",
        f"/api/v1/indexes/{index_id}/entities/{entity_id}/mentions",
        params=params,
    )
    mentions_data = _unwrap(mentions_resp) or {}
    return {
        "resolved_concept": top,
        "mentions": mentions_data.get("mentions", []),
    }
