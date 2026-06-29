"""MomentMix augmentation (Park et al., "MomentMix Augmentation with
Length-Aware DETR for Temporally Robust Moment Retrieval", WACV 2026,
arXiv:2412.20816) adapted ONLINE for the SG-DETR codebase.

Deviation from the reference implementation (documented for the thesis): the
authors pre-generate augmented annotation files offline; here both operators
run at dataloader time on the cached backbone features, so every epoch sees a
fresh mix and no extra feature files are written.

IMPORTANT correctness note (learned the hard way): the foreground is derived
from `relevant_windows` (seconds), NOT from `relevant_clip_ids` — in the
TACoS `_updated.jsonl` annotations the clip ids are a constant placeholder
([4, 5] on every sample) and do not encode the moment. Trusting them poisons
~50% of training samples (BackgroundMix swaps out real answer footage). The
windows are the ground truth the span loss trains on, so they define the
foreground here. Augmented samples also get fresh clip_ids/saliency derived
from the same windows.

Operators (paper semantics):
- ForegroundMix: split each foreground run into sub-segments of length
  <= ceil(eps_cut * run_len) (the paper's epsilon_cut) and scatter them among
  the background -> synthesizes SHORT-moment supervision; windows become
  clip-grid aligned.
- BackgroundMix: foreground clips stay in place; every background run is
  replaced by an equal-length contiguous slice of a donor video -> original
  (float) windows remain exactly valid.

Everything operates in CLIP space on the raw (pre-TEF, pre-normalization)
feature tensor; the caller re-applies normalization + TEF afterwards. Pure
functions, deterministic under a seeded `random.Random`.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Sequence, Tuple

import torch


def extract_runs(clip_ids: Sequence[int]) -> List[Tuple[int, int]]:
    """Sorted unique clip ids -> list of inclusive (start, end) runs."""
    ids = sorted(set(int(i) for i in clip_ids))
    runs: List[Tuple[int, int]] = []
    for cid in ids:
        if runs and cid == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], cid)
        else:
            runs.append((cid, cid))
    return runs


def windows_to_runs(
    windows_sec: Sequence[Sequence[float]], clip_len: float, length: int,
) -> List[Tuple[int, int]]:
    """GT windows in seconds -> merged inclusive clip runs, clamped to length."""
    ids: List[int] = []
    for win in windows_sec:
        if len(win) < 2 or win[1] <= win[0]:
            continue
        start = max(0, min(length - 1, int(math.floor(float(win[0]) / clip_len))))
        end = max(start, min(length - 1, int(math.ceil(float(win[1]) / clip_len)) - 1))
        ids.extend(range(start, end + 1))
    return extract_runs(ids)


def runs_to_windows(runs: Sequence[Tuple[int, int]], clip_len: float) -> List[List[float]]:
    """Inclusive clip runs -> [start_sec, end_sec] windows on the clip grid."""
    return [[float(s) * clip_len, (float(e) + 1.0) * clip_len] for s, e in runs]


def _split_run(run: Tuple[int, int], eps_cut: float, rng: random.Random) -> List[List[int]]:
    """Split one run's clip ids into sub-segments of length <= ceil(eps_cut * run_len)."""
    s, e = run
    ids = list(range(s, e + 1))
    max_piece = max(1, int(math.ceil(eps_cut * len(ids))))
    pieces: List[List[int]] = []
    i = 0
    while i < len(ids):
        take = rng.randint(1, max_piece)
        pieces.append(ids[i:i + take])
        i += take
    return pieces


