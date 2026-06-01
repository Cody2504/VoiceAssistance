from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from cm_shared.db import Base


class Plan(Base):
    """A subscription tier. Ids ('free' | 'developer' | 'enterprise') match the
    frontend pricing source of truth (frontend/src/pages/pricing/pricingData.ts
    TIERS). Monthly caps mirror that file's ITEMS.freeMonthly; NULL = unlimited."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Informational — the live Stripe price id used at checkout is read from
    # settings.stripe_price_developer (env-specific), not from this column.
    stripe_price_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    monthly_index_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_search_queries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_ground_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_qa_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_summary_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class Subscription(Base):
    """One row per user (the system is user-scoped — no org/account concept).
    user_id is an FK-by-convention to iam users.id (TokenPayload.sub)."""

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(32), ForeignKey("plans.id"), nullable=False, server_default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Mirrors Stripe: active | trialing | past_due | canceled | incomplete
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class WebhookEvent(Base):
    """Idempotency ledger — Stripe redelivers events, so we record each event.id
    and skip ones we've already applied."""

    __tablename__ = "billing_webhook_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Stripe evt_...
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
