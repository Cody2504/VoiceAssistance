from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from cm_shared.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)          # curated|harvested|custom
    mode: Mapped[str] = mapped_column(String(8), nullable=False)           # fake|live
    judge_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running|done|failed
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    # Python-side default only; the DB-side `server_default=now()` lives in the
    # migration (production Postgres). Keeping server_default off the model lets
    # `create_all` render valid DDL on SQLite for tests. timezone=True matches the
    # migration's TIMESTAMP(timezone=True) so asyncpg accepts the tz-aware values.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # nullable: filled when the run finishes. JSON on sqlite for tests.
    summary: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True)


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("eval_runs.id"), index=True, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)        # curated|harvested|custom
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    golden_id: Mapped[str | None] = mapped_column(String(64), nullable=True)   # which golden (for re-run selection)
    expected_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_args: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True)             # editable ground truth
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)  # editable expected answer
    predicted_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    arg_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    task_completion: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevancy: Mapped[float | None] = mapped_column(Float, nullable=True)
