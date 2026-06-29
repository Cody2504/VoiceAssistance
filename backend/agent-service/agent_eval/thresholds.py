"""Pass/fail thresholds for the agent tool-trajectory eval."""
from agent_eval.report import Aggregate

DEFAULT_THRESHOLDS = {
    "routing_f1_macro": 0.90,
    "arg_correctness_rate": 0.95,
    "mean_task_completion": 0.80,
    "mean_answer_relevancy": 0.80,
}


def assert_thresholds(agg: Aggregate, thresholds: dict | None = None) -> list[str]:
    """Return a list of breach strings (empty == pass). None-valued metrics are skipped."""
    th = thresholds or DEFAULT_THRESHOLDS
    values = {
        "routing_f1_macro": agg.routing_f1_macro,
        "arg_correctness_rate": agg.arg_correctness_rate,
        "mean_task_completion": agg.mean_task_completion,
        "mean_answer_relevancy": agg.mean_answer_relevancy,
    }
    failures: list[str] = []
    for key, floor in th.items():
        val = values.get(key)
        if val is not None and val < floor:
            failures.append(f"{key}={val:.3f} < {floor}")
    return failures
