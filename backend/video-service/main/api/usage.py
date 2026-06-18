"""Index-usage: minutes of video indexed this calendar month (derived, not recorded)."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.video import IndexingJob, Video

router = APIRouter(prefix="/api/v1/videos", tags=["usage"])


def current_month_start(now: datetime) -> datetime:
    # Naive UTC: the IndexingJob.completed_at / Video.created_at columns are
    # TIMESTAMP WITHOUT TIME ZONE, and asyncpg rejects comparing a naive column
    # to a tz-aware param ("can't subtract offset-naive and offset-aware").
    return now.astimezone(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )


def index_minutes_query(user_id: UUID, period_start: datetime) -> Select:
    """Sum of duration_s (seconds) over the user's videos whose indexing job
    completed in the period. Divide by 60 for minutes."""
    return (
        select(func.coalesce(func.sum(Video.duration_s), 0.0))
        .select_from(IndexingJob)
        .join(Video, Video.id == IndexingJob.video_id)
        .where(
            Video.user_id == user_id,
            IndexingJob.status == "completed",
            IndexingJob.completed_at >= period_start,
        )
    )


@router.get("/index-usage")
async def index_usage(
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    period_start = current_month_start(now)
    seconds = (await session.execute(index_minutes_query(UUID(payload.sub), period_start))).scalar_one()
    return success_response({
        "used_minutes": round(float(seconds) / 60, 2),
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
    })
