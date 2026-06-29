from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.app.db.models.conversation import Conversation, Message

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    user_id = UUID(payload.sub)
    rows = (await session.execute(
        select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.created_at.desc())
    )).scalars().all()
    return success_response([
        {"id": str(c.id), "title": c.title, "video_id": str(c.video_id) if c.video_id else None, "created_at": c.created_at.isoformat()}
        for c in rows
    ])


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: UUID, payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    convo = await session.get(Conversation, conversation_id)
    if not convo or convo.user_id != UUID(payload.sub):
        raise HTTPException(404, "Conversation not found")
    # The user + assistant rows of one turn are committed in the same transaction,
    # so Postgres `now()` gives them an IDENTICAL created_at. Without a tiebreaker
    # the order is arbitrary and the assistant can sort before its user message
    # (renders the question below its answer on reload). Tiebreak user(0)<assistant(1).
    _role_order = case((Message.role == "user", 0), else_=1)
    msgs = (await session.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), _role_order)
    )).scalars().all()
    return success_response({
        "id": str(convo.id),
        "title": convo.title,
        "video_id": str(convo.video_id) if convo.video_id else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "thoughts": m.thoughts,
                "tool_calls": m.tool_calls,
                "image": m.image,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
    })


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.get(Conversation, conversation_id)
    if not convo or convo.user_id != UUID(payload.sub):
        raise HTTPException(404, "Conversation not found")
    # messages FK has no ON DELETE CASCADE — remove children explicitly.
    await session.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await session.delete(convo)
    await session.commit()
    return success_response({"deleted": True})
