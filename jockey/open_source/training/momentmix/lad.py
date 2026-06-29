"""Length-Aware Decoder (LAD) primitives for SG-DETR (Arm E).

Adapts LA-DETR's LAD (arXiv:2412.20816) onto SG-DETR's RPN query selection:
  - `length_class`: bin a span width into one of M length classes.
  - `class_balanced_topk`: select top-N_q proposals *per length class* and lay
    them out in contiguous class-ordered slots, so the o2o query at slot i has a
    fixed length class i // N_q (no per-query tag threading needed).
  - `cc_matching_mask`: forbid Hungarian matches between a query and a GT of a
    different length class.

All borders are normalized span-widths in [0,1] (QVH ~150s; paper seconds
[13.4,31.5,75] -> normalized [0.089,0.21,0.5]). Empty borders => M=1 => every
path reduces to the stock behavior (global top-k, no mask) => bit-identical.
"""
import torch


def length_class(widths: torch.Tensor, borders) -> torch.Tensor:
    """Map normalized widths -> length-class index in [0, len(borders)]."""
    if len(borders) == 0:
        return torch.zeros_like(widths, dtype=torch.long)
    bounds = torch.as_tensor(borders, dtype=widths.dtype, device=widths.device)
    return torch.bucketize(widths, bounds)


def cc_matching_mask(query_classes: torch.Tensor, gt_classes: torch.Tensor) -> torch.Tensor:
    """(Q,), (G,) -> (Q, G) bool; True where the match is FORBIDDEN (class mismatch)."""
    return query_classes[:, None] != gt_classes[None, :]


def class_balanced_topk(
    scores: torch.Tensor,
    widths: torch.Tensor,
    borders,
    num_queries: int,
) -> torch.Tensor:
    """Per-class top-N_q proposal selection, laid out in class-ordered slots.

    Args:
        scores: (B, S) proposal objectness scores (already -inf-masked for invalid).
        widths: (B, S) proposal widths, normalized [0,1].
        borders: length-class borders (normalized). Empty => global top-k.
        num_queries: total queries; must equal M * N_q.

    Returns:
        (B, num_queries) selected proposal indices, slots [0:N_q]=class0, ...
    """
    if len(borders) == 0:
        return torch.topk(scores, num_queries, dim=1)[1]
    num_classes = len(borders) + 1
    per_class = num_queries // num_classes
    classes = length_class(widths, borders)  # (B, S)
    chunks = []
    for cls in range(num_classes):
        masked = scores.masked_fill(classes != cls, float("-inf"))
        chunks.append(torch.topk(masked, per_class, dim=1)[1])
    return torch.cat(chunks, dim=1)
