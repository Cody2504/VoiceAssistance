"""add golden_id + editable ground-truth + predicted_args to eval_cases

Enables per-case Edit (expected tool/args/answer) and re-run selection by
golden id. Additive + nullable — safe on existing rows.

Revision ID: 0004_eval_case_groundtruth
Revises: 0003_eval_tables
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_eval_case_groundtruth"
down_revision = "0003_eval_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eval_cases", sa.Column("golden_id", sa.String(64), nullable=True))
    op.add_column("eval_cases", sa.Column("expected_args", JSONB(), nullable=True))
    op.add_column("eval_cases", sa.Column("reference_answer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_cases", "reference_answer")
    op.drop_column("eval_cases", "expected_args")
    op.drop_column("eval_cases", "golden_id")
