"""Seed one curated eval run so the admin dashboard has content.

Usage (from backend/agent-service, with the service .env loaded so OPENAI_API_KEY
+ Postgres vars are set):
    PYTHONPATH=..:.:main python -m scripts.seed_eval_run            # fake mode + judge
    PYTHONPATH=..:.:main python -m scripts.seed_eval_run --no-judge # routing only, no LLM
"""
import argparse
import asyncio
from uuid import UUID

from agent_eval.goldens_loader import load_goldens
from agent_eval.run_eval import run_eval
from cm_shared.db import get_sessionmaker
from main.app.db.models.eval import EvalRun
from main.app.services.eval_service import GOLDENS_DIR, persist_results

SEED_ADMIN = UUID("00000000-0000-0000-0000-000000000000")  # system/seed author


async def main(judge: bool, limit: int | None = None) -> None:
    goldens = load_goldens(GOLDENS_DIR)
    if limit:
        goldens = goldens[:limit]
    queries = {g.id: g.query for g in goldens}
    goldens_by_id = {g.id: g for g in goldens}
    scores = await run_eval(goldens, live=False, judge=judge)
    factory = get_sessionmaker()
    async with factory() as session:
        run = EvalRun(kind="curated", mode="fake", judge_on=judge,
                      status="running", created_by=SEED_ADMIN)
        session.add(run)
        await session.flush()
        await persist_results(session, run, scores, queries, goldens_by_id)
        await session.commit()
        print(f"Seeded curated run {run.id}: {run.summary}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    asyncio.run(main(judge=not args.no_judge, limit=args.limit))
