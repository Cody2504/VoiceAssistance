"""reflect_node — produces the final user-facing answer. Streams tokens (tag=reflect)."""
from typing import Any

from langchain_core.messages import SystemMessage

from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import reflect_prompt
from main.app.core.state import AgentState


async def reflect_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("reflect")
    inputs = [SystemMessage(content=reflect_prompt())] + list(state.get("messages") or [])
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
