"""Tool: free-form Q&A / summary / time-range QA on a single video (Qwen3-VL via video-service /qa)."""
from typing import Any

from langchain.tools import tool

from cm_shared.internal import post_request
from cm_shared.response import unwrap_response as _unwrap


@tool
async def ask_video_local(video_id: str, question: str, t_start: float | None = None, t_end: float | None = None) -> dict[str, Any]:
    """Ask a free-form question about a video segment (or whole video).

    For time-range questions (e.g. 'from 0:15 to 0:25 what does the speaker say'), pass
    `t_start` and `t_end` in seconds. For whole-video summaries, omit both.
    """
    body: dict[str, Any] = {"question": question}
    if t_start is not None:
        body["t_start"] = t_start
    if t_end is not None:
        body["t_end"] = t_end
    resp = await post_request("video-service", f"/api/v1/videos/{video_id}/qa", json=body)
    return _unwrap(resp)
