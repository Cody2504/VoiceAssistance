"""Agent graph state."""
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def merge_unique(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """Reducer: order-preserving dedupe union (accumulates across turns)."""
    out = list(existing or [])
    for v in new or []:
        if v not in out:
            out.append(v)
    return out


class AgentState(TypedDict, total=False):
    # Conversation context
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_id: str
    user_id: str

    # Attached video(s) — passed in by the API layer
    video_id: str | None
    video_ids: list[str] | None
    # Attached index — when set, the user is asking against an Index (lecture
    # series / collection). `video_ids` may be empty (whole index) or a subset.
    index_id: str | None

    # Most recent tool result, copied out for reflect/router context
    last_tool_name: str | None
    last_tool_result: Any

    # Number of router→tool→router cycles taken (cap with settings.router_max_steps)
    router_steps: int

    # video_ids any per-video tool has acted on, accumulated across the thread.
    acted_video_ids: Annotated[list[str], merge_unique]
