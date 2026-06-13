"""reflect_node — produces the final user-facing answer. Streams tokens (tag=reflect)."""
from typing import Any

from langchain_core.messages import SystemMessage

from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import reflect_prompt
from main.app.core.state import AgentState


async def reflect_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("reflect")
    # Trailing anchor: conversations that predate the Postgres checkpointer can
    # contain duplicated assistant turns (the old history_node bug). That
    # repetition pattern pulls the model into replaying the previous answer, so
    # explicitly pin it to the latest question + tool result.
    anchor = SystemMessage(
        content=(
            "Answer ONLY the user's most recent question, using the most recent "
            "tool result. Do NOT repeat or rephrase an earlier assistant answer "
            "unless the latest question asks for it."
        )
    )
    inputs = [SystemMessage(content=reflect_prompt())] + list(state.get("messages") or []) + [anchor]
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
