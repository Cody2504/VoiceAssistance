"""Wire the BAM-DETR-style BoundaryRefinementHead into SG-DETR (Part 2b).

Edits src/model/blocks/detector.py (MomentDetector):
  - import BoundaryRefinementHead
  - new __init__ kwarg `use_boundary_head` (default False = BIT-IDENTICAL: the
    head is None and the forward branch is skipped)
  - instantiate self.boundary_head next to span_embed/class_embed
  - in forward, after _predict_spans, refine ONLY the final-layer spans from
    (final query emb hs[-1], clip-grid memory, final cxw spans) and splice back;
    aux layers (outputs_coord[:-1]) are left untouched.
Replacing outputs_coord[-1] propagates the refined spans to model.py:420
out["pred_spans"], so the matcher and loss_spans consume them with no edits.

Config: `use_boundary_head` in configs/model/default.yaml detr_detector block;
override with `model.detr_detector.use_boundary_head=true`.

Run on the pod:  python patch_boundary_head.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

DET = f"{REPO}/src/model/blocks/detector.py"
src = open(DET).read()
if "boundary_head" in src:
    print("detector.py already patched — skipping")
else:
    # 1. import
    old = "from src.model.blocks.feed_forward import SlimMLP\n"
    assert old in src, "import anchor not found"
    src = src.replace(old, old + "from src.model.blocks.boundary_head import BoundaryRefinementHead\n", 1)

    # 2. __init__ signature
    old = "        aux_anchors_type: Tuple[str, ...] = (),\n"
    assert old in src, "__init__ signature anchor not found"
    src = src.replace(old, old + "        use_boundary_head: bool = False,\n", 1)

    # 3. instantiate head (after class_embed, before _init_parameters)
    old = "        self.class_embed = nn.Linear(model_dim, 1)\n"
    assert old in src, "class_embed anchor not found"
    src = src.replace(
        old,
        old + "        self.boundary_head = BoundaryRefinementHead(model_dim) if use_boundary_head else None\n",
        1,
    )

    # 4. forward: refine the final-layer spans
    old = "        outputs_coord, offset = self._predict_spans(hs, reference_points)\n"
    assert old in src, "_predict_spans call anchor not found"
    new = old + (
        "        if self.boundary_head is not None:\n"
        "            refined_last = self.boundary_head(\n"
        "                hs[-1],\n"
        "                memory_local.transpose(0, 1),\n"
        "                outputs_coord[-1],\n"
        "            )\n"
        "            outputs_coord = torch.cat([outputs_coord[:-1], refined_last.unsqueeze(0)], dim=0)\n"
    )
    src = src.replace(old, new, 1)

    open(DET, "w").write(src)
    print("patched", DET)

YPATH = f"{REPO}/configs/model/default.yaml"
ysrc = open(YPATH).read()
if "use_boundary_head" in ysrc:
    print("model/default.yaml already patched — skipping")
else:
    old = '  aux_anchors_type: ["collab"] # ["denoise", "collab"]\n'
    assert old in ysrc, "detr_detector config anchor not found"
    ysrc = ysrc.replace(old, old + "  use_boundary_head: False\n", 1)
    open(YPATH, "w").write(ysrc)
    print("patched", YPATH)
