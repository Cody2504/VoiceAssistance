"""SSE chat endpoint — maps LangGraph events to the protocol the frontend expects:
    event: thought|tool_call|tool_result|message|end
"""
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.schemas import ChatMessageIn
from main.agent.jockey_graph import build_jockey_agent
from main.models.conversation import Conversation, Message

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


_AGENT = None


def get_agent():
    """Lazy-init so module import is cheap (Alembic, tests, etc.)."""
    global _AGENT
    if _AGENT is None:
        _AGENT = build_jockey_agent()
    return _AGENT


async def _event_stream(agent, user_id: UUID, conversation_id: UUID, video_ids: list[UUID] | None, message: str, session: AsyncSession):
    """Yield SSE-formatted events from LangGraph's astream_events output."""
    final_text_parts: list[str] = []
    thoughts: list[dict] = []
    tool_calls: list[dict] = []

    # Inject attached-video context so the planner knows which videos are in scope.
    full_message = message
    if video_ids:
        full_message = f"[Attached videos: {', '.join(str(v) for v in video_ids)}]\n\n{message}"

    input_state = {"chat_history": [HumanMessage(content=full_message)]}
    config = {"configurable": {"thread_id": str(conversation_id)}}

    async for ev in agent.astream_events(input_state, config=config, version="v2"):
        kind = ev.get("event")
        tags = ev.get("tags") or []
        data = ev.get("data") or {}

        if kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk and getattr(chunk, "content", None):
                if "reflect" in tags:
                    final_text_parts.append(chunk.content)
                    yield {"event": "message", "data": json.dumps({"delta": chunk.content})}
                elif "planner" in tags or "supervisor" in tags or "instructor" in tags:
                    thoughts.append({"agent": (tags[-1] if tags else "agent"), "delta": chunk.content})
                    yield {"event": "thought", "data": json.dumps({"agent": tags[-1] if tags else "agent", "delta": chunk.content})}

        elif kind == "on_tool_start":
            tc = {"tool": ev.get("name"), "args": data.get("input")}
            tool_calls.append(tc)
            yield {"event": "tool_call", "data": json.dumps(tc)}

        elif kind == "on_tool_end":
            payload = {"tool": ev.get("name"), "result": data.get("output")}
            yield {"event": "tool_result", "data": json.dumps(payload, default=str)}

    # Persist user + assistant turns
    msg_user = Message(conversation_id=conversation_id, role="user", content=message)
    msg_assistant = Message(
        conversation_id=conversation_id,
        role="assistant",
        content="".join(final_text_parts),
        thoughts=thoughts or None,
        tool_calls=tool_calls or None,
    )
    session.add_all([msg_user, msg_assistant])
    await session.commit()

    yield {"event": "end", "data": json.dumps({"conversation_id": str(conversation_id), "message_id": str(msg_assistant.id)})}


@router.post("/stream")
async def stream(
    body: ChatMessageIn,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)

    # Accept either video_ids[] (preferred, supports multi-attach) or singular video_id.
    video_ids = body.video_ids or ([body.video_id] if body.video_id else None)
    primary_video = video_ids[0] if video_ids else None

    if body.conversation_id:
        convo = await session.get(Conversation, body.conversation_id)
        if not convo or convo.user_id != user_id:
            raise HTTPException(404, "Conversation not found")
    else:
        convo = Conversation(id=uuid4(), user_id=user_id, video_id=primary_video, title=body.message[:64])
        session.add(convo)
        await session.commit()

    agent = get_agent()
    return EventSourceResponse(
        _event_stream(agent, user_id, convo.id, video_ids, body.message, session)
    )
