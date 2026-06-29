"""Extract the agent's tool-call trajectory + final answer from a finished run."""
from dataclasses import dataclass

from langchain_core.messages import AIMessage


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    forced: bool = False  # id "forced-*" = synthesized, not a router decision (legacy; the
                          # graph no longer force-fetches, but flag any stray forced calls)


def extract_trajectory(messages: list) -> tuple[list[ToolCallRecord], str]:
    """Return (ordered tool calls, final answer text).

    Every call here is router-chosen now; any "forced-*" id (none are produced
    since the scope-guard was removed) is still flagged so routing metrics can
    ignore it. The final answer is the content of the last AIMessage that made no
    tool calls (the reflect output)."""
    calls: list[ToolCallRecord] = []
    final_answer = ""
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for c in m.tool_calls:
                cid = str(c.get("id") or "")
                calls.append(ToolCallRecord(
                    name=c.get("name") or "",
                    args=c.get("args") or {},
                    forced=cid.startswith("forced-"),
                ))
        elif isinstance(m, AIMessage):
            content = m.content if isinstance(m.content, str) else ""
            if content:
                final_answer = content
    return calls, final_answer