def foreground_mix(
    feat: torch.Tensor,
    fg_runs: Sequence[Tuple[int, int]],
    sal_by_clip: Dict[int, List[int]],
    eps_cut: float,
    rng: random.Random,
) -> Tuple[torch.Tensor, List[int], List[List[int]], List[Tuple[int, int]]]:
    """Split foreground runs into short pieces and scatter them among background.

    Returns (new_feat, new_clip_ids, new_saliency_scores, new_runs). The new
    feature tensor is a permutation of the original clips (length preserved).
    """
    length = feat.shape[0]
    pieces: List[List[int]] = []
    for run in fg_runs:
        pieces.extend(_split_run(run, eps_cut, rng))
    rng.shuffle(pieces)

    fg_set = {c for p in pieces for c in p}
    bg = [c for c in range(length) if c not in fg_set]
    if not pieces or not bg:  # nothing to scatter, or nowhere to scatter into
        ids = sorted(fg_set)
        return feat, ids, [sal_by_clip.get(c, [1]) for c in ids], list(fg_runs)

    # choose an insertion gap (0..len(bg)) for every piece; ties allowed
    gaps = sorted(((rng.randint(0, len(bg)), k) for k in range(len(pieces))))
    order: List[int] = []
    new_runs: List[Tuple[int, int]] = []
    gi = 0
    for bg_pos in range(len(bg) + 1):
        while gi < len(gaps) and gaps[gi][0] == bg_pos:
            piece = pieces[gaps[gi][1]]
            new_runs.append((len(order), len(order) + len(piece) - 1))
            order.extend(piece)
            gi += 1
        if bg_pos < len(bg):
            order.append(bg[bg_pos])

    new_feat = feat[torch.tensor(order, dtype=torch.long)]
    new_clip_ids: List[int] = []
    new_sal: List[List[int]] = []
    for s, e in new_runs:
        for pos in range(s, e + 1):
            new_clip_ids.append(pos)
            new_sal.append(sal_by_clip.get(order[pos], [1]))
    # adjacent pieces may touch; merge runs for window labels
    merged = extract_runs(new_clip_ids)
    return new_feat, new_clip_ids, new_sal, merged


def background_mix(
    feat: torch.Tensor,
    fg_runs: Sequence[Tuple[int, int]],
    donor_feat: torch.Tensor,
    rng: random.Random,
) -> torch.Tensor:
    """Replace each background run with an equal-length contiguous donor slice.

    Foreground clips (and therefore all labels/windows) are untouched.
    """
    length = feat.shape[0]
    fg = {c for s, e in fg_runs for c in range(s, e + 1)}
    bg_runs = extract_runs([c for c in range(length) if c not in fg])
    if not bg_runs or donor_feat.shape[0] == 0:
        return feat
    new_feat = feat.clone()
    dlen = donor_feat.shape[0]
    for s, e in bg_runs:
        need = e - s + 1
        if dlen >= need:
            start = rng.randint(0, dlen - need)
            new_feat[s:e + 1] = donor_feat[start:start + need]
        else:  # short donor: tile with wraparound
            idx = [(rng.randint(0, dlen - 1) + k) % dlen for k in range(need)]
            new_feat[s:e + 1] = donor_feat[torch.tensor(idx, dtype=torch.long)]
    return new_feat


def apply_momentmix(
    feat: torch.Tensor,
    windows_sec: Sequence[Sequence[float]],
    clip_ids: Sequence[int],
    saliency_scores: Sequence[Sequence[int]],
    donor_feat: torch.Tensor,
    clip_len: float,
    eps_cut: float,
    rng: random.Random,
) -> Tuple[torch.Tensor, List[int], List[List[int]], List[List[float]]]:
    """Apply one MomentMix operator (coin flip between Fg/Bg mix).

    The foreground is defined by `windows_sec` (the span-loss ground truth).
    Returns (feat, relevant_clip_ids, saliency_scores, relevant_windows_sec);
    inputs unchanged when the sample is not augmentable.
    """
    length = feat.shape[0]
    fg_runs = windows_to_runs(windows_sec, clip_len, length)
    if not fg_runs:
        return feat, list(clip_ids), [list(s) for s in saliency_scores], [list(w) for w in windows_sec]
    sal_by_clip = {int(c): list(s) for c, s in zip(clip_ids, saliency_scores)}

    if rng.random() < 0.5:
        new_feat, new_ids, new_sal, runs = foreground_mix(feat, fg_runs, sal_by_clip, eps_cut, rng)
        return new_feat, new_ids, new_sal, runs_to_windows(runs, clip_len)

    new_feat = background_mix(feat, fg_runs, donor_feat, rng)
    ids = [c for s, e in fg_runs for c in range(s, e + 1)]
    sal = [sal_by_clip.get(c, [1]) for c in ids]
    # foreground untouched -> the ORIGINAL (float) windows remain exactly valid
    return new_feat, ids, sal, [list(w) for w in windows_sec]
