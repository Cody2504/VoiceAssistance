"""scope_guard_node — guarantees per-turn attached videos are fetched.

Runs right after the router. If the router decided to stop (no tool call) but
videos attached THIS turn were never fetched in this thread, deterministically
synthesize an `ask_video_local` call per un-fetched attachment so the agent acts
on the attached videos instead of summarizing stale earlier results.
"""
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage

from cm_shared.internal import current_image
from main.app.common.conf.app_conf import get_settings
from main.app.core.state import AgentState


def missing_attached(state: AgentState) -> list[str]:
    """Attached videos this turn that no per-video tool has acted on yet.

    Empty when an index or an image is attached (those route through their own
    tool families, not per-video summary)."""
    if state.get("index_id"):
        return []
    if current_image.get():
        return []
    attached = list(state.get("video_ids") or [])
    vid = state.get("video_id")
    if vid and vid not in attached:
        attached.append(vid)
    acted = set(state.get("acted_video_ids") or [])
    return [v for v in attached if v not in acted]


def _latest_human_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else ""
    return ""


def _at_cap(state: AgentState) -> bool:
    return (state.get("router_steps") or 0) >= get_settings().router_max_steps


# A node must update at least one channel (langgraph forbids an empty dict). This
# no-op writes an empty list to acted_video_ids, which merge_unique ignores.
_PASS_THROUGH: dict[str, Any] = {"acted_video_ids": []}


async def scope_guard_node(state: AgentState) -> dict[str, Any]:
    if _at_cap(state):
        return dict(_PASS_THROUGH)
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return dict(_PASS_THROUGH)  # router already chose tool(s)
    missing = missing_attached(state)
    if not missing:
        return dict(_PASS_THROUGH)
    question = _latest_human_text(messages) or "Summarize this video."
    calls = [
        {"name": "ask_video_local", "args": {"video_id": v, "question": question}, "id": f"forced-{i}-{v}"}
        for i, v in enumerate(missing)
    ]
    return {"messages": [AIMessage(content="", tool_calls=calls)]}


def route_after_guard(state: AgentState) -> Literal["tool_executor", "reflect"]:
    if _at_cap(state):
        return "reflect"
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tool_executor"
    return "reflect"
