"""create eval_runs + eval_cases

Persists evaluation runs of the agent_eval harness and their per-query results
so the admin Evaluation dashboard can browse run history. Additive — safe on
existing rows.

Revision ID: 0003_eval_tables
Revises: 0002_message_image
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003_eval_tables"
down_revision = "0002_message_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("judge_on", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("summary", JSONB(), nullable=True),
    )
    op.create_index("ix_eval_runs_created_by", "eval_runs", ["created_by"])

    op.create_table(
        "eval_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("eval_runs.id"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=True),
        sa.Column("expected_tool", sa.String(64), nullable=True),
        sa.Column("predicted_tool", sa.String(64), nullable=True),
        sa.Column("tool_correct", sa.Boolean(), nullable=True),
        sa.Column("arg_ok", sa.Boolean(), nullable=True),
        sa.Column("task_completion", sa.Float(), nullable=True),
        sa.Column("answer_relevancy", sa.Float(), nullable=True),
    )
    op.create_index("ix_eval_cases_run_id", "eval_cases", ["run_id"])


def downgrade() -> None:
    op.drop_table("eval_cases")
    op.drop_table("eval_runs")
