"""Offline MomentMix generator for QVHighlights (SG-DETR training).

Faithful port of the official LA-DETR pipeline (Park et al., WACV 2026,
arXiv:2412.20816; github.com/sjpark5800/LA-DETR, momentmix/temporal/) for the
QVHighlights annotation format used by sg-detr. Produces an EXPANDED jsonl:
originals + ForegroundMix rows + BackgroundMix rows, where augmented rows
carry `org_clip_ids_order` = [(vid, [clip_start, clip_end)), ...] stitching
recipes that the dataloader resolves against the original feature files.

Deviations from the reference implementation (documented for the thesis):
1. The CLIP-based temporal-query rewrite branch is dropped. It depends on a
   `run_on_video` module the official repo does not ship, writes CLIP text
   features tied to their feature stack, and has an upstream bug (the rewrite
   is assigned to `new_crop_data` instead of `new_replace_data`, so it never
   actually attaches). Net behavior matches the published code: FgMix skips
   temporal-word queries, BgMix (order-preserving) runs on them unchanged.
2. Donor lookup guards: an empty length bin or an exhausted donor search
   returns None for that sample instead of crashing (random.choice on [])
   or looping forever (single-video bins). No behavior change when donors
   exist.
3. Compound rows: the official pass 2 runs BgMix over FgMix rows but builds
   moment entries as (vid, [rs, re)) in REMIXED coordinates, which the loader
   would slice from the ORIGINAL video -> wrong foreground content (label
   poisoning, same failure mode as the TACoS relevant_clip_ids bug). Here
   moment entries are resolved through the row's existing org_clip_ids_order
   so the stitched foreground is the true remixed moment content.
4. The BgMix count assert is replaced by a total-length-conservation assert
   (resolution in (3) can legitimately split one moment into several
   stitching entries).

Usage:
    python gen_qvh_mmix.py highlight_train_release.jsonl \
        hl_mmix_5_seed0.jsonl --thres-crop 5 --seed 0
"""
from __future__ import annotations

import argparse
import json
import random
from copy import deepcopy

# moment class borderlines for QVHighlights ('hl' in the official script)
HL_DB_RANGE = [150, 130, 110, 90, 70, 50, 30, 10, 0]

# verbatim official list (momentmix/temporal/mmix.py)
TEMPORAL_WORDS = [
    # Sequential relationships (before, after)
    "before", "prior to", "earlier than", "previously", "formerly", "once", "ahead of",
    "preceding", "by the time", "until", "after", "following", "subsequent to", "later",
    "thereafter", "then", "next", "henceforth", "from then on", "since",
    # Simultaneous relationships (while, during)
    "while", "as", "when", "meanwhile", "simultaneously", "at the same time", "concurrently",
    "in the meantime", "during", "throughout",
    # Continuous or overlapping relationships
    "until", "throughout", "all the while", "ever since", "as long as", "so long as",
    "from start to finish",
    # Expressions emphasizing the passage of time
    "eventually", "gradually", "over time", "sooner or later", "in the long run",
    "before long", "by then", "by now", "from now on", "hence",
]

_DONOR_TRIES = 100
_SHORT_MOMENT_SEC = 30  # official BgMix gate: sample must have a moment <= 30s


def has_temporal_words(query: str) -> bool:
    """Official check, including its substring semantics ('as' in 'basketball')."""
    q = query.lower()
    return any(word in q for word in TEMPORAL_WORDS)


