"""reflect_node — produces the final user-facing answer. Streams tokens (tag=reflect)."""
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from main.app.common.service.llm import get_llm_client
from main.app.core.constants.prompts import reflect_prompt
from main.app.core.state import AgentState


# Vietnamese-specific letters/diacritics. Their presence reliably marks VI; the
# absence (Latin-only) marks EN — the two languages this product serves. This
# fixes "English question -> Vietnamese answer": reflect.md asks the model to
# match the user's language, but nothing told it WHICH language the user used,
# so it guessed (and Vietnamese tool/UI context biased it). We detect it and pin
# it explicitly as a trailing (most-salient) system message.
_VI_CHARS = re.compile(
    r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]",
    re.IGNORECASE,
)


def _detect_user_language(messages: list) -> str:
    """Language of the user's most recent message: 'Vietnamese', 'English', or
    '' (unknown — leave the model to infer)."""
    text = ""
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            c = m.content
            text = c if isinstance(c, str) else " ".join(
                p.get("text", "") for p in c if isinstance(p, dict)
            ) if isinstance(c, list) else str(c)
            break
    if not text.strip():
        return ""
    if _VI_CHARS.search(text):
        return "Vietnamese"
    # Latin-only text → English (the other language this product serves).
    return "English"


# Trailing anchor: conversations that predate the Postgres checkpointer can
# contain duplicated assistant turns (the old history_node bug). That repetition
# pulls the model into replaying the previous answer, so pin it to the latest
# question. "result(s)" (plural-aware) lets multi-video turns — where the router
# fetched several attached videos — synthesize across ALL of this turn's results.
REFLECT_ANCHOR = (
    "Answer ONLY the user's most recent question, using the tool result(s) "
    "produced for the current question. When several videos were fetched this "
    "turn, synthesize across ALL of their results. Do NOT repeat or rephrase an "
    "earlier assistant answer unless the latest question asks for it."
)


async def reflect_node(state: AgentState) -> dict[str, Any]:
    llm = get_llm_client("reflect")
    msgs = list(state.get("messages") or [])
    anchor = SystemMessage(content=REFLECT_ANCHOR)
    trailing = [anchor]
    lang = _detect_user_language(msgs)
    if lang:
        trailing.append(SystemMessage(content=(
            f"CRITICAL: the user's latest message is written in {lang}. Write your "
            f"ENTIRE response in {lang}; do not switch languages. (Technical terms "
            f"may stay in English when that's how they appear in the transcripts.)"
        )))
    inputs = [SystemMessage(content=reflect_prompt())] + msgs + trailing
    response = await llm.ainvoke(inputs)
    return {"messages": [response]}
