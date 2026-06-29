"""TDD for ReferenceRefinementHead (RDSA-inspired, Arm F).

A 3-reference-point (left / center / right) successor to BoundaryRefinementHead.
Refines center and width directly in cxw space so it can RE-CENTER a prediction
(the diagnosed short-moment failure: center-in-GT 10% / IoU 0.097 at rank-1),
which the 2-point start/end head structurally cannot do.

Run on the pod: cd /workspace/mmix_tools &&
  PYTHONPATH=/workspace/sg-detr /workspace/tvenv/bin/python -m pytest test_reference_head.py -q
"""
import torch

from src.model.blocks.boundary_head import ReferenceRefinementHead


def _last_linear(mlp):
    return [m for m in mlp.modules() if isinstance(m, torch.nn.Linear)][-1]


def test_output_shape_and_finite():
    B, Q, L, D = 2, 5, 16, 32
    head = ReferenceRefinementHead(D)
    out = head(torch.randn(B, Q, D), torch.randn(B, L, D), torch.rand(B, Q, 2))
    assert out.shape == (B, Q, 2)
    assert torch.isfinite(out).all()


def test_identity_at_init():
    """Zero-init -> refined == decoder spans at step 0 (no matcher shock)."""
    B, Q, L, D = 2, 4, 20, 32
    torch.manual_seed(0)
    head = ReferenceRefinementHead(D)
    head.eval()
    q = torch.randn(B, Q, D)
    mem = torch.randn(B, L, D)
    center = torch.rand(B, Q) * 0.4 + 0.3   # [0.3, 0.7]
    width = torch.rand(B, Q) * 0.2 + 0.1    # [0.1, 0.3]
    spans = torch.stack([center, width], dim=-1)
    out = head(q, mem, spans)
    assert torch.allclose(out, spans, atol=1e-2), f"not identity: {(out - spans).abs().max()}"


def test_width_stays_in_unit_interval_under_extreme_offsets():
    """cxw-native width = sigmoid(...) is in (0,1) by construction, so no negative
    width can ever reach the gIoU assert — even when offsets are pushed hard both ways."""
    B, Q, L, D = 1, 4, 10, 16
    head = ReferenceRefinementHead(D)
    head.eval()
    spans = torch.tensor([[[0.5, 0.2], [0.5, 0.2], [0.5, 0.2], [0.5, 0.2]]])
    q = torch.randn(B, 4, D)
    mem = torch.randn(B, L, D)
    for bias in (25.0, -25.0):
        torch.nn.init.constant_(_last_linear(head.width_mlp).bias, bias)
        width = head(q, mem, spans)[..., 1]
        assert (width >= 0).all() and (width <= 1).all(), f"width left [0,1] at bias {bias}: {width}"


def test_center_reference_is_used():
    """Defining property vs the 2-point head: this head samples the CENTER clip and
    uses it. Perturbing the center clip (never sampled by a start/end-only head)
    must move the refined center."""
    D, L = 8, 21
    head = ReferenceRefinementHead(D)
    torch.nn.init.normal_(_last_linear(head.center_mlp).weight, std=0.5)  # let f_center flow out
    head.eval()
    torch.manual_seed(1)
    q = torch.randn(1, 1, D)
    mem = torch.randn(1, L, D)
    spans = torch.tensor([[[0.5, 0.6]]])  # center 0.5->clip10, left 0.2->clip4, right 0.8->clip16 (distinct)
    out_a = head(q, mem, spans)
    mem2 = mem.clone()
    mem2[0, 10] += 10.0                    # perturb ONLY the center clip
    out_b = head(q, mem2, spans)
    assert (out_b[..., 0] - out_a[..., 0]).abs().item() > 1e-4, "center clip had no effect -> f_center unused"


def test_gradients_flow_to_inputs_and_params():
    """Wiring guard: memory + query stay differentiable, head params receive grad."""
    B, Q, L, D = 2, 3, 12, 16
    head = ReferenceRefinementHead(D)
    for mlp in (head.center_mlp, head.width_mlp):
        torch.nn.init.normal_(_last_linear(mlp).weight, std=0.1)
    q = torch.randn(B, Q, D, requires_grad=True)
    mem = torch.randn(B, L, D, requires_grad=True)
    spans = torch.rand(B, Q, 2) * 0.6 + 0.2
    head(q, mem, spans).sum().backward()
    assert q.grad is not None and q.grad.abs().sum() > 0
    assert mem.grad is not None and mem.grad.abs().sum() > 0
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in head.parameters())


# --- Arm G: center->score role-split (attacks the RANKING failure) ---

def test_without_score_flag_returns_tensor_unchanged():
    """Arm F path (default flag off) stays byte-compatible: returns a single tensor."""
    D = 16
    head = ReferenceRefinementHead(D)  # default with_center_score=False
    out = head(torch.randn(1, 3, D), torch.randn(1, 8, D), torch.rand(1, 3, 2))
    assert torch.is_tensor(out) and out.shape == (1, 3, 2)


def test_center_score_returns_tuple_and_zero_at_init():
    """with_center_score=True -> forward returns (cxw, score_delta); zero-init means
    score_delta is exactly 0 at step 0 (no ranking shock) and cxw is still identity."""
    B, Q, L, D = 2, 4, 20, 32
    torch.manual_seed(0)
    head = ReferenceRefinementHead(D, with_center_score=True)
    head.eval()
    q = torch.randn(B, Q, D)
    mem = torch.randn(B, L, D)
    center = torch.rand(B, Q) * 0.4 + 0.3
    width = torch.rand(B, Q) * 0.2 + 0.1
    spans = torch.stack([center, width], dim=-1)
    out = head(q, mem, spans)
    assert isinstance(out, tuple) and len(out) == 2, "score mode must return (cxw, score_delta)"
    cxw, score_delta = out
    assert torch.allclose(cxw, spans, atol=1e-2), "cxw not identity at init"
    assert score_delta.shape == (B, Q, 1)
    assert torch.allclose(score_delta, torch.zeros_like(score_delta), atol=1e-6), "score_delta not 0 at init"


def test_center_score_responds_to_center_clip():
    """The ranking fix: the center action-feature must DRIVE the score. Perturbing the
    center clip (a 2-point head never samples it) must move the score delta."""
    D, L = 8, 21
    head = ReferenceRefinementHead(D, with_center_score=True)
    torch.nn.init.normal_(_last_linear(head.score_mlp).weight, std=0.5)  # let f_center flow to score
    head.eval()
    torch.manual_seed(2)
    q = torch.randn(1, 1, D)
    mem = torch.randn(1, L, D)
    spans = torch.tensor([[[0.5, 0.6]]])  # center 0.5 -> clip 10
    _, s_a = head(q, mem, spans)
    mem2 = mem.clone()
    mem2[0, 10] += 10.0
    _, s_b = head(q, mem2, spans)
    assert (s_b - s_a).abs().item() > 1e-4, "center clip had no effect on score -> f_center not driving rank"
