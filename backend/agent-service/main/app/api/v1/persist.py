"""Persistence helpers for the chat stream — stdlib-only on purpose so unit
tests can import this without pulling in the LangChain/SSE stack."""
import json


def attach_tool_result(tool_calls: list[dict], tool: str, result) -> None:
    """Attach a tool's output to its first pending `tool_calls` entry.

    FIFO across repeated calls of the same tool; entries that already carry a
    result are skipped. The result is round-tripped through JSON with
    ``default=str`` so the JSONB column never receives non-serializable
    objects (UUID, datetime, ...). No matching pending entry → no-op.
    """
    jsonable = json.loads(json.dumps(result, default=str))
    for entry in tool_calls:
        if entry.get("tool") == tool and "result" not in entry:
            entry["result"] = jsonable
            return
