"""Billing API — subscription read, Stripe Checkout, and webhook receiver.

DEMO-ONLY billing. Drive entirely with Stripe TEST-mode keys (sk_test_...). No
card data ever touches this service: Stripe-hosted Checkout collects the card on
Stripe's domain, and we only persist the resulting subscription state delivered
back to us over the signed webhook. That keeps PCI scope at zero.
"""
from datetime import datetime, timezone
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

try:  # top-level export in modern stripe; fall back to the legacy module path
    from stripe import SignatureVerificationError
except ImportError:  # pragma: no cover
    from stripe.error import SignatureVerificationError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_admin, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.settings import get_base_settings
from main.models.subscription import Plan, Subscription, WebhookEvent

settings = get_base_settings()
stripe.api_key = settings.stripe_secret_key

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Which Stripe Price backs each self-serve plan (test mode). Only Developer is
# self-serve checkout; Free is the default, Enterprise is "talk to sales".
_PLAN_PRICE: dict[str, str] = {"developer": settings.stripe_price_developer}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
async def _get_or_create_subscription(session: AsyncSession, user_id: UUID) -> Subscription:
    sub = (
        await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, plan_id="free", status="active")
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
    return sub


def _plan_dict(plan: Plan | None) -> dict | None:
    if plan is None:
        return None
    return {
        "id": plan.id,
        "name": plan.name,
        "monthly_index_minutes": plan.monthly_index_minutes,
        "monthly_search_queries": plan.monthly_search_queries,
        "monthly_ground_calls": plan.monthly_ground_calls,
        "monthly_qa_calls": plan.monthly_qa_calls,
        "monthly_summary_calls": plan.monthly_summary_calls,
    }


def _user_id_from(metadata: dict | None, client_ref: str | None) -> UUID | None:
    raw = (metadata or {}).get("user_id") or client_ref
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# read endpoints
# --------------------------------------------------------------------------- #
@router.get("/plans")
async def list_plans(session: AsyncSession = Depends(get_session)):
    plans = (await session.execute(select(Plan).order_by(Plan.created_at))).scalars().all()
    return success_response({"plans": [_plan_dict(p) for p in plans]})


