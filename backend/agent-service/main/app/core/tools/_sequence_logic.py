"""Pure ordering logic for the compositional `find_sequence` tool (roadmap #5).

Kept free of any langchain import so it is unit-testable without the agent stack.
"""
from __future__ import annotations

from typing import Any


def build_sequence(steps: list[str], per_step_top: list[dict | None]) -> dict[str, Any]:
    """Given each step's best event (the top `/when` hit, or None if not found),
    build the ordered result and verify the steps occur in the listed order.

    Returns {steps:[{query,found,t_start,t_end,label,source}], all_found, ordered}.
    `ordered` is True only if EVERY step was found AND their `t_start` values are
    non-decreasing in the listed order — an *approximate* compositional check
    (order, not true co-occurrence)."""
    out: list[dict] = []
    for q, ev in zip(steps, per_step_top):
        if ev:
            out.append({
                "query": q, "found": True,
                "t_start": float(ev["t_start"]), "t_end": float(ev["t_end"]),
                "label": ev.get("label", ""), "source": ev.get("source", ""),
            })
        else:
            out.append({"query": q, "found": False, "t_start": None, "t_end": None,
                        "label": "", "source": ""})

    all_found = bool(out) and all(s["found"] for s in out)
    ordered = all_found
    prev: float | None = None
    for s in out:
        if not s["found"]:
            ordered = False
            break
        if prev is not None and s["t_start"] < prev:
            ordered = False
            break
        prev = s["t_start"]
    return {"steps": out, "all_found": all_found, "ordered": bool(ordered)}
