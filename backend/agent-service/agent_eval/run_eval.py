"""CLI: run the goldens through the agent, score, and write a report."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

from agent_eval.goldens_loader import load_goldens
from agent_eval.harness import run_case
from agent_eval.metrics import CaseScore, score_case
from agent_eval.report import aggregate, render_csv, render_markdown

GOLDENS_DIR = Path(__file__).parent / "goldens"


async def run_eval(goldens, *, live=False, judge=True, runner=run_case, scorer=score_case):
    scores = []
    total = len(goldens)
    for i, g in enumerate(goldens, 1):
        try:
            run = await runner(g, live=live)
            s = scorer(run, judge=judge)
            scores.append(s)
            print(f"[{i}/{total}] {g.id}: {g.primary_tool} -> {s.predicted_tool}", file=sys.stderr, flush=True)
        except Exception as exc:  # noqa: BLE001 — one bad case must not abort the run
            print(f"[{i}/{total}] [warn] case {g.id} failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            scores.append(CaseScore(g.id, g.primary_tool, "(error)", False, None, None, None))
    return scores


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Agent tool-trajectory eval")
    p.add_argument("--live", action="store_true", help="hit the real video-service instead of fakes")
    p.add_argument("--no-judge", action="store_true", help="skip GPT-5 judged metrics (routing/args only)")
    p.add_argument("--tools", default=None, help="comma-separated primary tools to filter goldens")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", default="eval_report.md")
    p.add_argument("--env-file", default=None,
                   help="load this .env into the environment first (agent LLM settings + judge OPENAI_API_KEY)")
    p.add_argument("--openrouter", action="store_true",
                   help="route router/reflect/judge through OpenRouter using OPENROUTER_API_KEY "
                        "(router=openai/gpt-4.1, reflect=openai/gpt-4o-mini, judge=openai/gpt-4.1-mini)")
    return p.parse_args(argv)


def _apply_openrouter() -> None:
    """Point both LangChain (agent) and deepeval (judge) at OpenRouter via env.
    OpenRouter is OpenAI-compatible; LangChain reads OPENAI_API_BASE, the openai SDK
    (deepeval) reads OPENAI_BASE_URL. Models are forced to OpenRouter ids (override the
    .env's gpt-4o/gpt-4o-mini)."""
    orkey = os.environ.get("OPENROUTER_API_KEY")
    if not orkey:
        raise SystemExit("--openrouter needs OPENROUTER_API_KEY (set it, or pass --env-file with it)")
    os.environ["OPENAI_API_KEY"] = orkey
    os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
    os.environ["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
    os.environ["OPENAI_PLANNER_MODEL"] = "openai/gpt-4.1"        # router
    os.environ["OPENAI_WORKER_MODEL"] = "openai/gpt-4o-mini"     # reflect
    os.environ.setdefault("EVAL_JUDGE_MODEL", "openai/gpt-4.1-mini")  # judge


def main(argv=None):
    args = _parse_args(argv)
    if args.env_file:
        from dotenv import dotenv_values
        # Set only NON-empty values: an empty AZURE_OPENAI_ENDPOINT="" in the file
        # otherwise reaches deepeval's settings, which rejects it as an invalid URL.
        for k, v in dotenv_values(args.env_file).items():
            if v:
                os.environ.setdefault(k, v)
    if args.openrouter:
        _apply_openrouter()
    tools = set(args.tools.split(",")) if args.tools else None
    goldens = load_goldens(GOLDENS_DIR, tools=tools)
    if args.limit:
        goldens = goldens[: args.limit]
    scores = asyncio.run(run_eval(goldens, live=args.live, judge=not args.no_judge))
    agg = aggregate(scores)
    out = Path(args.out)
    out.write_text(render_markdown(agg))
    out.with_suffix(".csv").write_text(render_csv(scores))
    print(render_markdown(agg))
    print(f"\nReport written to {out} and {out.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
