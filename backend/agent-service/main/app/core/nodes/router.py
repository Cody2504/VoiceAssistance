"""router_node — picks the next tool call (or stops). Single LLM round-trip per pass."""
from typing import Any

from langchain_core.messages import SystemMessage

from cm_shared.internal import current_image
from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import router_prompt
from main.app.core.state import AgentState
from main.app.core.tools import TOOLS


def _scope_note(state: AgentState) -> str:
    """Inject attached IDs as a system message so the router has them in scope.

    Three possible scopes:
      - Single video: only `video_id` is set → traditional per-video tools.
      - Subset of an index: `index_id` + non-empty `video_ids` → use `search_index`
        with `video_ids` set, or per-video tools targeted at one of them.
      - Whole index: `index_id` set, `video_ids` empty → use `search_index` with
        an empty `video_ids` list.
    """
    vid = state.get("video_id")
    vids = state.get("video_ids") or []
    iid = state.get("index_id")
    lines: list[str] = []
    if iid:
        if vids:
            lines.append(
                f"Attached Index ID (in scope): {iid}\n"
                f"Selected videos within this index (subset scope):"
            )
            lines.extend(f"- {v}" for v in vids)
        else:
            lines.append(
                f"Attached Index ID (in scope, WHOLE INDEX — search every video in it): {iid}"
            )
        if vid and vid not in vids:
            lines.append(f"Current single video (if user references 'this video'): {vid}")
    else:
        all_vids = list(vids)
        if vid and vid not in all_vids:
            all_vids.append(vid)
        if not all_vids:
            return ""
        lines.append("Attached video IDs (in scope for this turn):")
        lines.extend(f"- {v}" for v in all_vids)
    return "\n".join(lines)


async def router_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("router").bind_tools(TOOLS)

    sys_msgs = [SystemMessage(content=router_prompt())]
    scope = _scope_note(state)
    if scope:
        sys_msgs.append(SystemMessage(content=scope))
    if current_image.get():
        sys_msgs.append(SystemMessage(content=(
            "The user has ATTACHED AN IMAGE to this turn. To find the scene/moment "
            "that matches or looks like the image, you MUST use an image tool (text "
            "search ignores the image). The image is supplied automatically — never "
            "put it in the arguments.\n"
            "- If NO single video is pinned (corpus / 'from my videos' / 'which video "
            "is this from') → call `search_scene_by_image` (searches all videos, "
            "returns the matching video(s) + timestamps).\n"
            "- If exactly one video is pinned and the user wants the moment in THAT "
            "video → call `find_scene_by_image` with that video_id."
        )))

    inputs = sys_msgs + list(state.get("messages") or [])
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
