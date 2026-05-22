"""history_node — loads prior conversation turns from Postgres into state.messages.

Called once at the start of each request. If `conversation_id` is missing or unknown,
returns an empty history.
"""
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.db import get_sessionmaker
from main.app.core.state import AgentState
from main.app.db.models.conversation import Message

log = logging.getLogger(__name__)


async def _load(session: AsyncSession, conversation_id: str) -> list:
    rows = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()
    msgs: list = []
    for r in rows:
        if r.role == "user":
            msgs.append(HumanMessage(content=r.content or ""))
        elif r.role == "assistant":
            msgs.append(AIMessage(content=r.content or ""))
    return msgs


async def history_node(state: AgentState) -> dict[str, Any]:
    cid = state.get("conversation_id")
    if not cid:
        return {"router_steps": 0}
    try:
        async with get_sessionmaker()() as session:
            prior = await _load(session, cid)
    except Exception as exc:
        log.warning("history_node: load failed conversation_id=%s err=%s", cid, exc)
        prior = []
    return {"messages": prior, "router_steps": 0}
