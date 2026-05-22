"""Master-router + tool-executor + reflect graph. Replaces the upstream JockeyLocal supervisor pattern."""
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from main.app.common.conf.app_conf import get_settings
from main.app.core.nodes.history import history_node
from main.app.core.nodes.reflect import reflect_node
from main.app.core.nodes.router import router_node
from main.app.core.nodes.tool_executor import tool_executor_node
from main.app.core.state import AgentState


def _route_after_router(state: AgentState) -> Literal["tool_executor", "reflect"]:
    """Send to tool_executor if the router emitted a tool call AND we still have budget."""
    s = get_settings()
    steps = state.get("router_steps") or 0
    if steps >= s.router_max_steps:
        return "reflect"

    msgs = state.get("messages") or []
    last = msgs[-1] if msgs else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tool_executor"
    return "reflect"


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Compile and return the agent graph. Pass `None` to use the in-process MemorySaver."""
    g: StateGraph = StateGraph(AgentState)
    g.add_node("history", history_node)
    g.add_node("router", router_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("reflect", reflect_node)

    g.add_edge(START, "history")
    g.add_edge("history", "router")
    g.add_conditional_edges("router", _route_after_router, {
        "tool_executor": "tool_executor",
        "reflect": "reflect",
    })
    g.add_edge("tool_executor", "router")
    g.add_edge("reflect", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())
