"""router_node — picks the next tool call (or stops). Single LLM round-trip per pass."""
from typing import Any

from langchain_core.messages import SystemMessage

from cm_shared.internal import current_image
from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import router_prompt
from main.app.core.state import AgentState
from main.app.core.tools import TOOLS

_IMAGE_NOTE = (
    "The user has ATTACHED AN IMAGE to this turn. To find the scene/moment "
    "that matches or looks like the image, you MUST use an image tool (text "
    "search ignores the image). The image is supplied automatically — never "
    "put it in the arguments.\n"
    "- If NO single video is pinned (corpus / 'from my videos' / 'which video "
    "is this from') → call `search_scene_by_image` (searches all videos, "
    "returns the matching video(s) + timestamps).\n"
    "- If exactly one video is pinned and the user wants the moment in THAT "
    "video → call `find_scene_by_image` with that video_id."
)


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
        if len(all_vids) == 1:
            lines.append(
                f"THIS TURN's attached video (the subject of 'this video'): {all_vids[0]}\n"
                f"→ Use THIS video_id for every per-video tool by default. Do NOT substitute a "
                f"video_id seen only in an earlier tool result or message unless the user explicitly "
                f"refers to that earlier/previous video."
            )
        else:
            lines.append("THIS TURN's attached videos (all in scope — act on the one(s) the user means):")
            lines.extend(f"- {v}" for v in all_vids)
            lines.append(
                "→ For 'this video' use the most recently attached; for 'compare/both' act on all of "
                "them; do NOT pull in a video_id from earlier in the conversation unless the user "
                "explicitly refers to it."
            )
    return "\n".join(lines)


def build_router_inputs(state: AgentState) -> list:
    """Router prompt first, conversation history next, per-turn attachment scope LAST.

    Placing the attached-video scope after the history beats recency/lost-in-the-middle
    bias: the model reads the current attachment immediately before deciding."""
    messages = list(state.get("messages") or [])
    trailing: list = []
    scope = _scope_note(state)
    if scope:
        trailing.append(SystemMessage(content=scope))
    if current_image.get():
        trailing.append(SystemMessage(content=_IMAGE_NOTE))
    return [SystemMessage(content=router_prompt())] + messages + trailing


async def router_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("router").bind_tools(TOOLS)
    inputs = build_router_inputs(state)
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
