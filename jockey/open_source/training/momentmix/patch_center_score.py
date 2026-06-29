"""Wire Arm G: the center->score role-split for ReferenceRefinementHead.

Builds ON TOP of patch_reference_head.py. Adds a `use_center_score` flag that
makes the reference head also emit a per-query score_delta from f_center; the
forward then splices it onto outputs_class[-1] (= pred_logits), which drives BOTH
the final ranking (postprocessing.py:173) and the Hungarian class cost
(matcher.py:109). Zero-init => 0 at step 0 (bit-identical). Override with
`model.detr_detector.use_reference_head=true model.detr_detector.use_center_score=true`.

Run on the pod:  python patch_center_score.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

DET = f"{REPO}/src/model/blocks/detector.py"
src = open(DET).read()
assert "use_reference_head" in src, "patch_reference_head.py must be applied first"
if "use_center_score" in src:
    print("detector.py already patched — skipping")
else:
    # 1. __init__ signature
    old = "        use_reference_head: bool = False,\n"
    assert old in src, "use_reference_head __init__ anchor not found"
    src = src.replace(old, old + "        use_center_score: bool = False,\n", 1)

    # 2. pass with_center_score into the reference head
    old = "            ReferenceRefinementHead(model_dim) if use_reference_head\n"
    assert old in src, "ReferenceRefinementHead instantiation anchor not found"
    src = src.replace(
        old,
        "            ReferenceRefinementHead(model_dim, with_center_score=use_center_score) if use_reference_head\n",
        1,
    )

    # 3. forward: unpack the (cxw, score_delta) tuple and refine outputs_class[-1]
    old = "            outputs_coord = torch.cat([outputs_coord[:-1], refined_last.unsqueeze(0)], dim=0)\n"
    assert old in src, "forward outputs_coord splice anchor not found"
    new = (
        "            if isinstance(refined_last, tuple):\n"
        "                refined_last, score_delta = refined_last\n"
        "                outputs_class = torch.cat(\n"
        "                    [outputs_class[:-1], (outputs_class[-1] + score_delta).unsqueeze(0)], dim=0,\n"
        "                )\n"
        + old
    )
    src = src.replace(old, new, 1)

    open(DET, "w").write(src)
    print("patched", DET)

YPATH = f"{REPO}/configs/model/default.yaml"
ysrc = open(YPATH).read()
if "use_center_score" in ysrc:
    print("model/default.yaml already patched — skipping")
else:
    old = "  use_reference_head: False\n"
    assert old in ysrc, "use_reference_head config anchor not found"
    ysrc = ysrc.replace(old, old + "  use_center_score: False\n", 1)
    open(YPATH, "w").write(ysrc)
    print("patched", YPATH)
