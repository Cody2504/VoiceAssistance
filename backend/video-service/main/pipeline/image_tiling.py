"""Image multi-crop / tiling (roadmap #6) — improve small-object / logo recall
by embedding crops of frames (and the query image) in the CLIP-L space, not just
the whole frame (where a small logo is washed out by the global embedding).

Pure helpers here (no torch/encoder import) so they're unit-testable; the encoder
calls live in ingest (`_encode_crop_embeddings`) and the image-search path.
"""
from __future__ import annotations

import numpy as np


def tile_frames(frames: np.ndarray, grid: int = 2) -> list[tuple[str, np.ndarray]]:
    """Split each frame in `frames` [N,H,W,3] into a grid×grid set of crops.
    Returns [(region, sub_frames[N,h,w,3]), ...] — crops only (the caller already
    has the full-frame embedding). Returns [] for empty input or a grid too fine
    for the frame size."""
    if frames is None or len(frames) == 0 or grid < 1:
        return []
    H, W = int(frames.shape[1]), int(frames.shape[2])
    hs, ws = H // grid, W // grid
    if hs == 0 or ws == 0:
        return []
    out: list[tuple[str, np.ndarray]] = []
    for r in range(grid):
        for c in range(grid):
            y0, y1 = r * hs, (H if r == grid - 1 else (r + 1) * hs)
            x0, x1 = c * ws, (W if c == grid - 1 else (c + 1) * ws)
            out.append((f"r{r}c{c}", frames[:, y0:y1, x0:x1, :]))
    return out


def merge_hits_by_shot(per_query_hits: list[list[dict]], top_n: int) -> list[dict]:
    """Merge hits from several crop queries, keeping the MAX score per
    (video_id, shot_idx). Each hit dict needs `video_id`, `shot_idx`, `score`.
    Returns the merged hits sorted by score desc, capped at top_n."""
    best: dict[tuple, dict] = {}
    for hits in per_query_hits:
        for h in hits:
            key = (h.get("video_id"), h.get("shot_idx"))
            if key not in best or h["score"] > best[key]["score"]:
                best[key] = dict(h)
    ranked = sorted(best.values(), key=lambda h: -h["score"])
    return ranked[:top_n]
