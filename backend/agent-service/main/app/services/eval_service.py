"""Drive the agent_eval harness from the app + persist results.

Thin layer over agent_eval: load goldens -> run_eval -> aggregate -> persist.
Admin runs are infrequent + one-at-a-time, so the run executes as an in-process
background task (scheduled by start_run); the heavy synchronous judge work is
offloaded to a worker thread so the FastAPI event loop stays responsive.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.db import get_sessionmaker
from main.app.db.models.eval import EvalCase, EvalRun

# NOTE: agent_eval (+ its deepeval dependency) is the dev/eval harness and is NOT
# shipped in the production agent-service image. It is imported LAZILY inside the
# run/seed paths only, so the read-only dashboard endpoints + app boot never need
# it. Runs/seeding execute in an environment that has the harness (a dev venv);
# the results are read back from the DB here.

log = logging.getLogger(__name__)

GOLDENS_DIR = Path(__file__).resolve().parents[3] / "agent_eval" / "goldens"


class RunInProgressError(Exception):
    """A run is already executing; only one at a time is allowed."""


def _sanitize_deepeval_env() -> None:
    """Prep the process env for the deepeval-backed harness.

    1. deepeval 4.x reads several *_ENDPOINT / *_BASE_URL env vars as pydantic
       AnyUrl; pydantic 2.13 rejects an empty string (vs unset), and our compose
       sets some of these to "" (e.g. AZURE_OPENAI_ENDPOINT) — which crashes
       deepeval's settings on import. Drop the empties.
    2. Route the deepeval JUDGE through OpenRouter when configured: the plain
       OpenAI key is commonly out of quota, while OpenRouter (what the agent uses)
       has credits. deepeval's judge reads OPENAI_API_KEY/OPENAI_BASE_URL, so point
       them at OpenRouter + use an OpenRouter-qualified judge model. Safe: the agent
       graph passes its OpenRouter creds explicitly, so chat is unaffected.
    """
    import os
    for k in (
        "AZURE_OPENAI_ENDPOINT", "LITELLM_API_BASE", "LITELLM_PROXY_API_BASE",
        "LOCAL_MODEL_BASE_URL", "PORTKEY_BASE_URL", "OPENROUTER_BASE_URL",
        "LOCAL_EMBEDDING_BASE_URL", "CONFIDENT_OTEL_URL", "CONFIDENT_BASE_URL",
    ):
        if os.environ.get(k) == "":
            os.environ.pop(k, None)
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        os.environ["OPENAI_API_KEY"] = openrouter_key
        os.environ["OPENAI_BASE_URL"] = (
            os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1")
        os.environ.setdefault("EVAL_JUDGE_MODEL", "openai/gpt-4.1-mini")


def compute_summary(scores: "list") -> dict:
    from agent_eval.report import aggregate
    from agent_eval.thresholds import assert_thresholds
    agg = aggregate(scores)
    breaches = assert_thresholds(agg)
    return {
        "n": agg.n,
        "routing_f1_macro": agg.routing_f1_macro,
        "arg_correctness_rate": agg.arg_correctness_rate,
        "mean_task_completion": agg.mean_task_completion,
        "mean_answer_relevancy": agg.mean_answer_relevancy,
        "passed": sum(1 for s in scores if s.tool_correct and s.arg_ok is not False),
        "thresholds_pass": not breaches,
        "breaches": breaches,
    }


def build_eval_cases(
    run_id, kind: str, scores: "list", queries: dict[str, str], goldens_by_id: dict | None = None
) -> list[EvalCase]:
    """Pure: map CaseScores to unsaved EvalCase rows, enriched with the golden's
    expected args + reference answer (the editable ground truth) when available."""
    goldens_by_id = goldens_by_id or {}
    cases = []
    for sc in scores:
        g = goldens_by_id.get(sc.golden_id)
        exp_args = g.expected_tools[0].args if (g and g.expected_tools) else None
        cases.append(EvalCase(
            run_id=run_id,
            query=queries.get(sc.golden_id, sc.golden_id),
            source=kind,
            golden_id=sc.golden_id,
            expected_tool=sc.expected_tool,
            expected_args=exp_args,
            reference_answer=(g.reference_answer if g else None),
            predicted_tool=sc.predicted_tool,
            tool_correct=sc.tool_correct,
            arg_ok=sc.arg_ok,
            task_completion=sc.task_completion,
            answer_relevancy=sc.answer_relevancy,
        ))
    return cases


async def persist_results(
    session: AsyncSession, run: EvalRun, scores: "list", queries: dict[str, str],
    goldens_by_id: dict | None = None,
) -> None:
    """Write one EvalCase per score and finalise the run (summary + status=done)."""
    for case in build_eval_cases(run.id, run.kind, scores, queries, goldens_by_id):
        session.add(case)
    run.summary = compute_summary(scores)
    run.status = "done"
    run.finished_at = datetime.now(timezone.utc)


def _run_blocking(goldens, *, live: bool, judge: bool) -> "list":
    """Run the whole eval in a private event loop (called inside a worker thread)."""
    from agent_eval.run_eval import run_eval
    return asyncio.run(run_eval(goldens, live=live, judge=judge))


async def execute_run(run_id: UUID, *, kind: str, mode: str, judge: bool,
                      limit: int | None, tools: set[str] | None,
                      golden_ids: set[str] | None = None) -> None:
    """Background job: load goldens, run the harness, persist, finalise.

    The agent_eval harness is imported lazily here — it is absent from the
    production image, so this path only succeeds where the harness is installed.
    """
    _sanitize_deepeval_env()
    from agent_eval.goldens_loader import load_goldens
    factory = get_sessionmaker()
    try:
        goldens = load_goldens(GOLDENS_DIR, tools=tools)
        if golden_ids:                       # "run selected" — only the chosen cases
            goldens = [g for g in goldens if g.id in golden_ids]
        if limit:
            goldens = goldens[:limit]
        queries = {g.id: g.query for g in goldens}
        goldens_by_id = {g.id: g for g in goldens}
        scores = await asyncio.to_thread(_run_blocking, goldens, live=(mode == "live"), judge=judge)
        async with factory() as session:
            run = await session.get(EvalRun, run_id)
            await persist_results(session, run, scores, queries, goldens_by_id)
            await session.commit()
        log.info("eval run %s done (%d cases)", run_id, len(scores))
    except Exception as exc:  # noqa: BLE001 — record failure, never crash the loop
        log.exception("eval run %s failed", run_id)
        async with factory() as session:
            run = await session.get(EvalRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"
                run.finished_at = datetime.now(timezone.utc)
                await session.commit()


async def start_run(session: AsyncSession, *, kind: str, mode: str, judge: bool,
                    limit: int | None, tools: set[str] | None, created_by: UUID,
                    golden_ids: set[str] | None = None) -> EvalRun:
    """Create the run row and schedule its background execution. One at a time."""
    running = (await session.execute(
        select(EvalRun).where(EvalRun.status == "running"))).scalars().first()
    if running is not None:
        raise RunInProgressError()
    run = EvalRun(kind=kind, mode=mode, judge_on=judge, status="running", created_by=created_by)
    session.add(run)
    await session.commit()
    asyncio.create_task(execute_run(
        run.id, kind=kind, mode=mode, judge=judge, limit=limit, tools=tools, golden_ids=golden_ids))
    return run
