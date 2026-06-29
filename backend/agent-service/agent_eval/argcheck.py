"""Deterministic structural argument-constraint checking for tool calls."""
from dataclasses import dataclass, field

from agent_eval.trajectory import ToolCallRecord

# Structural args = SCOPE (which video/index to act on) — must match the case
# context exactly. Everything else (query, question, tag, group_by, top_n, ...) is
# free text / presentation and only checked non-empty. group_by is intentionally
# NOT structural: clip-vs-video grouping is the model's call, not a scope error.
STRUCTURAL_KEYS = {"video_id", "index_id", "video_ids"}


@dataclass
class ArgCheck:
    passed: bool
    details: dict = field(default_factory=dict)


def _struct_equal(key: str, actual, expected) -> bool:
    if key == "video_ids":
        return sorted(actual or []) == sorted(expected or [])
    return actual == expected


def check_arg_constraints(call: ToolCallRecord, expected_args: dict) -> ArgCheck:
    details: dict = {}
    ok = True
    for key, exp in expected_args.items():
        actual = call.args.get(key)
        if key in STRUCTURAL_KEYS:
            match = _struct_equal(key, actual, exp)
            details[key] = {"expected": exp, "actual": actual, "ok": match}
            ok = ok and match
        else:
            present = isinstance(actual, str) and bool(actual.strip())
            details[key] = {"free_text": actual, "ok": present}
            ok = ok and present
    return ArgCheck(passed=ok, details=details)
