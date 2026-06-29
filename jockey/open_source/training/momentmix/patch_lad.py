"""Wire Length-Aware Decoder (LAD) into SG-DETR (Arm E).

Two changes, both gated by `lad_borders` (empty list = BIT-IDENTICAL):
  1. QuerySelector.get_query_proposals: class-balanced top-k proposal selection
     (per-class top-N_q in contiguous class-ordered slots) instead of global top-k.
  2. HungarianMatcher: forbid o2o matches between a query (class = slot // N_q,
     since aux_post_process keeps the RPN queries in selection order) and a GT of a
     different length class, by raising that cost entry before linear_sum_assignment.

Config: `lad_borders: []` added to query_selector (model/default.yaml) and matcher
(losses/default.yaml). Enable Arm E with:
  model.num_queries=40 model.query_selector.lad_borders='[0.089,0.21,0.5]' \
  losses.matcher.lad_borders='[0.089,0.21,0.5]'

Run on the pod:  python patch_lad.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

# ---- detector.py: QuerySelector ----
DET = f"{REPO}/src/model/blocks/detector.py"
src = open(DET).read()
if "class_balanced_topk" in src:
    print("detector.py already LAD-patched — skipping")
else:
    old = "from src.model.utils.model_utils import gen_encoder_output_proposals, inverse_sigmoid\n"
    assert old in src, "detector import anchor not found"
    src = src.replace(old, old + "from src.model.utils.lad import class_balanced_topk\n", 1)

    # __init__ signature (QuerySelector — unique via default_widths line)
    old = (
        "        default_widths: List[float] = [0.05, 0.2, 0.4, 0.85],\n"
        "        init_spans_with_zeros: bool = True,\n"
        "    ):\n"
    )
    assert old in src, "QuerySelector __init__ signature anchor not found"
    src = src.replace(
        old,
        "        default_widths: List[float] = [0.05, 0.2, 0.4, 0.85],\n"
        "        init_spans_with_zeros: bool = True,\n"
        "        lad_borders: List[float] = (),\n"
        "    ):\n",
        1,
    )
    # __init__ body (QuerySelector — unique via self.default_widths)
    old = (
        "        self.default_widths = default_widths\n"
        "        self.init_spans_with_zeros = init_spans_with_zeros\n"
    )
    assert old in src, "QuerySelector __init__ body anchor not found"
    src = src.replace(old, old + "        self.lad_borders = lad_borders\n", 1)

    # get_query_proposals: class-balanced selection
    old = "        topk_proposals = torch.topk(enc_outputs_combo_unselected[..., 0], self.num_queries, dim=1)[1]  # noqa: WPS221\n"
    assert old in src, "topk selection anchor not found"
    new = (
        "        if len(self.lad_borders) > 0:\n"
        "            _widths = torch.sigmoid(enc_outputs_coord_unselected[..., 1])\n"
        "            topk_proposals = class_balanced_topk(\n"
        "                enc_outputs_combo_unselected[..., 0], _widths, list(self.lad_borders), self.num_queries,\n"
        "            )\n"
        "        else:\n"
        "            topk_proposals = torch.topk(enc_outputs_combo_unselected[..., 0], self.num_queries, dim=1)[1]\n"
    )
    src = src.replace(old, new, 1)
    open(DET, "w").write(src)
    print("patched", DET)

# ---- matcher.py: class-conditioned matching ----
MAT = f"{REPO}/src/losses/matcher.py"
msrc = open(MAT).read()
if "cc_matching_mask" in msrc:
    print("matcher.py already LAD-patched — skipping")
else:
    old = "from scipy.optimize import linear_sum_assignment\n"
    assert old in msrc, "matcher scipy import anchor not found"
    msrc = msrc.replace(old, old + "from src.model.utils.lad import cc_matching_mask, length_class\n", 1)

    old = "        cost_reference: float = 1,\n    ):\n"
    assert old in msrc, "matcher __init__ signature anchor not found"
    msrc = msrc.replace(old, "        cost_reference: float = 1,\n        lad_borders=(),\n    ):\n", 1)

    old = "        self.cost_reference = cost_reference\n"
    assert old in msrc, "matcher __init__ body anchor not found"
    msrc = msrc.replace(old, old + "        self.lad_borders = lad_borders\n", 1)

    # Mask the full cost matrix once (query class = slot // N_q, since aux_post_process
    # preserves RPN selection order). Forbidden cross-class pairs get a large finite cost
    # so linear_sum_assignment steers each GT to an in-class query. Per-component cost
    # stats (cost_span/giou) are separate tensors and stay unmasked.
    old = "        cost_matrix = cost_matrix.view(batch_size, num_queries, -1).cpu()\n"
    assert old in msrc, "cost_matrix.view anchor not found"
    new = old + (
        "        if len(self.lad_borders) > 0:\n"
        "            _qcls = torch.arange(num_queries) // (num_queries // (len(self.lad_borders) + 1))\n"
        "            _gcls = length_class(tgt_spans[:, 1].cpu(), list(self.lad_borders))\n"
        "            cost_matrix = cost_matrix.masked_fill(cc_matching_mask(_qcls, _gcls).unsqueeze(0), 1e6)\n"
    )
    msrc = msrc.replace(old, new, 1)
    open(MAT, "w").write(msrc)
    print("patched", MAT)

# ---- configs ----
MY = f"{REPO}/configs/model/default.yaml"
y = open(MY).read()
if "lad_borders" in y:
    print("model/default.yaml already LAD-patched — skipping")
else:
    old = "  _target_: src.model.blocks.detector.QuerySelector\n"
    assert old in y, "query_selector config anchor not found"
    y = y.replace(old, old + "  lad_borders: []\n", 1)
    open(MY, "w").write(y)
    print("patched", MY)

LY = f"{REPO}/configs/losses/default.yaml"
ly = open(LY).read()
if "lad_borders" in ly:
    print("losses/default.yaml already LAD-patched — skipping")
else:
    old = "  _target_: src.losses.matcher.HungarianMatcher\n"
    assert old in ly, "matcher config anchor not found"
    ly = ly.replace(old, old + "  lad_borders: []\n", 1)
    open(LY, "w").write(ly)
    print("patched", LY)
