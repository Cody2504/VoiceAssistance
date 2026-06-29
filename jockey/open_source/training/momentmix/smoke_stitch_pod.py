"""Pod smoke test: offline-MomentMix stitching against real QVH features.

Run:  PYTHONPATH=/workspace/sg-detr /workspace/tvenv/bin/python smoke_stitch_pod.py
"""
import json
import time
from os.path import join

import torch

from src.dataset.qvhighlights import QVHighlights

ANN = "/workspace/data/qvhighlights/annotation/hl_mmix_5_seed0.jsonl"
FEAT = "/workspace/models/sg_detr/features/custom_features"

rows = [json.loads(line) for line in open(ANN)]
ds = QVHighlights(
    data_path=ANN,
    video_feat_dir=join(FEAT, "video"),
    query_feat_dir=join(FEAT, "custom_text"),
    max_query_length=40,
    max_video_length=75,
    clip_len=2,
)
assert len(ds.data) == len(rows), (len(ds.data), len(rows))

def is_fg(r):
    return "org_clip_ids_order" in r and all(v == r["vid"] for v, _ in r["org_clip_ids_order"])

fg_idx = next(i for i, r in enumerate(ds.data) if is_fg(r))
bg_idx = next(i for i, r in enumerate(ds.data)
              if "org_clip_ids_order" in r and not is_fg(r))
compound_idx = next((i for i, r in enumerate(ds.data)
                     if not is_fg(r) and "org_clip_ids_order" in r
                     and sum(v == r["vid"] for v, _ in r["org_clip_ids_order"])
                     > len(r["relevant_windows"])), None)

for name, idx in [("fgmix", fg_idx), ("bgmix", bg_idx), ("compound", compound_idx)]:
    if idx is None:
        print(f"{name}: none found")
        continue
    meta = ds.data[idx]
    order = meta["org_clip_ids_order"]
    stitched = ds._load_stitched_video_feat(order)
    manual = torch.cat([
        torch.load(join(FEAT, "video", f"{vid}.pt"))[s:e].float()
        for vid, (s, e) in order
    ])[:75]
    assert torch.equal(stitched, manual), f"{name}: stitched != manual"
    item = ds[idx]["model_inputs"]
    v = item["video_feat"]
    assert v.shape[0] >= stitched.shape[0] and v.shape[1] == stitched.shape[1] + 2, v.shape
    assert "span_labels" in item
    assert max(meta["relevant_clip_ids"]) < stitched.shape[0], name
    print(f"{name}: idx {idx} qid {meta['qid']} clips {stitched.shape[0]} "
          f"windows {len(meta['relevant_windows'])} OK")

# original row still loads through the untouched path
orig_idx = next(i for i, r in enumerate(ds.data) if "org_clip_ids_order" not in r)
item = ds[orig_idx]["model_inputs"]
print(f"original: idx {orig_idx} video_feat {tuple(item['video_feat'].shape)} OK")

# throughput sanity over 100 augmented rows
aug = [i for i, r in enumerate(ds.data) if "org_clip_ids_order" in r][:100]
t0 = time.time()
for i in aug:
    ds[i]
print(f"100 augmented loads in {time.time() - t0:.2f}s")
print("SMOKE OK")
