"""Unit tests for the online MomentMix operators (run on the pod's tvenv)."""
import random

import torch

from momentmix import (
    apply_momentmix,
    background_mix,
    extract_runs,
    foreground_mix,
    runs_to_windows,
    windows_to_runs,
)


def _feat(n, d=4, base=0.0):
    # row i is identifiable: filled with base + i
    return torch.arange(n, dtype=torch.float32).unsqueeze(1).repeat(1, d) + base


def test_extract_runs():
    assert extract_runs([3, 4, 5, 9, 10, 20]) == [(3, 5), (9, 10), (20, 20)]
    assert extract_runs([]) == []
    assert extract_runs([7, 7, 6]) == [(6, 7)]


def test_windows_to_runs_derives_foreground_from_seconds():
    # the TACoS lesson: clip ids come from WINDOWS, not relevant_clip_ids
    assert windows_to_runs([[4.79, 12.04]], 2.0, 100) == [(2, 6)]
    assert windows_to_runs([[0.0, 4.0], [4.0, 8.0]], 2.0, 100) == [(0, 3)]  # merge
    assert windows_to_runs([[190.0, 210.0]], 2.0, 100) == [(95, 99)]        # clamp
    assert windows_to_runs([[5.0, 5.0]], 2.0, 100) == []                    # degenerate


def test_runs_to_windows_clip_grid():
    assert runs_to_windows([(2, 4)], 2.0) == [[4.0, 10.0]]


def test_foreground_mix_is_permutation_and_labels_align():
    rng = random.Random(7)
    feat = _feat(30)
    fg_runs = [(10, 21)]                          # one long 12-clip moment
    sal = {c: [2] for c in range(10, 22)}
    new_feat, new_ids, new_sal, runs = foreground_mix(feat, fg_runs, sal, eps_cut=0.34, rng=rng)
    # permutation: same multiset of rows
    assert torch.equal(new_feat.sum(dim=1).sort().values, feat.sum(dim=1).sort().values)
    assert len(new_ids) == 12 and len(new_sal) == 12
    # every labeled clip in the new layout is an original foreground row
    orig_fg_rows = {float(feat[i, 0]) for i in range(10, 22)}
    assert all(float(new_feat[i, 0]) in orig_fg_rows for i in new_ids)
    # runs cover exactly the labeled ids
    covered = [c for s, e in runs for c in range(s, e + 1)]
    assert sorted(covered) == sorted(new_ids)
    assert all(s == [2] for s in new_sal)
    # eps_cut=0.34 on a 12-clip moment -> pieces of <=4 clips -> more runs than 1
    assert len(runs) >= 2


def test_foreground_mix_full_video_foreground_is_noop():
    rng = random.Random(1)
    feat = _feat(8)
    _, new_ids, _, runs = foreground_mix(feat, [(0, 7)], {}, 0.5, rng)
    assert new_ids == list(range(8)) and runs == [(0, 7)]


def test_background_mix_keeps_foreground_replaces_background():
    rng = random.Random(3)
    feat = _feat(20)
    donor = _feat(50, base=1000.0)
    out = background_mix(feat, [(5, 8)], donor, rng)
    for i in range(5, 9):
        assert torch.equal(out[i], feat[i])              # fg untouched
    bg = [i for i in range(20) if i not in range(5, 9)]
    assert all(float(out[i, 0]) >= 1000.0 for i in bg)   # bg from donor
    assert out.shape == feat.shape


def test_background_mix_short_donor_wraps():
    rng = random.Random(5)
    feat = _feat(30)
    donor = _feat(3, base=500.0)
    out = background_mix(feat, [(0, 1)], donor, rng)
    assert all(float(out[i, 0]) >= 500.0 for i in range(2, 30))


def test_apply_momentmix_uses_windows_not_clip_ids():
    """Garbage relevant_clip_ids (the TACoS [4,5] placeholder) must be ignored."""
    feat = _feat(40)
    donor = _feat(40, base=900.0)
    windows = [[20.0, 32.0]]                      # true fg = clips 10..15
    garbage_ids = [4, 5]
    for seed in range(6):                         # both branches across seeds
        out_feat, ids, sal, wins = apply_momentmix(
            feat, windows, garbage_ids, [[1], [1]], donor, 2.0, 0.5, random.Random(seed),
        )
        fg_rows = {float(feat[i, 0]) for i in range(10, 16)}
        # every labeled clip in the output holds original fg content
        assert all(float(out_feat[i, 0]) in fg_rows for i in ids)
        assert len(ids) == len(sal) == 6
        duration = 40 * 2.0
        for w in wins:
            assert 0.0 <= w[0] < w[1] <= duration


def test_apply_momentmix_bgmix_preserves_float_windows():
    feat = _feat(40)
    donor = _feat(40, base=900.0)
    windows = [[4.79, 12.04]]
    rng = random.Random(2)                        # seed 2 -> bg branch (rng.random()>=0.5)
    while True:
        probe = random.Random(2)
        if probe.random() >= 0.5:
            break
        rng = random.Random(rng.randint(0, 10**6))
        # find a seed whose first draw goes to the bg branch
        for s in range(100):
            if random.Random(s).random() >= 0.5:
                rng = random.Random(s)
                break
        break
    out_feat, ids, _, wins = apply_momentmix(feat, windows, [], [], donor, 2.0, 0.5, rng)
    assert wins == [[4.79, 12.04]]                # float GT untouched by BackgroundMix
    for i in ids:                                  # fg content in place
        assert torch.equal(out_feat[i], feat[i])


def test_apply_momentmix_deterministic():
    feat = _feat(40)
    donor = _feat(40, base=900.0)
    a = apply_momentmix(feat, [[16.0, 48.0]], [], [], donor, 2.0, 0.5, random.Random(42))
    b = apply_momentmix(feat, [[16.0, 48.0]], [], [], donor, 2.0, 0.5, random.Random(42))
    assert torch.equal(a[0], b[0]) and a[1] == b[1] and a[3] == b[3]
