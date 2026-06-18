"""reflect_node — produces the final user-facing answer. Streams tokens (tag=reflect)."""
from typing import Any

from langchain_core.messages import SystemMessage

from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import reflect_prompt
from main.app.core.state import AgentState


# Trailing anchor: conversations that predate the Postgres checkpointer can
# contain duplicated assistant turns (the old history_node bug). That repetition
# pulls the model into replaying the previous answer, so pin it to the latest
# question. "result(s)" (plural-aware) lets multi-video turns — where scope_guard
# fetched several attached videos — synthesize across ALL of this turn's results.
REFLECT_ANCHOR = (
    "Answer ONLY the user's most recent question, using the tool result(s) "
    "produced for the current question. When several videos were fetched this "
    "turn, synthesize across ALL of their results. Do NOT repeat or rephrase an "
    "earlier assistant answer unless the latest question asks for it."
)


async def reflect_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("reflect")
    anchor = SystemMessage(content=REFLECT_ANCHOR)
    inputs = [SystemMessage(content=reflect_prompt())] + list(state.get("messages") or []) + [anchor]
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
