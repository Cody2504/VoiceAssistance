"""Merge temporally back-to-back shots from a search result into single clips.

Search over `jockey_shots` returns one row per shot span. On a contiguous shot
grid, adjacent shots that both rank for a query are really one moment, so
collapse them into a single clip for cleaner citations (e.g. 3:16-3:23 + 3:23-3:30
→ 3:16-3:30). Pure function — no I/O — so it stays trivially testable.
"""
from __future__ import annotations


def merge_contiguous_shots(shots: list[dict], gap_s: float = 1.0) -> list[dict]:
    """Collapse adjacent shots (of the same video) whose spans touch within
    `gap_s` seconds into one clip.

    A merged clip spans [min t_start, max t_end], takes the MAX score of its
    members, and concatenates their `asr_text` in time order; every other field
    is inherited from the top-scoring member. Output is re-sorted by score desc.
    Single shots and non-adjacent shots pass through unchanged. Shots are grouped
    by `video_id` first (a missing key groups them together), so a corpus result
    never merges across videos.
    """
    if not shots:
        return []

    groups: dict = {}
    for sh in shots:
        groups.setdefault(sh.get("video_id"), []).append(sh)

    out: list[dict] = []
    for _vid, group in groups.items():
        ordered = sorted(group, key=lambda x: float(x["t_start"]))
        clusters: list[list[dict]] = [[ordered[0]]]
        for sh in ordered[1:]:
            prev_end = max(float(c["t_end"]) for c in clusters[-1])
            if float(sh["t_start"]) <= prev_end + gap_s:
                clusters[-1].append(sh)
            else:
                clusters.append([sh])

        for cl in clusters:
            if len(cl) == 1:
                out.append(cl[0])
                continue
            top = max(cl, key=lambda x: float(x["score"]))
            merged = dict(top)
            merged["t_start"] = min(float(c["t_start"]) for c in cl)
            merged["t_end"] = max(float(c["t_end"]) for c in cl)
            merged["score"] = max(float(c["score"]) for c in cl)
            parts = [(c.get("asr_text") or "").strip()
                     for c in sorted(cl, key=lambda x: float(x["t_start"]))]
            merged["asr_text"] = " ".join(p for p in parts if p)
            out.append(merged)

    out.sort(key=lambda x: float(x["score"]), reverse=True)
    return out
