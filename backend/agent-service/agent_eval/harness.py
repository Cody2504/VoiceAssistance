"""Run one golden through the real agent graph; capture trajectory + answer."""
from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from cm_shared.internal import current_image
from main.app.core.graph.graph import build_graph

from agent_eval.fakes import inject_fake_tools
from agent_eval.goldens_loader import Golden
from agent_eval.trajectory import ToolCallRecord, extract_trajectory


@dataclass
class CaseRun:
    golden: Golden
    tool_calls: list[ToolCallRecord]
    final_answer: str


def _input_state(golden: Golden) -> dict:
    vids = golden.video_ids or ([golden.video_id] if golden.video_id else None)
    return {
        "messages": [HumanMessage(content=golden.query)],
        "video_id": vids[0] if vids else None,
        "video_ids": vids,
        "index_id": golden.index_id,
        "router_steps": 0,
    }


async def run_case(golden: Golden, *, live: bool = False) -> CaseRun:
    agent = build_graph()  # default MemorySaver — in-memory, never touches Postgres
    config = {"configurable": {"thread_id": f"eval-{golden.id}"}}
    token = current_image.set(golden.image or "")
    try:
        if live:
            result = await agent.ainvoke(_input_state(golden), config)
        else:
            with inject_fake_tools(golden.fake_outputs):
                result = await agent.ainvoke(_input_state(golden), config)
    finally:
        current_image.reset(token)
    calls, answer = extract_trajectory(result.get("messages") or [])
    return CaseRun(golden=golden, tool_calls=calls, final_answer=answer)
