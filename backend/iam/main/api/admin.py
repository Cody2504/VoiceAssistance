"""Admin console endpoints — aggregated reads over the shared DB plus
iam-owned user mutations (role / is_active). All guarded by require_admin.

Reads deliberately reference other services' tables (subscriptions, videos,
conversations, token_usage): every service shares the one `jockey` Postgres,
so one SQL round trip beats four HTTP fan-outs. If a sibling migration renames
a column, these queries are the place to fix.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_admin
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.api.admin_rules import validate_admin_patch
from main.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Per-user aggregate columns shared by the list and detail queries.
_USER_ROW_SQL = """
    u.id, u.email, u.role, u.is_active, u.created_at,
    coalesce(s.plan_id, 'free')  AS plan_id,
    s.status                     AS sub_status,
    s.stripe_customer_id         AS stripe_customer_id,
    s.current_period_end         AS current_period_end,
    (SELECT count(*) FROM videos v WHERE v.user_id = u.id)                       AS video_count,
    (SELECT coalesce(sum(v.size_bytes), 0) FROM videos v WHERE v.user_id = u.id) AS storage_bytes,
    (SELECT coalesce(sum(v.duration_s), 0) FROM videos v WHERE v.user_id = u.id) AS duration_s,
    (SELECT count(*) FROM conversations c WHERE c.user_id = u.id)                AS conversation_count,
    (SELECT coalesce(sum(t.cost_usd), 0) FROM token_usage t
       WHERE t.user_id = u.id
         AND t.created_at >= now() - interval '30 days')                         AS cost_usd_30d
"""


def _user_row_dict(r) -> dict:
    return {
        "id": str(r.id),
        "email": r.email,
        "role": r.role,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat(),
        "plan_id": r.plan_id,
        "sub_status": r.sub_status,
        "video_count": r.video_count,
        "storage_bytes": int(r.storage_bytes),
        "duration_s": float(r.duration_s),
        "conversation_count": r.conversation_count,
        "cost_usd_30d": float(r.cost_usd_30d),
    }


@router.get("/stats")
async def platform_stats(
    payload: TokenPayload = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    totals = (await session.execute(text("""
        SELECT
          (SELECT count(*) FROM users)                                  AS users,
          (SELECT count(*) FROM videos)                                 AS videos,
          (SELECT coalesce(sum(size_bytes), 0) FROM videos)             AS storage_bytes,
          (SELECT coalesce(sum(duration_s), 0) / 60.0 FROM videos)      AS video_minutes,
          (SELECT count(*) FROM conversations)                          AS conversations,
          (SELECT coalesce(sum(cost_usd), 0) FROM token_usage)          AS cost_usd_total,
          (SELECT coalesce(sum(cost_usd), 0) FROM token_usage
             WHERE created_at >= now() - interval '30 days')            AS cost_usd_30d
    """))).one()

    # Users without a subscription row are implicitly on the seeded free plan.
    plan_rows = (await session.execute(text(
        "SELECT plan_id, count(*) AS n FROM subscriptions GROUP BY plan_id"
    ))).all()
    users_per_plan = {r.plan_id: r.n for r in plan_rows}
    users_per_plan["free"] = users_per_plan.get("free", 0) + (totals.users - sum(r.n for r in plan_rows))

    signups = (await session.execute(text("""
        SELECT date_trunc('day', created_at)::date AS day, count(*) AS count
        FROM users WHERE created_at >= now() - interval '30 days'
        GROUP BY 1 ORDER BY 1
    """))).all()
    cost = (await session.execute(text("""
        SELECT date_trunc('day', created_at)::date AS day, coalesce(sum(cost_usd), 0) AS cost_usd
        FROM token_usage WHERE created_at >= now() - interval '30 days'
        GROUP BY 1 ORDER BY 1
    """))).all()

    return success_response({
        "users": totals.users,
        "videos": totals.videos,
        "storage_bytes": int(totals.storage_bytes),
        "video_minutes": float(totals.video_minutes),
        "conversations": totals.conversations,
        "cost_usd_30d": float(totals.cost_usd_30d),
        "cost_usd_total": float(totals.cost_usd_total),
        "users_per_plan": users_per_plan,
        "signups_daily": [{"day": r.day.isoformat(), "count": r.count} for r in signups],
        "cost_daily": [{"day": r.day.isoformat(), "cost_usd": float(r.cost_usd)} for r in cost],
    })


@router.get("/users")
async def list_users(
    search: str = "",
    page: int = 1,
    page_size: int = 20,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    params = {"search": search.strip(), "limit": page_size, "offset": (page - 1) * page_size}

    total = (await session.execute(text(
        "SELECT count(*) FROM users u WHERE (:search = '' OR u.email ILIKE '%' || :search || '%')"
    ), params)).scalar_one()

    rows = (await session.execute(text(f"""
        SELECT {_USER_ROW_SQL}
        FROM users u LEFT JOIN subscriptions s ON s.user_id = u.id
        WHERE (:search = '' OR u.email ILIKE '%' || :search || '%')
        ORDER BY u.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)).all()

    return success_response({"total": total, "items": [_user_row_dict(r) for r in rows]})


@router.get("/users/{user_id}")
async def user_detail(
    user_id: UUID,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    row = (await session.execute(text(f"""
        SELECT {_USER_ROW_SQL}
        FROM users u LEFT JOIN subscriptions s ON s.user_id = u.id
        WHERE u.id = :uid
    """), {"uid": str(user_id)})).one_or_none()
    if row is None:
        raise HTTPException(404, "User not found")

    usage = (await session.execute(text("""
        SELECT date_trunc('day', created_at)::date AS day,
               coalesce(sum(prompt_tokens), 0)     AS prompt_tokens,
               coalesce(sum(completion_tokens), 0) AS completion_tokens,
               coalesce(sum(cost_usd), 0)          AS cost_usd
        FROM token_usage
        WHERE user_id = :uid AND created_at >= now() - interval '30 days'
        GROUP BY 1 ORDER BY 1
    """), {"uid": str(user_id)})).all()

    out = _user_row_dict(row)
    out["stripe_customer_id"] = row.stripe_customer_id
    out["current_period_end"] = row.current_period_end.isoformat() if row.current_period_end else None
    out["usage_daily"] = [
        {
            "day": r.day.isoformat(),
            "prompt_tokens": int(r.prompt_tokens),
            "completion_tokens": int(r.completion_tokens),
            "cost_usd": float(r.cost_usd),
        }
        for r in usage
    ]
    return success_response(out)


class AdminUserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: UUID,
    body: AdminUserPatch,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    err = validate_admin_patch(payload.sub, str(user_id), body.role, body.is_active)
    if err:
        raise HTTPException(err[0], err[1])

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await session.commit()
    return success_response({
        "id": str(user.id), "email": user.email, "role": user.role, "is_active": user.is_active,
    })