def ctx_len(duration: float, clip_len: float) -> int:
    return int(duration // clip_len) if duration % clip_len == 0 else int(duration // clip_len) + 1


def find_ones_groups(arr, clip_len):
    groups, start_idx = [], None
    for i, v in enumerate(arr):
        if v == 1 and start_idx is None:
            start_idx = i
        elif v == 0 and start_idx is not None:
            groups.append([start_idx * clip_len, i * clip_len])
            start_idx = None
    if start_idx is not None:
        groups.append([start_idx * clip_len, len(arr) * clip_len])
    return groups


def find_zeros_groups(arr, clip_len):
    groups, start_idx = [], None
    for i, v in enumerate(arr):
        if v == 0 and start_idx is None:
            start_idx = i
        elif v == 1 and start_idx is not None:
            groups.append([start_idx * clip_len, i * clip_len])
            start_idx = None
    if start_idx is not None:
        groups.append([start_idx * clip_len, len(arr) * clip_len])
    return groups


def crop_clip_index(start_index, end_index, num_crop=1, clip_len=2):
    candidates = list(range(start_index + clip_len, end_index, clip_len))
    if num_crop > 1:
        return sorted(random.sample(candidates, num_crop))
    return random.sample(candidates, num_crop)


def derive_segments(data, ctx_l, clip_len):
    """QVHighlights branch: moments/non-moments from relevant_clip_ids."""
    all_clips = [0] * ctx_l
    for c in data["relevant_clip_ids"]:
        all_clips[c] = 1
    moments = find_ones_groups(all_clips, clip_len)
    assert moments == data["relevant_windows"], (
        f"qid {data['qid']}: relevant_windows {data['relevant_windows']} "
        f"!= clip-id-derived {moments}"
    )
    non_moments = find_zeros_groups(all_clips, clip_len)
    return moments, non_moments


def resolve_order(order, start, end):
    """Map remixed clip range [start, end) through an existing stitching order."""
    out, pos = [], 0
    for vid, (s, e) in order:
        seg_len = e - s
        lo, hi = max(start, pos), min(end, pos + seg_len)
        if lo < hi:
            out.append((vid, [s + lo - pos, s + hi - pos]))
        pos += seg_len
    return out


# --------------------------------------------------------------------- FgMix
def fg_mix(data, moments, non_moments, thres_crop, ctx_l, clip_len):
    """Split the longest moment into ~thres_crop-second pieces and scatter."""
    # find the longest moment (grid-aligned bounds, seconds)
    max_moment_length, max_moment_idx, ms, me = 0, -1, -1, -1
    for i, (s, e) in enumerate(moments):
        rs = int(s // clip_len) if s != 0 else 0
        re = int(e // clip_len) if e % clip_len == 0 else int(e // clip_len) + 1
        rs, re = rs * clip_len, re * clip_len
        if re - rs > max_moment_length:
            max_moment_length, max_moment_idx, ms, me = re - rs, i, rs, re

    if max_moment_length < thres_crop * 2:
        return None

    # split the longest moment; keep the others whole
    num_crop = max_moment_length // thres_crop - 1
    moment_crop_idxs = crop_clip_index(ms, me, num_crop=num_crop, clip_len=clip_len)

    moment_segments, ss_idx = [], 0
    for i, (s, e) in enumerate(moments):
        if i == max_moment_idx:
            bounds = moment_crop_idxs + [e]
            ss = s
            for ee in bounds:
                rss = int(ss // clip_len) if ss != 0 else 0
                ree = int(ee // clip_len) if ee % clip_len == 0 else int(ee // clip_len) + 1
                seg = {"clip_id": [rss, ree], "len": ree - rss}
                seg["saliency_scores"] = data["saliency_scores"][ss_idx:ss_idx + seg["len"]]
                ss_idx += seg["len"]
                moment_segments.append(seg)
                ss = ee
        else:
            rs = int(s // clip_len) if s != 0 else 0
            re = int(e // clip_len) if e % clip_len == 0 else int(e // clip_len) + 1
            seg = {"clip_id": [rs, re], "len": re - rs}
            seg["saliency_scores"] = data["saliency_scores"][ss_idx:ss_idx + seg["len"]]
            ss_idx += seg["len"]
            moment_segments.append(seg)

    # split long non-moments until there is one more of them than moments
    need_crop_count = len(moment_segments) + 1 - len(non_moments)
    non_moment_crop_idxs, non_moment_idxs = [], []
    for i, (s, e) in enumerate(non_moments):
        rs = 0 if s == 0 else (int(s // clip_len) if s % clip_len == 0 else int(s // clip_len) + 1)
        re = int(e // clip_len)
        rs, re = rs * clip_len, re * clip_len
        if re - rs >= thres_crop * 2 and need_crop_count > 0:
            num_crop = min((re - rs) // thres_crop - 1, need_crop_count)
            non_moment_crop_idxs.append(crop_clip_index(rs, re, num_crop=num_crop, clip_len=clip_len))
            non_moment_idxs.append(i)
            need_crop_count -= num_crop
        if need_crop_count <= 0:
            break
    if need_crop_count > 0:
        return None

    non_moment_segments = []
    for i, (s, e) in enumerate(non_moments):
        if i in non_moment_idxs:
            bounds = non_moment_crop_idxs[non_moment_idxs.index(i)] + [e]
            ss = s
            for ee in bounds:
                rss = 0 if ss == 0 else (int(ss // clip_len) if ss % clip_len == 0 else int(ss // clip_len) + 1)
                ree = int(ee // clip_len)
                non_moment_segments.append({"clip_id": [rss, ree], "len": ree - rss})
                ss = ee
        else:
            rs = 0 if s == 0 else (int(s // clip_len) if s % clip_len == 0 else int(s // clip_len) + 1)
            re = int(e // clip_len)
            non_moment_segments.append({"clip_id": [rs, re], "len": re - rs})

    random.shuffle(non_moment_segments)
    random.shuffle(moment_segments)

    new_data = {
        "qid": data["qid"], "query": data["query"],
        "duration": data["duration"], "vid": data["vid"],
    }
    new_clips = [0] * ctx_l
    cur, order, saliency = 0, [], []
    for i, moment_segment in enumerate(moment_segments):
        nm = non_moment_segments[i]
        cur += nm["len"]
        order.append((data["vid"], nm["clip_id"]))
        nxt = cur + moment_segment["len"]
        for k in range(cur, nxt):
            new_clips[k] = 1
        cur = nxt
        order.append((data["vid"], moment_segment["clip_id"]))
        saliency += moment_segment["saliency_scores"]
    order.append((data["vid"], non_moment_segments[-1]["clip_id"]))

    new_data["org_clip_ids_order"] = order
    new_data["saliency_scores"] = saliency
    new_data["relevant_clip_ids"] = [i for i, v in enumerate(new_clips) if v == 1]
    new_data["relevant_windows"] = find_ones_groups(new_clips, clip_len)

    assert len(data["saliency_scores"]) == len(new_data["saliency_scores"])
    assert len(new_data["saliency_scores"]) == len(new_data["relevant_clip_ids"])
    check = [0] * ctx_l
    for _, (s, e) in order:
        for k in range(s, e):
            check[k] += 1
    assert all(c <= 1 for c in check)
    assert all(c > 0 for c in check[:-1])
    return new_data


# --------------------------------------------------------------------- BgMix
def bg_mix(data, moments, non_moments, ctx_l, clip_len, db_range, moment_db):
    """Replace non-moments with length-matched segments from other videos."""
    if not any(e - s <= _SHORT_MOMENT_SEC for s, e in moments):
        return None

    non_moment_segments = []
    for s, e in non_moments:
        need_len = e - s
        find, db_range_idx = False, -1
        for border in db_range:
            if need_len > border:
                find = True
                break
            db_range_idx += 1
        if not find or db_range_idx == -1:
            return None
        if not moment_db[db_range_idx]:  # guard: empty bin (official crashes)
            return None
        another_moment = None
        for _ in range(_DONOR_TRIES):  # guard: official loops forever
            cand = random.choice(moment_db[db_range_idx])
            if cand[0] != data["qid"] and cand[1] != data["vid"]:
                another_moment = cand
                break
        if another_moment is None:
            return None

        ass, aee = another_moment[2]
        assert aee - ass >= need_len
        aee = ass + need_len
        rss = 0 if ass == 0 else (int(ass // clip_len) if ass % clip_len == 0 else int(ass // clip_len) + 1)
        ree = int(aee // clip_len)
        non_moment_segments.append({"vid": another_moment[1], "clip_id": [rss, ree], "len": ree - rss})

    new_data = {
        "qid": data["qid"], "query": data["query"],
        "duration": data["duration"], "vid": data["vid"],
        "relevant_windows": data["relevant_windows"],
        "relevant_clip_ids": data["relevant_clip_ids"],
        "saliency_scores": data["saliency_scores"],
    }

    existing_order = data.get("org_clip_ids_order")

    def moment_entries(s, e):
        rs = int(s // clip_len) if s != 0 else 0
        re = int(e // clip_len) if e % clip_len == 0 else int(e // clip_len) + 1
        if existing_order is None:
            return [(data["vid"], [rs, re])]
        return resolve_order(existing_order, rs, re)  # true remixed content

    order, nm_idx = [], 0
    if non_moments[0][0] == 0:
        nm = non_moment_segments[0]
        order.append((nm["vid"], nm["clip_id"]))
        nm_idx += 1
    for i in range(len(moments) - 1):
        order.extend(moment_entries(*moments[i]))
        nm = non_moment_segments[nm_idx]
        order.append((nm["vid"], nm["clip_id"]))
        nm_idx += 1
    order.extend(moment_entries(*moments[-1]))
    if nm_idx < len(non_moment_segments):
        nm = non_moment_segments[-1]
        order.append((nm["vid"], nm["clip_id"]))

    new_data["org_clip_ids_order"] = order
    total = sum(e - s for _, (s, e) in order)
    assert total == ctx_l, f"qid {data['qid']}: stitched {total} clips != ctx_l {ctx_l}"
    return new_data


# ------------------------------------------------------------------ pipeline
def build_moment_db(datalist, db_range, clip_len):
    """Length-binned database of every moment AND non-moment segment."""
    moment_db = [[] for _ in db_range]
    for data in datalist:
        moments, non_moments = derive_segments(data, ctx_len(data["duration"], clip_len), clip_len)
        for segs in (moments, non_moments):
            for start, end in segs:
                for i, border in enumerate(db_range):
                    if end - start >= border:
                        moment_db[i].append((data["qid"], data["vid"], [start, end]))
                        break
    return moment_db


def generate(datalist, thres_crop=5, seed=0, clip_len=2):
    """Two-pass official flow: originals -> +FgMix -> +BgMix."""
    random.seed(seed)
    datalist = [deepcopy(d) for d in datalist]
    moment_db = build_moment_db(datalist, HL_DB_RANGE, clip_len)

    pass1 = []
    for data in datalist:
        pass1.append(data)
        moments, non_moments = derive_segments(data, ctx_len(data["duration"], clip_len), clip_len)
        if not non_moments or has_temporal_words(data["query"]):
            continue
        new_row = fg_mix(data, moments=moments, non_moments=non_moments,
                         thres_crop=thres_crop, ctx_l=ctx_len(data["duration"], clip_len),
                         clip_len=clip_len)
        if new_row:
            pass1.append(new_row)

    pass2 = []
    for data in pass1:
        pass2.append(data)
        moments, non_moments = derive_segments(data, ctx_len(data["duration"], clip_len), clip_len)
        if not non_moments:
            continue
        new_row = bg_mix(data, moments=moments, non_moments=non_moments,
                         ctx_l=ctx_len(data["duration"], clip_len), clip_len=clip_len,
                         db_range=HL_DB_RANGE, moment_db=moment_db)
        if new_row:
            pass2.append(new_row)

    print(f"Length Augmentation : {len(datalist)} -> {len(pass1)} -> {len(pass2)}")
    return pass2


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="highlight_train_release.jsonl")
    parser.add_argument("output", help="augmented jsonl to write")
    parser.add_argument("--thres-crop", type=int, default=5,
                        help="epsilon_cut in seconds (official QVH value: 5)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    with open(args.input) as f:
        datalist = [json.loads(line) for line in f if line.strip()]
    out = generate(datalist, thres_crop=args.thres_crop, seed=args.seed)

    n_fg = sum(1 for r in out if "org_clip_ids_order" in r
               and all(v == r["vid"] for v, _ in r["org_clip_ids_order"]))
    n_aug = sum(1 for r in out if "org_clip_ids_order" in r)
    print(f"originals {len(datalist)}, fgmix ~{n_fg}, bgmix ~{n_aug - n_fg}, total {len(out)}")

    with open(args.output, "w") as f:
        for row in out:
            f.write(json.dumps(row, default=list) + "\n")
    print(f"Saved File : {args.output}")


if __name__ == "__main__":
    main()
