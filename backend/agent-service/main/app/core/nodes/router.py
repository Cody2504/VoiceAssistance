"""router_node — picks the next tool call (or stops). Single LLM round-trip per pass."""
from typing import Any

from langchain_core.messages import SystemMessage

from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import router_prompt
from main.app.core.state import AgentState
from main.app.core.tools import TOOLS


def _scope_note(state: AgentState) -> str:
    """Inject attached video IDs as a system message so the router has them in scope."""
    vid = state.get("video_id")
    vids = state.get("video_ids") or []
    if vid and vid not in vids:
        vids = [*vids, vid]
    if not vids:
        return ""
    pretty = "\n".join(f"- {v}" for v in vids)
    return f"Attached video IDs (in scope for this turn):\n{pretty}"


async def router_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("router").bind_tools(TOOLS)

    sys_msgs = [SystemMessage(content=router_prompt())]
    scope = _scope_note(state)
    if scope:
        sys_msgs.append(SystemMessage(content=scope))

    inputs = sys_msgs + list(state.get("messages") or [])
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
