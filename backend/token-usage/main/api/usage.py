from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import TokenUsageLog
from main.models.usage import TokenUsage

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


@router.post("/log")
async def log_usage(body: TokenUsageLog, session: AsyncSession = Depends(get_session)):
    """Internal endpoint — called by agent-service after each LLM call."""
    row = TokenUsage(
        user_id=body.user_id,
        conversation_id=body.conversation_id,
        model=body.model,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
        cost_usd=body.cost_usd,
    )
    session.add(row)
    await session.commit()
    return success_response({"id": str(row.id)})


@router.get("/me")
async def my_usage(payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)):
    user_id = UUID(payload.sub)
    # Naive UTC: token_usage.created_at is TIMESTAMP WITHOUT TIME ZONE; asyncpg
    # rejects comparing a naive column to a tz-aware param.
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)

    daily = (await session.execute(
        select(
            func.date_trunc("day", TokenUsage.created_at).label("day"),
            func.sum(TokenUsage.prompt_tokens).label("prompt"),
            func.sum(TokenUsage.completion_tokens).label("completion"),
            func.sum(TokenUsage.cost_usd).label("cost"),
        )
        .where(TokenUsage.user_id == user_id, TokenUsage.created_at >= since)
        .group_by("day").order_by("day")
    )).all()

    return success_response({
        "days": [
            {"day": r.day.isoformat(), "prompt_tokens": int(r.prompt or 0), "completion_tokens": int(r.completion or 0), "cost_usd": float(r.cost or 0)}
            for r in daily
        ],
    })
