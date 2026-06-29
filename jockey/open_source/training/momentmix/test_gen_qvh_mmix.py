"""Tests for the offline QVHighlights MomentMix generator (gen_qvh_mmix).

Port of the official LA-DETR pipeline (momentmix/temporal/, WACV 2026,
arXiv:2412.20816) for QVHighlights. The tests encode the official
invariants plus one correctness fix: when BackgroundMix runs on a row that
already carries `org_clip_ids_order` (a ForegroundMix product), moment
segments must be resolved THROUGH that mapping so the stitched foreground
is the true remixed moment content, not arbitrary clips of the original
video at remixed indices.

Run: /tmp/mmixvenv/bin/python -m pytest test_gen_qvh_mmix.py -q
"""
import copy
import json
import random

import pytest

from gen_qvh_mmix import (
    HL_DB_RANGE,
    bg_mix,
    build_moment_db,
    derive_segments,
    fg_mix,
    find_ones_groups,
    find_zeros_groups,
    generate,
    has_temporal_words,
    resolve_order,
)

CLIP_LEN = 2


# ---------------------------------------------------------------- fixtures
def make_sample(qid, vid, duration, windows, query="Girl drinks milk."):
    """QVH-style row; saliency entry k is [c, c, c] for its source clip c."""
    clip_ids = []
    for s, e in windows:
        clip_ids.extend(range(s // CLIP_LEN, e // CLIP_LEN))
    return {
        "qid": qid,
        "query": query,
        "duration": duration,
        "vid": vid,
        "relevant_windows": [list(w) for w in windows],
        "relevant_clip_ids": clip_ids,
        "saliency_scores": [[c, c, c] for c in clip_ids],
    }


def ctx_len(duration):
    return duration // CLIP_LEN if duration % CLIP_LEN == 0 else duration // CLIP_LEN + 1


def stitch_tokens(row):
    """Virtual stitcher: per-clip tokens 'vid:clip' as the dataloader sees them."""
    if "org_clip_ids_order" not in row:
        return [f"{row['vid']}:{i}" for i in range(ctx_len(row["duration"]))]
    out = []
    for vid, (s, e) in row["org_clip_ids_order"]:
        out.extend(f"{vid}:{i}" for i in range(s, e))
    return out


def foreground_tokens(row):
    toks = stitch_tokens(row)
    return [toks[c] for c in row["relevant_clip_ids"]]


# long-moment FgMix-eligible sample: 40s moment, 110s background
def fg_eligible():
    return make_sample(1, "vidA", 150, [[0, 40]], query="A man eats a sandwich.")


# short-moment BgMix-eligible sample: 10s moment in 60s video
def bg_eligible():
    return make_sample(3, "vidC", 60, [[10, 20]])


# donor video: segments populating the bins bg_eligible() needs
def donor():
    return make_sample(4, "vidD", 150, [[0, 16], [80, 90]], query="Dog runs far.")


# ------------------------------------------------------------ group helpers
def test_find_ones_groups_returns_moment_windows():
    assert find_ones_groups([1, 1, 0, 0, 1], CLIP_LEN) == [[0, 4], [8, 10]]


def test_find_zeros_groups_returns_gap_windows():
    assert find_zeros_groups([1, 1, 0, 0, 1], CLIP_LEN) == [[4, 8]]


def test_temporal_query_detection():
    assert has_temporal_words("Man eats before the interview.")
    assert not has_temporal_words("Girl drinks milk.")


def test_derive_segments_matches_annotations():
    data = bg_eligible()
    moments, non_moments = derive_segments(data, ctx_len(data["duration"]), CLIP_LEN)
    assert moments == [[10, 20]]
    assert non_moments == [[0, 10], [20, 60]]


# ------------------------------------------------------------------ fg_mix
def run_fg(data, seed=0):
    random.seed(seed)
    ctx_l = ctx_len(data["duration"])
    moments, non_moments = derive_segments(data, ctx_l, CLIP_LEN)
    return fg_mix(
        data, moments=moments, non_moments=non_moments,
        thres_crop=5, ctx_l=ctx_l, clip_len=CLIP_LEN,
    )


def test_fg_mix_splits_longest_moment_into_multiple_windows():
    new = run_fg(fg_eligible())
    assert new is not None
    assert len(new["relevant_windows"]) > 1
    # windows stay on the clip grid and agree with clip ids
    ones = [0] * ctx_len(new["duration"])
    for c in new["relevant_clip_ids"]:
        ones[c] = 1
    assert new["relevant_windows"] == find_ones_groups(ones, CLIP_LEN)


def test_fg_mix_keeps_clip_count_and_duration():
    src = fg_eligible()
    new = run_fg(src)
    assert len(new["relevant_clip_ids"]) == len(src["relevant_clip_ids"])
    assert new["duration"] == src["duration"]
    assert new["qid"] == src["qid"] and new["vid"] == src["vid"]


def test_fg_mix_saliency_tracks_source_clips():
    new = run_fg(fg_eligible())
    toks = stitch_tokens(new)
    for pos, sal in zip(new["relevant_clip_ids"], new["saliency_scores"]):
        src_clip = int(toks[pos].split(":")[1])
        assert sal == [src_clip, src_clip, src_clip]


def test_fg_mix_covers_every_clip_exactly_once():
    src = fg_eligible()
    new = run_fg(src)
    counts = [0] * ctx_len(src["duration"])
    for vid, (s, e) in new["org_clip_ids_order"]:
        assert vid == src["vid"]
        for i in range(s, e):
            counts[i] += 1
    assert all(c <= 1 for c in counts)
    assert all(c == 1 for c in counts[:-1])


def test_fg_mix_returns_none_for_short_moments():
    data = make_sample(2, "vidB", 60, [[0, 8]])  # 8s < 2 * thres_crop
    assert run_fg(data) is None


# ------------------------------------------------------------------ bg_mix
def run_bg(data, db_sources, seed=0):
    random.seed(seed)
    ctx_l = ctx_len(data["duration"])
    moments, non_moments = derive_segments(data, ctx_l, CLIP_LEN)
    moment_db = build_moment_db(db_sources, HL_DB_RANGE, CLIP_LEN)
    return bg_mix(
        data, moments=moments, non_moments=non_moments, ctx_l=ctx_l,
        clip_len=CLIP_LEN, db_range=HL_DB_RANGE, moment_db=moment_db,
    )


def test_bg_mix_returns_none_without_short_moment():
    data = make_sample(5, "vidE", 60, [[0, 32]])  # 32s > 30s short gate
    assert run_bg(data, [data, donor()]) is None


def test_bg_mix_keeps_foreground_labels_unchanged():
    src = bg_eligible()
    new = run_bg(src, [src, donor()])
    assert new is not None
    assert new["relevant_windows"] == src["relevant_windows"]
    assert new["relevant_clip_ids"] == src["relevant_clip_ids"]
    assert new["saliency_scores"] == src["saliency_scores"]


def test_bg_mix_replaces_background_with_equal_length_donor_slices():
    src = bg_eligible()
    new = run_bg(src, [src, donor()])
    toks = stitch_tokens(new)
    assert len(toks) == ctx_len(src["duration"])
    fg = set(src["relevant_clip_ids"])
    for pos, tok in enumerate(toks):
        if pos in fg:
            assert tok == f"{src['vid']}:{pos}"
        else:
            assert tok.split(":")[0] != src["vid"]


def test_bg_mix_returns_none_when_donor_bin_empty():
    src = bg_eligible()
    assert run_bg(src, [src]) is None  # only own segments -> no usable donor


# ------------------------------------------------- compound (bg over fg row)
def test_resolve_order_maps_remixed_ranges_to_sources():
    order = [("v1", [10, 15]), ("v2", [0, 5])]  # remixed video of 10 clips
    assert resolve_order(order, 3, 8) == [("v1", [13, 15]), ("v2", [0, 3])]


def test_bg_mix_on_fg_row_resolves_true_foreground_content():
    row = {
        "qid": 7,
        "query": "Girl drinks milk.",
        "duration": 20,
        "vid": "v1",
        "relevant_clip_ids": [2, 3, 7],
        "relevant_windows": [[4, 8], [14, 16]],
        "saliency_scores": [[0, 0, 0], [1, 1, 1], [4, 4, 4]],
        "org_clip_ids_order": [
            ("v1", [5, 7]), ("v1", [0, 2]), ("v1", [8, 9]),
            ("v1", [2, 5]), ("v1", [7, 8]),
        ],
    }
    expected_fg = foreground_tokens(row)  # ['v1:0', 'v1:1', 'v1:4']
    donor2 = make_sample(8, "v2", 20, [[0, 8]])
    new = run_bg(row, [row, donor2])
    assert new is not None
    toks = stitch_tokens(new)
    assert len(toks) == 10
    assert foreground_tokens(new) == expected_fg
    for pos in range(10):
        if pos not in {2, 3, 7}:
            assert toks[pos].startswith("v2:")


# ---------------------------------------------------------------- generate
def small_datalist():
    return [
        fg_eligible(),
        make_sample(2, "vidB", 150, [[0, 40]], query="Man eats before the interview."),
        bg_eligible(),
        donor(),
    ]


def test_generate_appends_augmented_rows():
    out = generate(small_datalist(), thres_crop=5, seed=0)
    assert len(out) > 4
    assert [r["qid"] for r in out if "org_clip_ids_order" not in r] == [1, 2, 3, 4]
    assert any("org_clip_ids_order" in r for r in out)


def test_generate_skips_fgmix_for_temporal_queries():
    out = generate(small_datalist(), thres_crop=5, seed=0)
    for row in out:
        if row["qid"] == 2 and "org_clip_ids_order" in row:
            # any augmented row for the temporal query must be BgMix
            # (order-preserving), never a FgMix shuffle: foreground tokens
            # must sit at their original positions.
            for pos, tok in zip(row["relevant_clip_ids"], foreground_tokens(row)):
                assert tok == f"vidB:{pos}"


def test_generate_foreground_content_is_faithful_everywhere():
    originals = {r["qid"]: r for r in small_datalist()}
    out = generate(small_datalist(), thres_crop=5, seed=0)
    for row in out:
        if "org_clip_ids_order" not in row:
            continue
        src = originals[row["qid"]]
        expected = sorted(f"{src['vid']}:{c}" for c in src["relevant_clip_ids"])
        assert sorted(foreground_tokens(row)) == expected


def test_generate_is_deterministic_per_seed():
    a = generate(small_datalist(), thres_crop=5, seed=0)
    b = generate(small_datalist(), thres_crop=5, seed=0)
    assert json.dumps(a, sort_keys=True, default=list) == json.dumps(
        b, sort_keys=True, default=list
    )


def test_generate_does_not_mutate_input():
    datalist = small_datalist()
    snapshot = copy.deepcopy(datalist)
    generate(datalist, thres_crop=5, seed=0)
    assert datalist == snapshot
