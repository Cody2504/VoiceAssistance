"""Subclass of jockey.jockey_graph.Jockey that uses our rewired stirrups (HTTP to video-service)."""
import os

from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

# Import the source-of-truth Jockey class. We only override _build_core_workers.
from jockey.jockey_graph import Jockey  # type: ignore

from main.agent.app import build_llms
from main.agent.stirrups import all_workers


PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


class JockeyLocal(Jockey):
    """Override worker construction to use our rewired stirrups."""

    def _build_core_workers(self):
        return all_workers(self.worker_llm)


def build_jockey_agent():
    """Compile the LangGraph for this service. Memory is in-process aiosqlite."""
    planner_llm, supervisor_llm, worker_llm = build_llms()

    planner_prompt = _read(os.path.join(PROMPTS_DIR, "planner.md"))
    supervisor_prompt = _read(os.path.join(PROMPTS_DIR, "supervisor.md"))

    graph = JockeyLocal(
        planner_llm=planner_llm,
        planner_prompt=planner_prompt,
        supervisor_llm=supervisor_llm,
        supervisor_prompt=supervisor_prompt,
        worker_llm=worker_llm,
    )

    checkpointer = AsyncSqliteSaver.from_conn_string(":memory:")
    return graph.compile(checkpointer=checkpointer)
