"""Rank image-search candidates by on-screen text overlap with the query frame.

Title cards / scoreboards carry instance-specific text (a show title, a player
name) that CLIP cannot read but that is already indexed per-shot as `ocr_text`.
Pure token-overlap ranking; the caller supplies the query's OCR text and each
candidate's indexed ocr_text.
"""
from __future__ import annotations

import re

_STOP = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with", "at",
    "is", "it", "this", "that", "by", "as", "be", "are", "from",
}


def _tokens(text: str) -> set:
    toks = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in toks if len(t) >= 2 and t not in _STOP}


def rank_by_text_overlap(query_text: str, candidates) -> list:
    """`candidates` is an iterable of (key, ocr_text). Returns keys with > 0
    shared content tokens, ordered by shared-token count (desc). Empty query or
    no overlaps → []."""
    q = _tokens(query_text)
    if not q:
        return []
    scored = []
    for key, ocr_text in candidates:
        shared = len(q & _tokens(ocr_text))
        if shared > 0:
            scored.append((shared, key))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [key for _, key in scored]
