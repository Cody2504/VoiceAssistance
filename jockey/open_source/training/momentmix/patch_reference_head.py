"""Wire the RDSA-inspired ReferenceRefinementHead into SG-DETR (Arm F).

Builds ON TOP of patch_boundary_head.py (detector.py already imports
BoundaryRefinementHead and has the self.boundary_head forward injection). Since
ReferenceRefinementHead shares the exact (query_emb, memory, spans_cxw)->cxw
interface, we reuse the SAME forward block — only the __init__ instantiation
becomes head-selectable via a new `use_reference_head` flag:

    self.boundary_head = ReferenceRefinementHead(model_dim) if use_reference_head
                         else (BoundaryRefinementHead(model_dim) if use_boundary_head else None)

Default False everywhere = BIT-IDENTICAL. Override with
`model.detr_detector.use_reference_head=true` (and the same on eval).

Run on the pod:  python patch_reference_head.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

DET = f"{REPO}/src/model/blocks/detector.py"
src = open(DET).read()
assert "BoundaryRefinementHead" in src, "patch_boundary_head.py must be applied first"
if "use_reference_head" in src:
    print("detector.py already patched — skipping")
else:
    # 1. extend the boundary-head import
    old = "from src.model.blocks.boundary_head import BoundaryRefinementHead\n"
    assert old in src, "import anchor not found"
    src = src.replace(
        old, "from src.model.blocks.boundary_head import BoundaryRefinementHead, ReferenceRefinementHead\n", 1,
    )

    # 2. __init__ signature: add use_reference_head next to use_boundary_head
    old = "        use_boundary_head: bool = False,\n"
    assert old in src, "__init__ use_boundary_head anchor not found"
    src = src.replace(old, old + "        use_reference_head: bool = False,\n", 1)

    # 3. make the head selectable (same self.boundary_head attr -> forward block unchanged)
    old = "        self.boundary_head = BoundaryRefinementHead(model_dim) if use_boundary_head else None\n"
    assert old in src, "boundary_head instantiation anchor not found"
    new = (
        "        self.boundary_head = (\n"
        "            ReferenceRefinementHead(model_dim) if use_reference_head\n"
        "            else (BoundaryRefinementHead(model_dim) if use_boundary_head else None)\n"
        "        )\n"
    )
    src = src.replace(old, new, 1)

    open(DET, "w").write(src)
    print("patched", DET)

YPATH = f"{REPO}/configs/model/default.yaml"
ysrc = open(YPATH).read()
if "use_reference_head" in ysrc:
    print("model/default.yaml already patched — skipping")
else:
    old = "  use_boundary_head: False\n"
    assert old in ysrc, "use_boundary_head config anchor not found"
    ysrc = ysrc.replace(old, old + "  use_reference_head: False\n", 1)
    open(YPATH, "w").write(ysrc)
    print("patched", YPATH)
