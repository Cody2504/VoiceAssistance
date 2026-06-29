"""Master-router + tool-executor + reflect graph. Replaces the upstream JockeyLocal supervisor pattern."""
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from main.app.core.nodes.reflect import reflect_node
from main.app.core.nodes.router import route_after_router, router_node
from main.app.core.nodes.tool_executor import tool_executor_node
from main.app.core.state import AgentState


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Compile and return the agent graph. Pass `None` to use the in-process MemorySaver."""
    # No history node: the checkpointer restores state.messages per thread_id.
    # (Legacy conversations are seeded once in chat.py via aupdate_state.)
    # Surface-don't-force: the attached video(s) are surfaced to the router (see
    # _scope_note); the router itself decides whether to act on them. There is no
    # deterministic guard overriding that decision — a greeting with a video
    # attached just gets answered, a content question fetches the video.
    g: StateGraph = StateGraph(AgentState)
    g.add_node("router", router_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("reflect", reflect_node)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_after_router, {
        "tool_executor": "tool_executor",
        "reflect": "reflect",
    })
    g.add_edge("tool_executor", "router")
    g.add_edge("reflect", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())