@router.get("/subscription")
async def my_subscription(
    payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    """Current caller's plan/status. Defaults to the seeded 'free' plan if the
    user has never subscribed."""
    user_id = UUID(payload.sub)
    sub = await _get_or_create_subscription(session, user_id)
    plan = (await session.execute(select(Plan).where(Plan.id == sub.plan_id))).scalar_one_or_none()
    return success_response(
        {
            "plan_id": sub.plan_id,
            "status": sub.status,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "stripe_customer_id": sub.stripe_customer_id,
            "plan": _plan_dict(plan),
        }
    )


@router.get("/invoices")
async def my_invoices(
    payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    """Billing history. This service keeps no Stripe-invoice store (plans can be set
    manually, with no checkout), so for a PAID plan we synthesize a short paid
    history for the caller — enough to populate the billing-history table in the
    demo. Free plan → no history."""
    from datetime import timedelta

    user_id = UUID(payload.sub)
    sub = await _get_or_create_subscription(session, user_id)
    plan = (await session.execute(select(Plan).where(Plan.id == sub.plan_id))).scalar_one_or_none()
    if not plan or plan.id == "free":
        return success_response({"invoices": []})
    now = datetime.now(timezone.utc)
    monthly = 22.00  # demo flat subscription fee for the paid plan
    invoices: list[dict] = []
    for i in range(1, 3):  # last two billing periods, most recent first
        mm, yy = now.month - i, now.year
        while mm <= 0:
            mm += 12
            yy -= 1
        p_start = datetime(yy, mm, 1, tzinfo=timezone.utc)
        nm, ny = (1, yy + 1) if mm == 12 else (mm + 1, yy)
        p_end = datetime(ny, nm, 1, tzinfo=timezone.utc) - timedelta(days=1)
        invoices.append(
            {
                "issued_at": p_start.isoformat(),
                "due_at": (p_start + timedelta(days=7)).isoformat(),
                "status": "paid",
                "total": monthly,
                "amount_paid": monthly,
                "currency": "usd",
                "period_start": p_start.date().isoformat(),
                "period_end": p_end.date().isoformat(),
                "invoice_url": "#",
                "receipt_url": "#",
                "usage_summary": f"{plan.name} plan",
            }
        )
    return success_response({"invoices": invoices})


# --------------------------------------------------------------------------- #
# checkout
# --------------------------------------------------------------------------- #
@router.post("/checkout")
async def create_checkout(
    payload: TokenPayload = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    """Create a Stripe Checkout Session for the Developer plan and return its
    hosted URL for the frontend to redirect the browser to."""
    if not settings.stripe_secret_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe is not configured (set STRIPE_SECRET_KEY)")
    price_id = _PLAN_PRICE.get("developer")
    if not price_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "No Stripe price configured (set STRIPE_PRICE_DEVELOPER)"
        )

    user_id = UUID(payload.sub)
    sub = await _get_or_create_subscription(session, user_id)

    # Lazily create + persist a Stripe Customer keyed to our user on first checkout.
    if not sub.stripe_customer_id:
        customer = await run_in_threadpool(
            stripe.Customer.create, email=payload.email, metadata={"user_id": str(user_id)}
        )
        sub.stripe_customer_id = customer["id"]
        await session.commit()

    checkout = await run_in_threadpool(
        stripe.checkout.Session.create,
        mode="subscription",
        customer=sub.stripe_customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        client_reference_id=str(user_id),
        metadata={"user_id": str(user_id)},
        subscription_data={"metadata": {"user_id": str(user_id)}},
    )
    return success_response({"url": checkout["url"], "session_id": checkout["id"]})


# --------------------------------------------------------------------------- #
# webhook (Stripe -> us). NO require_user: authenticity is the HMAC signature.
# --------------------------------------------------------------------------- #
@router.post("/webhooks")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook secret not configured")

    # MUST be the RAW request body — FastAPI's parsed JSON would change the bytes
    # and break the HMAC. Nginx forwards the body unmodified.
    payload_bytes = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload_bytes, sig_header, settings.stripe_webhook_secret)
    except ValueError as exc:  # malformed payload
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid payload: {exc}") from exc
    except SignatureVerificationError as exc:  # forged / wrong secret
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature") from exc

    # Idempotency: Stripe redelivers events; apply each event id at most once.
    event_id = event["id"]
    already = (
        await session.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
    ).scalar_one_or_none()
    if already is not None:
        return success_response({"status": "duplicate_ignored"})
    session.add(WebhookEvent(id=event_id, type=event["type"]))

    await _apply_event(session, event)
    await session.commit()
    return success_response({"status": "processed", "type": event["type"]})


async def _apply_event(session: AsyncSession, event: dict) -> None:
    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        user_id = _user_id_from(obj.get("metadata"), obj.get("client_reference_id"))
        if user_id:
            sub = await _get_or_create_subscription(session, user_id)
            sub.plan_id = "developer"
            sub.status = "active"
            sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
            sub.stripe_subscription_id = obj.get("subscription") or sub.stripe_subscription_id

    elif etype in ("customer.subscription.created", "customer.subscription.updated"):
        sub = await _resolve_subscription(session, obj)
        if sub:
            sub.stripe_subscription_id = obj.get("id") or sub.stripe_subscription_id
            sub.status = obj.get("status") or sub.status
            if obj.get("status") in ("active", "trialing"):
                sub.plan_id = "developer"
            cpe = obj.get("current_period_end")
            if cpe:
                sub.current_period_end = datetime.fromtimestamp(int(cpe), tz=timezone.utc)

    elif etype == "customer.subscription.deleted":
        sub = await _resolve_subscription(session, obj)
        if sub:
            sub.status = "canceled"
            sub.plan_id = "free"


async def _resolve_subscription(session: AsyncSession, obj: dict) -> Subscription | None:
    """Find the local Subscription for a Stripe subscription object, by user_id
    metadata first, then by stripe subscription/customer id."""
    user_id = _user_id_from(obj.get("metadata"), None)
    if user_id:
        return await _get_or_create_subscription(session, user_id)
    for col, val in ((Subscription.stripe_subscription_id, obj.get("id")), (Subscription.stripe_customer_id, obj.get("customer"))):
        if val:
            found = (await session.execute(select(Subscription).where(col == val))).scalar_one_or_none()
            if found:
                return found
    return None


# --------------------------------------------------------------------------- #
# admin: manual plan override (comps/demos). Coexists with Stripe test-mode —
# stripe ids are left untouched, so a later webhook may overwrite plan/status.
# --------------------------------------------------------------------------- #
class AdminPlanPatch(BaseModel):
    plan_id: str


@router.patch("/admin/subscription/{user_id}")
async def admin_set_plan(
    user_id: UUID,
    body: AdminPlanPatch,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    plan = (await session.execute(select(Plan).where(Plan.id == body.plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown plan: {body.plan_id}")
    sub = await _get_or_create_subscription(session, user_id)
    sub.plan_id = plan.id
    sub.status = "active"
    await session.commit()
    return success_response({"user_id": str(user_id), "plan_id": sub.plan_id, "status": sub.status})


# --------------------------------------------------------------------------- #
# admin: edit a plan's name + monthly quotas (null = unlimited). Stripe price is
# left untouched. Partial — only the fields sent are changed.
# --------------------------------------------------------------------------- #
class PlanUpdate(BaseModel):
    name: str | None = None
    monthly_index_minutes: int | None = None
    monthly_search_queries: int | None = None
    monthly_ground_calls: int | None = None
    monthly_qa_calls: int | None = None
    monthly_summary_calls: int | None = None


def _plan_dict(p: Plan) -> dict:
    return {
        "id": p.id, "name": p.name,
        "monthly_index_minutes": p.monthly_index_minutes,
        "monthly_search_queries": p.monthly_search_queries,
        "monthly_ground_calls": p.monthly_ground_calls,
        "monthly_qa_calls": p.monthly_qa_calls,
        "monthly_summary_calls": p.monthly_summary_calls,
    }


@router.patch("/admin/plans/{plan_id}")
async def admin_update_plan(
    plan_id: str,
    body: PlanUpdate,
    payload: TokenPayload = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown plan: {plan_id}")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    await session.commit()
    return success_response(_plan_dict(plan))
