"""tool_executor_node — invokes the tool calls emitted by router and feeds results back."""
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from main.app.core.state import AgentState
from main.app.core.tools import TOOLS_BY_NAME

log = logging.getLogger(__name__)


async def tool_executor_node(state: AgentState) -> dict[str, Any]:
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"router_steps": (state.get("router_steps") or 0) + 1}

    tool_msgs: list = []
    last_name: str | None = None
    last_result: Any = None

    for call in last.tool_calls:
        name = call.get("name") or ""
        args = call.get("args") or {}
        call_id = call.get("id") or name
        tool_obj = TOOLS_BY_NAME.get(name)
        if tool_obj is None:
            err = f"Unknown tool: {name}"
            tool_msgs.append(ToolMessage(content=err, tool_call_id=call_id, name=name))
            last_name, last_result = name, {"error": err}
            log.warning("tool_executor: %s", err)
            continue
        try:
            result = await tool_obj.ainvoke(args)
        except Exception as exc:
            log.exception("tool_executor: %s failed", name)
            result = {"error": f"{type(exc).__name__}: {exc}"}
        last_name, last_result = name, result
        tool_msgs.append(
            ToolMessage(
                content=json.dumps(result, default=str)[:8000],
                tool_call_id=call_id,
                name=name,
            )
        )

    return {
        "messages": tool_msgs,
        "last_tool_name": last_name,
        "last_tool_result": last_result,
        "router_steps": (state.get("router_steps") or 0) + 1,
    }
