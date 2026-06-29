"""BAM-DETR-style boundary refinement head for SG-DETR (Part 2b).

Pools single-scale encoder memory at each predicted boundary and regresses a
per-boundary offset in inverse-sigmoid space (DAB convention, matching
decoder.update_reference_points). Operates on the final decoder spans and
returns refined spans in the same cxw [0,1] format, so the matcher and span
losses consume them unchanged via the model.py `pred_spans` injection point.

Reference: Pilhyeon Lee, BAM-DETR (ECCV'24) — boundary-oriented regression.
"""
import torch
from torch import nn

from src.model.blocks.feed_forward import SlimMLP
from src.model.utils.model_utils import inverse_sigmoid
from src.utils.span_utils import span_cxw_to_xx, span_xx_to_cxw


def sample_memory_at(memory: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
    """Linear-interpolate clip-grid memory at normalized positions.

    Args:
        memory: (B, L, D) single-scale per-clip encoder memory.
        t: (B, Q) boundary positions in [0, 1].

    Returns:
        (B, Q, D) features sampled at each position.
    """
    batch, length, dim = memory.shape
    pos = t.clamp(0, 1) * (length - 1)
    lo = pos.floor().long().clamp(0, length - 1)
    hi = (lo + 1).clamp(max=length - 1)
    weight = (pos - lo.float()).unsqueeze(-1)

    def gather(idx: torch.Tensor) -> torch.Tensor:
        return memory.gather(1, idx.unsqueeze(-1).expand(batch, idx.shape[1], dim))

    return gather(lo) * (1 - weight) + gather(hi) * weight


def _zero_init_last_linear(mlp: nn.Module) -> None:
    """Zero the final Linear so the MLP emits 0 at init -> the head is identity."""
    last = None
    for module in mlp.modules():
        if isinstance(module, nn.Linear):
            last = module
    if last is not None:
        nn.init.zeros_(last.weight)
        if last.bias is not None:
            nn.init.zeros_(last.bias)


class BoundaryRefinementHead(nn.Module):
    """Refine final decoder spans from boundary-local memory features.

    Two stability properties (learned from the Part-1 negative-width crash):
    - **Identity at init**: the offset MLPs' last layer is zero-initialized, so
      at step 0 refined spans equal the decoder spans (no shock to the matcher).
    - **Ordered output**: start/end are min/max-sorted, so width >= 0 always and
      no degenerate span can reach the gIoU `end >= start` assert.
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.start_mlp = SlimMLP(d_model * 2, d_model, 1, num_layers=3)
        self.end_mlp = SlimMLP(d_model * 2, d_model, 1, num_layers=3)
        _zero_init_last_linear(self.start_mlp)
        _zero_init_last_linear(self.end_mlp)

    def forward(
        self,
        query_emb: torch.Tensor,
        memory: torch.Tensor,
        spans_cxw: torch.Tensor,
    ) -> torch.Tensor:
        """Args: query_emb (B,Q,D), memory (B,L,D), spans_cxw (B,Q,2) -> refined cxw (B,Q,2)."""
        xx = span_cxw_to_xx(spans_cxw)
        f_s = sample_memory_at(memory, xx[..., 0])
        f_e = sample_memory_at(memory, xx[..., 1])
        d_s = self.start_mlp(torch.cat([query_emb, f_s], dim=-1)).squeeze(-1)
        d_e = self.end_mlp(torch.cat([query_emb, f_e], dim=-1)).squeeze(-1)
        start = (inverse_sigmoid(xx[..., 0]) + d_s).sigmoid()
        end = (inverse_sigmoid(xx[..., 1]) + d_e).sigmoid()
        refined_xx = torch.stack([torch.minimum(start, end), torch.maximum(start, end)], dim=-1)
        return span_xx_to_cxw(refined_xx)


class ReferenceRefinementHead(nn.Module):
    """RDSA-inspired 3-reference-point refinement (Arm F) — successor to
    BoundaryRefinementHead.

    Samples the clip-grid encoder memory at THREE reference points — left (start),
    **center**, right (end) — and refines the span's center and width directly in
    cxw space. The center sample (absent from the 2-point boundary head) is what
    lets the head *re-center* a misplaced prediction — the diagnosed short-moment
    failure (rank-1 center-in-GT 10% / IoU 0.097 vs 65-74% for middle/long).

    Two structural safeties, both free here:
    - **width = sigmoid(.) in (0,1)**: cxw-native, so no negative-width span can
      ever reach the gIoU `end >= start` assert (no min/max ordering needed).
    - **Identity at init**: the center/width offset MLPs are zero-initialized, so
      at step 0 refined spans equal the decoder spans (no shock to the matcher).

    Inspired by SDST's Reference-based Deformable Self-Attention (arXiv:2507.07744),
    adapted as a single post-decoder head over RPN-proposal spans (no learned query
    bank, unlike LA-DETR's LAD).
    """

    def __init__(self, d_model: int, with_center_score: bool = False):
        super().__init__()
        self.center_mlp = SlimMLP(d_model * 4, d_model, 1, num_layers=3)
        self.width_mlp = SlimMLP(d_model * 4, d_model, 1, num_layers=3)
        _zero_init_last_linear(self.center_mlp)
        _zero_init_last_linear(self.width_mlp)
        # Arm G: center->score role-split. The center action-feature feeds the
        # foreground score so a short candidate with real action content gets
        # RANKED higher (attacks the diagnosed rank-1 center-in-GT 10% failure).
        # Zero-init -> score_delta = 0 at step 0 (no ranking/matcher shock).
        self.score_mlp = None
        if with_center_score:
            self.score_mlp = SlimMLP(d_model * 2, d_model, 1, num_layers=3)
            _zero_init_last_linear(self.score_mlp)

    def forward(
        self,
        query_emb: torch.Tensor,
        memory: torch.Tensor,
        spans_cxw: torch.Tensor,
    ):
        """query_emb (B,Q,D), memory (B,L,D), spans_cxw (B,Q,2).

        Returns refined cxw (B,Q,2); if center-score is enabled, returns the tuple
        (refined cxw, score_delta (B,Q,1)) to be added onto outputs_class[-1].
        """
        center = spans_cxw[..., 0]
        width = spans_cxw[..., 1]
        xx = span_cxw_to_xx(spans_cxw)
        f_l = sample_memory_at(memory, xx[..., 0])
        f_c = sample_memory_at(memory, center)
        f_r = sample_memory_at(memory, xx[..., 1])
        ctx = torch.cat([query_emb, f_l, f_c, f_r], dim=-1)
        d_c = self.center_mlp(ctx).squeeze(-1)
        d_w = self.width_mlp(ctx).squeeze(-1)
        new_center = (inverse_sigmoid(center) + d_c).sigmoid()
        new_width = (inverse_sigmoid(width) + d_w).sigmoid()
        refined = torch.stack([new_center, new_width], dim=-1)
        if self.score_mlp is None:
            return refined
        score_delta = self.score_mlp(torch.cat([query_emb, f_c], dim=-1))  # (B,Q,1)
        return refined, score_delta
