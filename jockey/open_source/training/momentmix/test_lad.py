"""TDD for Length-Aware Decoder (LAD) primitives, Arm E.

Run on the pod: cd /workspace/mmix_tools &&
  PYTHONPATH=/workspace/sg-detr /workspace/tvenv/bin/python -m pytest test_lad.py -q
"""
import torch

from src.model.utils.lad import length_class, cc_matching_mask, class_balanced_topk


def test_length_class_buckets():
    w = torch.tensor([0.05, 0.15, 0.3, 0.8])
    assert length_class(w, [0.0893, 0.21, 0.5]).tolist() == [0, 1, 2, 3]


def test_length_class_empty_borders_is_single_class():
    w = torch.tensor([0.1, 0.5, 0.9])
    assert length_class(w, []).tolist() == [0, 0, 0]


def test_cc_mask_forbids_cross_class_only():
    q = torch.tensor([0, 0, 1, 1])
    g = torch.tensor([0, 1])
    m = cc_matching_mask(q, g)  # (4,2), True = forbidden
    assert m.tolist() == [[False, True], [False, True], [True, False], [True, False]]


def test_cc_mask_single_class_forbids_nothing():
    q = torch.zeros(4, dtype=torch.long)
    g = torch.zeros(2, dtype=torch.long)
    assert not cc_matching_mask(q, g).any().item()


def test_class_balanced_topk_empty_borders_equals_global_topk():
    torch.manual_seed(0)
    scores = torch.randn(2, 20)
    widths = torch.rand(2, 20)
    idx = class_balanced_topk(scores, widths, [], num_queries=5)
    glob = torch.topk(scores, 5, dim=1)[1]
    assert torch.equal(idx.sort(1)[0], glob.sort(1)[0])


def test_class_balanced_topk_places_classes_in_contiguous_slots():
    scores = torch.tensor([[1.0, 2, 3, 4, 5, 6]])
    widths = torch.tensor([[0.05, 0.05, 0.05, 0.8, 0.8, 0.8]])  # first 3 = class0, last 3 = class1
    idx = class_balanced_topk(scores, widths, [0.5], num_queries=4)  # M=2, N_q=2
    selected_classes = length_class(widths[0][idx[0]], [0.5])
    assert selected_classes.tolist() == [0, 0, 1, 1]  # slots ordered by class


def test_matcher_cc_matching_routes_short_gt_to_short_slot():
    """End-to-end in the real matcher: a short GT whose lowest-cost query is a
    long-class slot (q2) must be matched to a short-class slot (q0/q1) instead."""
    from src.losses.matcher import HungarianMatcher

    matcher = HungarianMatcher(cost_iou=0, cost_class=0, cost_span=1, cost_giou=0,
                               cost_reference=0, lad_borders=[0.5])
    # num_queries=4 -> N_q=2: slots 0,1 = class0 (short), 2,3 = class1 (long)
    # q2 (long slot) predicts the GT exactly (lowest span cost) but is wrong-class.
    pred_spans = torch.tensor([[[0.9, 0.1], [0.9, 0.1], [0.3, 0.1], [0.9, 0.9]]])  # cxw
    outputs = {"pred_spans": pred_spans, "pred_logits": torch.zeros(1, 4, 1)}
    targets = {"span_labels": [{"spans": torch.tensor([[0.3, 0.1]])}]}  # one short GT (width 0.1 < 0.5)

    pred_idx, _ = matcher(outputs, targets, None)[0][0]
    assert pred_idx.item() in (0, 1), f"cc_matching failed: GT matched query {pred_idx.item()} (a long-class slot)"

    # sanity: WITHOUT lad it would pick the perfect-fit long-class query q2
    plain = HungarianMatcher(cost_iou=0, cost_class=0, cost_span=1, cost_giou=0, cost_reference=0)
    assert plain(outputs, targets, None)[0][0][0].item() == 2
