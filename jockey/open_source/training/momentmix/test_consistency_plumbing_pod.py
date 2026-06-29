"""Pod test: consistency second-view plumbing (dataset -> collate -> device).

Run:  PYTHONPATH=/workspace/sg-detr /workspace/tvenv/bin/python test_consistency_plumbing_pod.py
"""
from os.path import join

import torch

from src.dataset.collate import custom_collate, move_inputs_to_device
from src.dataset.qvhighlights import QVHighlights

ANN = "/workspace/data/qvhighlights/annotation/hl_mmix_5_seed0.jsonl"
FEAT = "/workspace/models/sg_detr/features/custom_features"
KW = dict(
    data_path=ANN,
    video_feat_dir=join(FEAT, "video"),
    query_feat_dir=join(FEAT, "custom_text"),
    max_query_length=40,
    max_video_length=75,
    clip_len=2,
)

# 1. default off -> keys absent (bit-identical behavior)
ds_off = QVHighlights(**KW)
item = ds_off[0]["model_inputs"]
assert "video_feat_orig" not in item and "cons_map" not in item
print("off-mode: keys absent OK")

# 2. enabled -> every sample emits both keys
ds = QVHighlights(**KW, emit_consistency_view=True)
aug_idx = next(i for i, r in enumerate(ds.data) if "org_clip_ids_order" in r)
plain_idx = next(i for i, r in enumerate(ds.data) if "org_clip_ids_order" not in r)
samples = [ds[plain_idx], ds[aug_idx], ds[plain_idx + 2], ds[aug_idx + 1]]
for s in samples:
    mi = s["model_inputs"]
    assert "video_feat_orig" in mi and "cons_map" in mi
    assert mi["video_feat_orig"].shape[1] == mi["video_feat"].shape[1]  # same dim (D+2)
    assert mi["video_feat_orig"].shape[0] % 4 == 0  # fpn-padded
plain_mi = samples[0]["model_inputs"]
assert plain_mi["cons_map"] == []
assert torch.equal(plain_mi["video_feat_orig"], plain_mi["video_feat"])
print("emit-mode: per-sample keys OK")

# 3. content invariant: mapped positions agree across views in feature dims
#    (first 512 dims; the 2 TEF dims legitimately differ by position)
aug_mi = samples[1]["model_inputs"]
cmap = aug_mi["cons_map"]
assert cmap, "augmented row must have a non-empty map"
for ms, me, ss, se in cmap[:5]:
    n = min(me - ms, se - ss,
            aug_mi["video_feat"].shape[0] - ms, aug_mi["video_feat_orig"].shape[0] - ss)
    assert n > 0
    assert torch.allclose(
        aug_mi["video_feat"][ms:ms + n, :512],
        aug_mi["video_feat_orig"][ss:ss + n, :512],
        atol=1e-6,
    ), "mapped clips differ between views"
print("content invariant across views OK")

# 4. collate + move_inputs_to_device threading
meta, batched = custom_collate(samples)
assert "video_feat_orig" in batched and "cons_map" in batched
assert isinstance(batched["cons_map"], list) and len(batched["cons_map"]) == 4
model_inputs, targets = move_inputs_to_device(batched, torch.device("cpu"))
for key in ("src_vid_orig", "src_vid_orig_mask", "cons_map"):
    assert key in model_inputs, key
assert model_inputs["src_vid_orig"].shape[0] == 4
assert model_inputs["src_vid_orig"].shape[2] == model_inputs["src_vid"].shape[2]
assert targets is not None and "span_labels" in targets
print("collate + device threading OK")
print("PLUMBING OK")
