"""Reciprocal Rank Fusion — combine independent ranked candidate lists by RANK
(not by score arithmetic), so heterogeneous retrievers (CLIP, DINOv2, OCR) fuse
without score normalization. score(key) = sum 1/(k + rank). k=60 is the standard.
"""
from __future__ import annotations

from typing import Hashable


def reciprocal_rank_fusion(ranked_lists: "list[list[Hashable]]", k: int = 60) -> list:
    """Return candidate keys ordered by fused score (desc). Empty/missing inner
    lists contribute nothing. Ties keep first-inserted order (Python sort is
    stable), which preferences keys seen earlier across the lists."""
    scores: dict = {}
    for lst in ranked_lists:
        for rank, key in enumerate(lst or []):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda key: scores[key], reverse=True)
