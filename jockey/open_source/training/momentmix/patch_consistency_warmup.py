"""Add warmup gating to the consistency loss (pilot-1 finding, 2026-06-12).

Pilot 1 (lambda=0.5 from epoch 0) showed the loss fights early ignition:
liftoff delayed ~10 epochs, 15 mAP behind Arm B at matched epoch 19, then a
degenerate-span matcher crash. The constraint's intended benefits (late-phase
overfit suppression, splice-shortcut removal) don't need early epochs ->
`consistency_warmup_epochs`: loss (and the teacher forward) disabled before
that epoch. Default 0 = previous behavior.

Run on the pod:  python patch_consistency_warmup.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

PATH = f"{REPO}/src/litmodule.py"
src = open(PATH).read()
if "consistency_warmup_epochs" in src:
    print("litmodule already patched — skipping")
else:
    old = "        consistency_weight: float = 0.0,\n"
    assert old in src, "__init__ signature anchor not found"
    src = src.replace(old, old + "        consistency_warmup_epochs: int = 0,\n", 1)

    old = "        self.consistency_weight = consistency_weight\n"
    assert old in src, "__init__ body anchor not found"
    src = src.replace(old, old + "        self.consistency_warmup_epochs = consistency_warmup_epochs\n", 1)

    old = "            if self.consistency_weight > 0 and src_vid_orig is not None:"
    assert old in src, "train-branch anchor not found"
    src = src.replace(old, """            if (
                self.consistency_weight > 0
                and src_vid_orig is not None
                and self.current_epoch >= self.consistency_warmup_epochs
            ):""", 1)
    open(PATH, "w").write(src)
    print("patched", PATH)

YPATH = f"{REPO}/configs/model/default.yaml"
ysrc = open(YPATH).read()
if "consistency_warmup_epochs" in ysrc:
    print("config already patched — skipping")
else:
    old = "  consistency_weight: 0.0\n"
    assert old in ysrc, "runner config anchor not found"
    ysrc = ysrc.replace(old, old + "  consistency_warmup_epochs: 0\n", 1)
    open(YPATH, "w").write(ysrc)
    print("patched", YPATH)
