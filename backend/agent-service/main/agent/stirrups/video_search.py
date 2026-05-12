"""video-search stirrup — local (Qdrant via video-service) or Twelve Labs fallback."""
from typing import Any

from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from cm_shared.internal import post_request

WORKER_NAME = "video-search"

SEARCH_PROMPT = """You are the video-search worker. Translate the user's request into a single
search call against a specific video. Return whatever the tool returns; do not summarize.
"""


@tool
async def search_video_local(video_id: str, query: str) -> dict[str, Any]:
    """Search shots of a video using Qdrant semantic search (local backend)."""
    return await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/search",
        json={"query": query},
    )


@tool
async def search_video_twelvelabs(index_id: str, query: str) -> dict[str, Any]:
    """Search videos via Twelve Labs (fallback, requires TWELVE_LABS_API_KEY)."""
    # Defer to the existing jockey implementation when explicitly toggled.
    from jockey.stirrups.video_search import VideoSearchWorker  # noqa: F401
    # Minimal pass-through — real adoption would wrap VideoSearchWorker's underlying functions.
    raise NotImplementedError("Twelve Labs fallback requires wiring jockey.stirrups.video_search functions.")


def build_search_worker(worker_llm, use_local: bool = True):
    tools = [search_video_local] if use_local else [search_video_twelvelabs]
    prompt = ChatPromptTemplate.from_messages([("system", SEARCH_PROMPT), MessagesPlaceholder("worker_task")])
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
