"""NEW stirrup — calls video-service /ground with the trained head.

This is the thesis showcase tool: the agent invokes the trained grounding model.
"""
from typing import Any

from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from cm_shared.internal import post_request

WORKER_NAME = "video-grounding"

GROUNDING_PROMPT = """You are the video-grounding worker. Your job is to take a user request
about locating a moment in a specific video and translate it into a single grounding call.

You have one tool:
  - ground_video(video_id, query): returns ranked shots and predicted span [t_start, t_end].

Always pass the cleanest natural-language description of the target moment as `query`.
"""


@tool
async def ground_video(video_id: str, query: str) -> dict[str, Any]:
    """Run the trained grounding head against a specific video for a natural-language query.

    Returns ranked relevant shots and a predicted (t_start, t_end) span.
    """
    return await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/ground",
        json={"query": query},
    )


def build_grounding_worker(worker_llm):
    """Construct a langchain worker bound to the grounding tool."""
    prompt = ChatPromptTemplate.from_messages([("system", GROUNDING_PROMPT), MessagesPlaceholder("worker_task")])
    llm = worker_llm.bind_tools([ground_video])

    async def _call_tools(message):
        out = []
        for tc in (message.tool_calls or []):
            tool_obj = {"ground_video": ground_video}[tc["name"]]
            tc = dict(tc)
            tc["output"] = await tool_obj.ainvoke(tc["args"])
            out.append(tc)
        return out

    worker = (prompt | llm | _call_tools).with_config({"tags": [WORKER_NAME]})
    worker.name = WORKER_NAME
    return worker
