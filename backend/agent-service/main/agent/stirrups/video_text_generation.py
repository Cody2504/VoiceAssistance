"""video-text-generation stirrup — local Qwen3-VL via video-service /qa, or Twelve Labs Pegasus."""
from typing import Any

from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from cm_shared.internal import post_request

WORKER_NAME = "video-text-generation"

TEXTGEN_PROMPT = """You are the video-text-generation worker. Use the tool to ask a question or
request a summary of a specific video. Pass the user's intent verbatim.
"""


@tool
async def ask_video_local(video_id: str, question: str, t_start: float | None = None, t_end: float | None = None) -> dict[str, Any]:
    """Ask a free-form question about a video segment (or whole video) via the local Qwen3-VL backend."""
    body = {"question": question}
    if t_start is not None:
        body["t_start"] = t_start
    if t_end is not None:
        body["t_end"] = t_end
    return await post_request("video-service", f"/api/v1/videos/{video_id}/qa", json=body)


def build_textgen_worker(worker_llm, use_local: bool = True):
    tools = [ask_video_local]   # Twelve Labs Pegasus fallback wiring deferred.
    prompt = ChatPromptTemplate.from_messages([("system", TEXTGEN_PROMPT), MessagesPlaceholder("worker_task")])
    llm = worker_llm.bind_tools(tools)

    async def _call_tools(message):
        out = []
        for tc in (message.tool_calls or []):
            tool_obj = {t.name: t for t in tools}[tc["name"]]
            tc = dict(tc)
            tc["output"] = await tool_obj.ainvoke(tc["args"])
            out.append(tc)
        return out

    worker = (prompt | llm | _call_tools).with_config({"tags": [WORKER_NAME]})
    worker.name = WORKER_NAME
    return worker
