"""Gated Stage-2 LightGlue verifier for image search.

Stage-1 (CLIP/DINOv2/region/OCR, fused by RRF) proposes candidate shots; this
re-ranks them by geometric agreement with the query: DISK local features +
LightGlue matching + RANSAC, scored by inlier count, run on each candidate's
cached keyframe thumbnail (no video access, no re-index).

The re-rank is GATED: a clean instance match scores ~150 inliers while unrelated
frames sit at <=10 (measured on our corpus). So we only reorder when a candidate
clears `min_inliers`; otherwise the fused order is kept untouched, which stops a
weak/no-match query (e.g. a package-variant mismatch) from letting noise-level
inliers reshuffle the result. `gate_rerank` is the pure decision and is unit
tested; the DISK/LightGlue matching is loaded lazily and verified end-to-end.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def gate_rerank(shots, inliers, min_inliers):
    """Re-rank `shots` by RANSAC `inliers`, but only when at least one shot clears
    `min_inliers`. Shots that clear the gate move to the front, sorted by inliers
    descending (stable on ties — original order preserved); the rest keep their
    incoming (fused) order. When nothing clears the gate, `shots` is returned
    unchanged. `inliers[i]` is the inlier count for `shots[i]`."""
    if len(inliers) != len(shots):
        raise ValueError(f"inliers ({len(inliers)}) must align with shots ({len(shots)})")
    strong = [i for i in range(len(shots)) if inliers[i] >= min_inliers]
    if not strong:
        return list(shots)
    strong.sort(key=lambda i: -inliers[i])  # stable: ties keep original order
    weak = [i for i in range(len(shots)) if inliers[i] < min_inliers]
    return [shots[i] for i in strong] + [shots[i] for i in weak]


# ---- DISK + LightGlue matcher (lazy; heavy deps stay out of module import) ----
_MATCHER = None       # (disk, lightglue, device), built on first use
_MIN_SIDE = 320       # upscale small thumbnails so DISK finds enough keypoints


def _load_matcher():
    global _MATCHER
    if _MATCHER is None:
        import torch
        import kornia.feature as KF
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        disk = KF.DISK.from_pretrained("depth").to(dev).eval()
        lg = KF.LightGlueMatcher("disk").to(dev).eval()
        _MATCHER = (disk, lg, dev)
        log.info("lightglue_verify: matcher loaded on %s", dev)
    return _MATCHER


def _feats(rgb, n=2048):
    """DISK keypoints + descriptors for an HxWx3 uint8 RGB array (small crops upscaled)."""
    import cv2
    import numpy as np
    import torch
    disk, _lg, dev = _load_matcher()
    h, w = rgb.shape[:2]
    side = min(h, w)
    if 0 < side < _MIN_SIDE:
        f = _MIN_SIDE / side
        rgb = cv2.resize(rgb, (int(w * f), int(h * f)), interpolation=cv2.INTER_CUBIC)
    t = torch.from_numpy(np.ascontiguousarray(rgb)).permute(2, 0, 1).float()[None].to(dev) / 255.0
    with torch.no_grad():
        out = disk(t, n=n, window_size=5, score_threshold=0.0, pad_if_not_divisible=True)[0]
    return out.keypoints, out.descriptors, (rgb.shape[0], rgb.shape[1])


def _match(qf, cf):
    """RANSAC inlier count between two DISK feature tuples (from `_feats`)."""
    import cv2
    import numpy as np  # noqa: F401  (used via cv2 arrays)
    import torch
    import kornia.feature as KF
    _disk, lg, dev = _load_matcher()
    (k1, d1, hw1), (k2, d2, hw2) = qf, cf
    if k1.shape[0] < 6 or k2.shape[0] < 6:
        return 0
    with torch.no_grad():
        l1 = KF.laf_from_center_scale_ori(k1[None])
        l2 = KF.laf_from_center_scale_ori(k2[None])
        _, idx = lg(d1, d2, l1, l2, torch.tensor(hw1, device=dev), torch.tensor(hw2, device=dev))
    if idx.shape[0] < 6:
        return 0
    p1 = k1[idx[:, 0]].cpu().numpy()
    p2 = k2[idx[:, 1]].cpu().numpy()
    _, mask = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)
    return int(mask.sum()) if mask is not None else 0


def _decode(jpeg_bytes):
    """JPEG bytes -> HxWx3 uint8 RGB array, or None on failure."""
    import cv2
    import numpy as np
    arr = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    return None if arr is None else cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)


def lightglue_inliers(query_rgb, cand_rgb):
    """Convenience: RANSAC inliers between two RGB uint8 arrays (query vs candidate)."""
    return _match(_feats(query_rgb), _feats(cand_rgb))


def verify_shots_lightglue(query_rgb, shots, thumb_fetch, *, min_inliers=30, top_k=20):
    """Gated Stage-2 re-rank of `shots` by LightGlue+RANSAC inliers against each
    candidate's keyframe thumbnail.

    `query_rgb` is the query image as an HxWx3 uint8 RGB array. `thumb_fetch(video_id,
    shot_idx) -> jpeg bytes | None` pulls a candidate's cached keyframe. Only the top
    `top_k` candidates are matched (the tail keeps its order); reordering is gated at
    `min_inliers`. Any failure (matcher unavailable in prod, bad thumbnail, etc.) is a
    safe no-op that returns `shots` unchanged — the verifier must never empty or break
    a result on infra issues."""
    try:
        head, tail = list(shots[:top_k]), list(shots[top_k:])
        if not head:
            return list(shots)
        qf = _feats(query_rgb)  # computed once, reused across candidates
        inliers = []
        for sh in head:
            n = 0
            try:
                b = thumb_fetch(sh["video_id"], sh["idx"])
                if b:
                    cand = _decode(b)
                    if cand is not None:
                        n = _match(qf, _feats(cand))
            except Exception:  # noqa: BLE001 — one bad candidate must not sink the rest
                n = 0
            inliers.append(n)
        return gate_rerank(head, inliers, min_inliers) + tail
    except Exception as exc:  # noqa: BLE001 — matcher missing / GPU OOM / etc.
        log.warning("lightglue_verify: no-op (%s)", exc)
        return list(shots)
