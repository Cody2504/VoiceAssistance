"""Query-time object verification stage for the `when` fan-out (research B).

After merge_rank, the top candidates are checked with GroundingDINO: frames
around each candidate's midpoint are scanned for the query's object phrase,
and candidate scores are rescaled by detection confidence —
`score × (demote + boost × conf)` — so a window that merely *embeds near* the
query but doesn't *show* the object drops below one where the object is
actually visible. Pure helpers are unit-testable without any model.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# "when is/does …", "at what time …", "show me when …" → the object phrase.
_LEAD_RE = re.compile(
    r"^(?:show me\s+|find\s+)?(?:when|at what time|what time|where)\s*"
    r"(?:is|are|was|were|does|do|did|will)?\s*",
    re.IGNORECASE,
)
_TRAIL_WORDS = {
    "happen", "happens", "happened", "occur", "occurs", "occurred",
    "appear", "appears", "appeared", "added", "shown", "seen", "visible", "used",
    "is", "are", "was", "were",  # aux left behind once its participle is popped
}
_LEAD_ARTICLES = {"the", "a", "an"}


def object_phrase(query: str) -> str:
    """Reduce a "when does X happen" query to the detectable object phrase,
    '.'-terminated per GroundingDINO's text-prompt convention. Empty string
    when nothing object-like remains (caller skips verification)."""
    q = (query or "").strip().strip("?.!").lower()
    q = _LEAD_RE.sub("", q)
    toks = q.split()
    while toks and toks[-1] in _TRAIL_WORDS:
        toks.pop()
    while toks and toks[0] in _LEAD_ARTICLES:
        toks.pop(0)
    phrase = " ".join(toks).strip()
    return f"{phrase}." if phrase else ""


def apply_verification(events: list[dict], confs: list[float | None], *,
                       boost: float, demote: float) -> list[dict]:
    """Rescale the first len(confs) events by detection confidence and re-sort.
    conf=None (detector couldn't look) leaves that event's score untouched."""
    out = [dict(e) for e in events]
    for e, conf in zip(out, confs):
        if conf is None:
            continue
        factor = demote + boost * float(conf)
        e["score"] = float(e["score"]) * factor
        meta = dict(e.get("metadata") or {})
        meta["object_verify"] = {"confidence": round(float(conf), 4), "factor": round(factor, 4)}
        e["metadata"] = meta
    out.sort(key=lambda e: -e["score"])
    return out


def verify_events(events: list[dict], local_path: str, query: str, *, settings) -> list[dict]:
    """Verify the top object_verify_top_k events against the video frames.
    Best-effort: any unavailability returns the input ranking unchanged."""
    phrase = object_phrase(query)
    if not phrase or not events:
        return events
    from main.encoders.object_detector import ObjectDetector
    det = ObjectDetector.from_settings(settings)
    if not det.is_available():
        return events
    from main.encoders.indexer import extract_frames  # type: ignore

    confs: list[float | None] = []
    for e in events[: settings.object_verify_top_k]:
        mid = (float(e["t_start"]) + float(e["t_end"])) / 2
        half = max(0.25, min(2.0, (float(e["t_end"]) - float(e["t_start"])) / 2))
        frames = extract_frames(
            local_path, max(0.0, mid - half), mid + half,
            max_frames=settings.object_verify_frames,
        )
        confs.append(det.max_confidence(frames, phrase))
    return apply_verification(
        events, confs, boost=settings.object_verify_boost, demote=settings.object_verify_demote,
    )
