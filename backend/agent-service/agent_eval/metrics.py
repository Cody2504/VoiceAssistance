"""deepeval metric wiring + deterministic scoring. gpt-4.1-mini is the default LLM judge."""
import logging
import os
from dataclasses import dataclass

from deepeval.metrics import (
    AnswerRelevancyMetric,
    TaskCompletionMetric,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, ToolCall

from agent_eval.argcheck import check_arg_constraints
from agent_eval.harness import CaseRun

log = logging.getLogger(__name__)

JUDGE_MODEL = "gpt-4.1-mini"  # default judge; override with EVAL_JUDGE_MODEL (e.g. openai/gpt-4.1-mini on OpenRouter)


def _judge_model() -> str:
    return os.getenv("EVAL_JUDGE_MODEL") or JUDGE_MODEL


@dataclass
class CaseScore:
    golden_id: str
    expected_tool: str
    predicted_tool: str
    tool_correct: bool
    arg_ok: bool | None
    task_completion: float | None = None
    answer_relevancy: float | None = None


def _router_calls(run: CaseRun):
    return [c for c in run.tool_calls if not c.forced]


def predicted_primary(run: CaseRun) -> str:
    rc = _router_calls(run)
    return rc[0].name if rc else "(none)"


def _build_test_case(run: CaseRun) -> LLMTestCase:
    expected = [ToolCall(name=t.name) for t in run.golden.expected_tools]
    actual = [ToolCall(name=c.name) for c in _router_calls(run)]
    return LLMTestCase(
        input=run.golden.query,
        actual_output=run.final_answer or "",
        expected_output=run.golden.reference_answer,
        tools_called=actual,
        expected_tools=expected,
        retrieval_context=[run.final_answer or ""],
    )


def score_tool_correctness(run: CaseRun) -> float:
    metric = ToolCorrectnessMetric()
    metric.measure(_build_test_case(run))
    return float(metric.score)


def score_arg_correctness(run: CaseRun) -> bool | None:
    """True/False only when the expected primary tool was actually called."""
    if not run.golden.expected_tools:
        return None
    primary = run.golden.primary_tool
    match = next((c for c in _router_calls(run) if c.name == primary), None)
    if match is None:
        return None
    return check_arg_constraints(match, run.golden.expected_tools[0].args).passed


def _safe_measure(metric, tc) -> float | None:
    """Run a judged metric; on any failure (timeout, rate limit, parse) return None
    so one flaky judge call never aborts the whole eval."""
    try:
        metric.measure(tc)
        return float(metric.score)
    except Exception as exc:  # noqa: BLE001 — judge calls fail in many ways
        log.warning("judge metric %s failed: %s: %s", type(metric).__name__, type(exc).__name__, exc)
        return None


def score_judged(run: CaseRun, model: str | None = None) -> dict:
    model = model or _judge_model()
    tc = _build_test_case(run)
    return {
        "task_completion": _safe_measure(TaskCompletionMetric(model=model), tc),
        "answer_relevancy": _safe_measure(AnswerRelevancyMetric(model=model), tc),
    }


def score_case(run: CaseRun, *, judge: bool = True) -> CaseScore:
    judged = score_judged(run) if judge else {}
    return CaseScore(
        golden_id=run.golden.id,
        expected_tool=run.golden.primary_tool,
        predicted_tool=predicted_primary(run),
        tool_correct=score_tool_correctness(run) >= 1.0,
        arg_ok=score_arg_correctness(run),
        task_completion=judged.get("task_completion"),
        answer_relevancy=judged.get("answer_relevancy"),
    )
