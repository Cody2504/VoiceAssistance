"""Aggregate CaseScores into per-tool metrics + a markdown/CSV report."""
from dataclasses import dataclass, field

from agent_eval.metrics import CaseScore


@dataclass
class Aggregate:
    n: int
    routing_precision: dict
    routing_recall: dict
    routing_f1_macro: float
    confusion: dict
    arg_correctness_rate: float | None
    mean_task_completion: float | None
    mean_answer_relevancy: float | None
    failures: list = field(default_factory=list)


def aggregate(scores: list[CaseScore]) -> Aggregate:
    confusion: dict = {}
    tools: set = set()
    for s in scores:
        key = (s.expected_tool, s.predicted_tool)
        confusion[key] = confusion.get(key, 0) + 1
        tools.update([s.expected_tool, s.predicted_tool])

    precision: dict = {}
    recall: dict = {}
    f1s: list = []
    for t in sorted(tools):
        tp = confusion.get((t, t), 0)
        fp = sum(c for (e, p), c in confusion.items() if p == t and e != t)
        fn = sum(c for (e, p), c in confusion.items() if e == t and p != t)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        precision[t] = prec
        recall[t] = rec
        if (tp + fp + fn) > 0:
            f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    f1_macro = sum(f1s) / len(f1s) if f1s else 0.0

    arg_vals = [s.arg_ok for s in scores if s.arg_ok is not None]
    arg_rate = (sum(1 for a in arg_vals if a) / len(arg_vals)) if arg_vals else None

    tcs = [s.task_completion for s in scores if s.task_completion is not None]
    ars = [s.answer_relevancy for s in scores if s.answer_relevancy is not None]
    mean_tc = sum(tcs) / len(tcs) if tcs else None
    mean_ar = sum(ars) / len(ars) if ars else None

    failures = [s for s in scores if (not s.tool_correct) or (s.arg_ok is False)]
    return Aggregate(
        n=len(scores),
        routing_precision=precision,
        routing_recall=recall,
        routing_f1_macro=f1_macro,
        confusion=confusion,
        arg_correctness_rate=arg_rate,
        mean_task_completion=mean_tc,
        mean_answer_relevancy=mean_ar,
        failures=failures,
    )


def render_markdown(agg: Aggregate) -> str:
    lines = [f"# Agent Tool-Trajectory Eval — {agg.n} cases", ""]
    lines.append(f"- Routing F1 (macro): **{agg.routing_f1_macro:.3f}**")
    if agg.arg_correctness_rate is not None:
        lines.append(f"- Argument correctness: **{agg.arg_correctness_rate:.3f}**")
    if agg.mean_task_completion is not None:
        lines.append(f"- Mean TaskCompletion: **{agg.mean_task_completion:.3f}**")
    if agg.mean_answer_relevancy is not None:
        lines.append(f"- Mean AnswerRelevancy: **{agg.mean_answer_relevancy:.3f}**")
    lines += ["", "## Per-tool routing", "", "| tool | precision | recall |", "|---|---|---|"]
    for t in sorted(agg.routing_precision):
        lines.append(f"| {t} | {agg.routing_precision[t]:.2f} | {agg.routing_recall[t]:.2f} |")
    lines += ["", "## Confusion (expected -> predicted)", "", "| expected | predicted | n |", "|---|---|---|"]
    for (e, p), c in sorted(agg.confusion.items()):
        lines.append(f"| {e} | {p} | {c} |")
    if agg.failures:
        lines += ["", "## Failures", "", "| id | expected | predicted | tool_ok | arg_ok |", "|---|---|---|---|---|"]
        for s in agg.failures:
            lines.append(f"| {s.golden_id} | {s.expected_tool} | {s.predicted_tool} | {s.tool_correct} | {s.arg_ok} |")
    return "\n".join(lines) + "\n"


def render_csv(scores: list[CaseScore]) -> str:
    rows = ["golden_id,expected_tool,predicted_tool,tool_correct,arg_ok,task_completion,answer_relevancy"]
    for s in scores:
        rows.append(
            f"{s.golden_id},{s.expected_tool},{s.predicted_tool},"
            f"{s.tool_correct},{s.arg_ok},{s.task_completion},{s.answer_relevancy}"
        )
    return "\n".join(rows) + "\n"
