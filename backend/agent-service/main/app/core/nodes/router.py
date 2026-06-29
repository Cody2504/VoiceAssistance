"""router_node — picks the next tool call (or stops). Single LLM round-trip per pass.

route_after_router sends the turn straight to the tool executor or to reflect based
on the router's OWN decision (did it emit a tool call?). There is no deterministic
guard in between: the attached video(s) are surfaced to the router via _scope_note,
and the router decides whether the user's message actually calls for acting on them.
"""
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from cm_shared.internal import current_image
from main.app.common.conf.app_conf import get_settings
from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import router_prompt
from main.app.core.state import AgentState
from main.app.core.tools import TOOLS

_IMAGE_NOTE = (
    "The user has ATTACHED AN IMAGE to this turn. If you have NOT yet searched it "
    "this turn, search it ONCE NOW with an image tool (text search ignores the "
    "image) — treat it as a NEW search about THIS image; do NOT reuse a previous "
    "turn's matched video or answer. As soon as you have the image-search RESULT, "
    "ANSWER from it — do NOT call the image tool again. The image is supplied "
    "automatically — never put it in the arguments.\n"
    "- If NO single video is pinned (corpus / 'from my videos' / 'which video "
    "is this from') → call `search_scene_by_image` (searches all videos, "
    "returns the matching video(s) + timestamps).\n"
    "- If exactly one video is pinned and the user wants the moment in THAT "
    "video → call `find_scene_by_image` with that video_id."
)


def _scope_note(state: AgentState) -> str:
    """Surface attached IDs to the router so it has them in scope — WITHOUT forcing
    a fetch. The router decides whether the user's message actually calls for acting
    on the attached video(s); a greeting or an off-topic message needs no fetch.

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
                f"→ Act on it with a per-video tool ONLY when the user's message is about a video "
                f"(its content, a specific moment, a summary, grounding, etc.). For a greeting or a "
                f"message not about any video, just reply — an attached video is NOT by itself a reason "
                f"to fetch. When you do act, use THIS video_id; do not substitute one seen only in an "
                f"earlier tool result unless the user explicitly refers back to that earlier video."
            )
        else:
            lines.append("THIS TURN's attached videos (all in scope — act on the one(s) the user means):")
            lines.extend(f"- {v}" for v in all_vids)
            lines.append(
                "→ Act on them ONLY when the user's request is about a video: for 'this video' use the "
                "most recently attached, for 'compare/both/all' act on all of them. A greeting or a "
                "message not about any video needs no fetch. Do NOT pull in a video_id from earlier in "
                "the conversation unless the user explicitly refers to it."
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


def _at_cap(state: AgentState) -> bool:
    return (state.get("router_steps") or 0) >= get_settings().router_max_steps


_IMAGE_TOOLS = {"search_scene_by_image", "find_scene_by_image"}


def _image_tool_ran_this_turn(messages: list) -> bool:
    """True if an image tool already produced a result since the last user message.
    Used to stop the router re-calling the same image search in a loop."""
    for m in reversed(messages[:-1]):  # skip the just-emitted AIMessage tool call
        if isinstance(m, HumanMessage):
            return False
        if isinstance(m, ToolMessage) and getattr(m, "name", None) in _IMAGE_TOOLS:
            return True
    return False


def route_after_router(state: AgentState) -> Literal["tool_executor", "reflect"]:
    """Honor the router's decision: run the tool(s) it picked, else go answer.

    Two overrides end a runaway loop: the step cap, and — deterministically — an
    image tool is NEVER re-run once it already produced a result this turn (the
    router answers from that result instead of searching the same image again)."""
    if _at_cap(state):
        return "reflect"
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        wants_image = any((tc.get("name") in _IMAGE_TOOLS) for tc in last.tool_calls)
        if wants_image and _image_tool_ran_this_turn(messages):
            return "reflect"
        return "tool_executor"
    return "reflect"
