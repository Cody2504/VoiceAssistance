"""video-editing stirrup — always local, ffmpeg via video-service /edit."""
from typing import Any

from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from cm_shared.internal import post_request

WORKER_NAME = "video-editing"

EDIT_PROMPT = """You are the video-editing worker. Build a list of clips
(each with t_start and t_end in seconds) that fulfils the user's request, then call combine_clips.
"""


@tool
async def combine_clips(video_id: str, clips: list[dict]) -> dict[str, Any]:
    """Cut and concatenate the listed clips from a source video. clips is a list of {t_start, t_end}."""
    return await post_request("video-service", f"/api/v1/videos/{video_id}/edit", json={"clips": clips})


def build_editing_worker(worker_llm):
    tools = [combine_clips]
    prompt = ChatPromptTemplate.from_messages([("system", EDIT_PROMPT), MessagesPlaceholder("worker_task")])
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
