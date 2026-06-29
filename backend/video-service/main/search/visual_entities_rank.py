"""Pure re-rank: add a fixed boost to a candidate's semantic score when any strong
query token (brand/wordmark) appears in its visual_entities text. Keeps the exact
instance pinned (brand name) without letting it override unrelated high-semantic hits
unless a real token match occurs."""
from typing import List


def rank_with_keyword_boost(candidates: List[dict], tokens: List[str], boost: float) -> List[dict]:
    toks = [t.lower() for t in tokens if t]
    out = []
    for c in candidates:
        text = (c.get("visual_entities") or "").lower()
        hit = any(t in text for t in toks)
        c = dict(c)
        c["score_boosted"] = float(c.get("score", 0.0)) + (boost if hit else 0.0)
        out.append(c)
    # stable sort: ties keep original (semantic) order
    return sorted(out, key=lambda c: -c["score_boosted"])
