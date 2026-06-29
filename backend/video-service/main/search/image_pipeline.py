"""Pure fusion/dedupe logic for corpus image search.

Kept free of FastAPI/Qdrant/torch so it is unit-testable. The endpoint
(`main.api.search`) supplies the CLIP and DINOv2 candidate shot dicts and the
query frame's OCR text; this module dedupes by (video_id, shot_idx) and fuses
the three ranked signals via Reciprocal Rank Fusion.
"""
from __future__ import annotations

from main.search.fusion import reciprocal_rank_fusion
from main.search.ocr_match import rank_by_text_overlap


def shot_key(sh: dict):
    return (sh["video_id"], sh["idx"])


def _dedupe_keys(keys):
    """Keep first occurrence (best rank) — collapses the per-frame duplicate
    points so a repeated shot doesn't get an inflated RRF score."""
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def pin_strong_ocr(verified_shots, fused_shots, pin_keys) -> list[dict]:
    """Move the strong OCR (on-screen-text) matches in `pin_keys` to the front of
    `verified_shots`, using their pre-verify `fused_shots` dicts (which carry the
    real CLIP/DINOv2 scores).

    The VLM verifier is unreliable at *same-domain* identity ("which tennis video")
    and was observed dropping the exact title-card match outright. On-screen title
    text is a near-certain identity signal, so it overrides the verdict: the
    verifier still prunes cross-domain noise from the tail, but cannot bury or drop
    a confirmed title-text match. `pin_keys` are (video_id, idx) tuples, best-first.
    """
    if not pin_keys:
        return verified_shots
    fused_by_key = {(s["video_id"], s["idx"]): s for s in fused_shots}
    pinned: list[dict] = []
    seen: set = set()
    for key in pin_keys:
        sh = fused_by_key.get(key)
        if sh is not None and key not in seen:
            pinned.append(sh)
            seen.add(key)
    return pinned + [s for s in verified_shots if (s["video_id"], s["idx"]) not in seen]


def fuse_image_candidates(
    clip_shots, dino_shots, query_ocr_text: str, ocr_shots=None, region_shots=None,
    k: int = 60,
) -> list[dict]:
    """Dedupe by (video_id, shot_idx) and fuse region + CLIP + DINOv2 + OCR ranked
    lists via RRF. Returns deduped shot dicts in fused order (best first).

    `ocr_shots` is the OCR *retrieval* stream: shots fetched from the corpus
    because their indexed `ocr_text` overlaps the query frame's text. They enter
    the pool so a visually-confusable correct video — one CLIP/DINOv2 never
    surface — can still be recovered by its on-screen title text.

    `region_shots` is the region/object stream: shots whose detected object regions
    (DINOv2-embedded at ingest) match the query. Background-invariant, so a clean
    logo/object query lands on the right video where the whole-frame CLIP/DINOv2
    channels are dominated by background — paired with OCR (wordmark logos).
    """
    ocr_shots = ocr_shots or []
    region_shots = region_shots or []
    pool: dict = {}
    for sh in list(clip_shots) + list(dino_shots) + list(ocr_shots) + list(region_shots):
        key = shot_key(sh)
        prev = pool.get(key)
        if prev is None or (sh.get("score") or 0) > (prev.get("score") or 0):
            pool[key] = {**(prev or {}), **sh}

    clip_rank = _dedupe_keys(shot_key(s) for s in clip_shots)
    dino_rank = _dedupe_keys(shot_key(s) for s in dino_shots)
    region_rank = _dedupe_keys(shot_key(s) for s in region_shots)
    ocr_rank = rank_by_text_overlap(
        query_ocr_text, [(key, pool[key].get("ocr_text", "")) for key in pool]
    )
    # region first, OCR second: both are high-precision *instance* identifiers
    # (region = the object/logo itself, background-invariant; OCR = on-screen
    # title text). On an RRF tie they should beat a same-category CLIP/DINOv2
    # whole-frame visual neighbour.
    fused = reciprocal_rank_fusion([region_rank, ocr_rank, clip_rank, dino_rank], k=k)
    ordered = [pool[key] for key in fused if key in pool]
    seen = {shot_key(s) for s in ordered}
    ordered += [pool[key] for key in pool if key not in seen]
    return ordered
