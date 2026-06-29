"""Span L1 loss-space switch: (center,width) -> (start,end) (Part 2a, BAM-DETR-style).

Edits src/losses/regression_losses/retrieval_losses.py (MainRegressionLosses):
new kwarg `span_loss_space` ("cxw" default = bit-identical; "xx" computes the
smooth-L1 on boundary coordinates instead). Covers the whole o2o-style branch
(main + per-decoder-layer aux + encoder losses, which all route through
loss_spans); ATSS aux head and denoise/collab losses are intentionally
untouched. gIoU unchanged (already boundary-space).

Config: `main_reg_losses.span_loss_space` in configs/losses/default.yaml;
override with `losses.main_reg_losses.span_loss_space=xx`.

Run on the pod:  python patch_span_loss_space.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

PATH = f"{REPO}/src/losses/regression_losses/retrieval_losses.py"
src = open(PATH).read()
if "span_loss_space" in src:
    print("retrieval_losses.py already patched — skipping")
else:
    old = "        self.use_span_weights = use_span_weights\n"
    assert old in src, "__init__ anchor not found"
    src = src.replace(old, old + "        self.span_loss_space = span_loss_space\n", 1)

    old = "        use_span_weights: bool = False,\n"
    assert old in src, "__init__ signature anchor not found"
    src = src.replace(old, old + '        span_loss_space: str = "cxw",\n', 1)

    old = """        loss_span = func.smooth_l1_loss(src_spans, tgt_spans, reduction="none")
        if self.use_span_weights:"""
    assert old in src, "loss_spans anchor not found"
    src = src.replace(old, """        if self.span_loss_space == "xx":
            loss_span = func.smooth_l1_loss(
                span_cxw_to_xx(src_spans), span_cxw_to_xx(tgt_spans), reduction="none",
            )
        else:
            loss_span = func.smooth_l1_loss(src_spans, tgt_spans, reduction="none")
        if self.use_span_weights:"""
    , 1)

    open(PATH, "w").write(src)
    print("patched", PATH)

YPATH = f"{REPO}/configs/losses/default.yaml"
ysrc = open(YPATH).read()
if "span_loss_space" in ysrc:
    print("losses/default.yaml already patched — skipping")
else:
    old = "  use_span_weights: False\n"
    assert old in ysrc, "losses config anchor not found"
    ysrc = ysrc.replace(old, old + '  span_loss_space: "cxw"\n', 1)
    open(YPATH, "w").write(ysrc)
    print("patched", YPATH)
