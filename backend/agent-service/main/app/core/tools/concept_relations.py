"""Tool: walk the entity-relation graph for an Index.

Two-step: resolve a concept name → entity_id (semantic match), then return
the entities connected to it via `entity_relations` rows. Use this when the
user asks how concepts connect within the course — "what's related to X",
"how does Y connect to Z", "show prerequisites of W".
"""
from typing import Any, Literal

from langchain.tools import tool

from cm_shared.internal import get_request, post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def find_concept_relations(
    index_id: str,
    concept_name: str,
    direction: Literal["both", "outgoing", "incoming"] = "both",
    top_k: int = 10,
) -> dict[str, Any]:
    """List concepts in an Index that are connected to a named concept.

    Resolves the concept name to the closest canonical entity, then returns
    the connected entities via the knowledge graph's relation edges. Each
    result has `canonical_name`, `entity_type`, `relation` (a short phrase
    extracted from the LLM, e.g. "is applied in", "computed via"),
    `relation_description`, `weight`, and `direction` (outgoing if this
    concept is the source, incoming if it's the target).

    Use this for graph-shaped questions:
    - "what's related to attention in this course"
    - "how do convolution and attention connect"
    - "prerequisites for understanding X"
    - "show the methods that use Y"
    - "khái niệm nào liên quan đến X"

    Returns `{"resolved_concept": {...}, "related": [...]}`. If the concept
    can't be resolved, `resolved_concept` is None and `related` is empty.
    """
    resolved = await post_request(
        "video-service",
        f"/api/v1/indexes/{index_id}/concepts/search",
        json={"query": concept_name, "top_k": 1},
    )
    data = _unwrap(resolved) or {}
    concepts = data.get("concepts") or []
    if not concepts:
        return {"resolved_concept": None, "related": []}
    top = concepts[0]
    entity_id = top["entity_id"]

    rel_resp = await get_request(
        "video-service",
        f"/api/v1/indexes/{index_id}/entities/{entity_id}/related",
        params={"direction": direction, "top_k": top_k},
    )
    rel_data = _unwrap(rel_resp) or {}
    return {
        "resolved_concept": top,
        "related": rel_data.get("related", []),
    }
