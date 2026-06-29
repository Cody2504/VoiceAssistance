"""TDD for BoundaryRefinementHead (BAM-DETR-style, Part 2b).

Run on the pod: cd /workspace/mmix_tools &&
  PYTHONPATH=/workspace/sg-detr /workspace/tvenv/bin/python -m pytest test_boundary_head.py -q
"""
import torch

from src.model.blocks.boundary_head import BoundaryRefinementHead


def test_output_shape_and_finite():
    B, Q, L, D = 2, 5, 16, 32
    head = BoundaryRefinementHead(D)
    q = torch.randn(B, Q, D)
    mem = torch.randn(B, L, D)
    spans = torch.rand(B, Q, 2)  # cxw, roughly in [0,1]
    out = head(q, mem, spans)
    assert out.shape == (B, Q, 2)
    assert torch.isfinite(out).all()


def test_identity_at_init():
    """At init the head must be an exact no-op (refined == decoder spans), so it
    cannot shock the span branch at step 0 — the Part-1 negative-width crash lesson."""
    B, Q, L, D = 2, 4, 20, 32
    torch.manual_seed(0)
    head = BoundaryRefinementHead(D)
    head.eval()
    q = torch.randn(B, Q, D)
    mem = torch.randn(B, L, D)
    # spans whose start/end sit safely inside (0,1) so inverse_sigmoid roundtrips
    center = torch.rand(B, Q) * 0.4 + 0.3   # [0.3, 0.7]
    width = torch.rand(B, Q) * 0.2 + 0.1    # [0.1, 0.3]
    spans = torch.stack([center, width], dim=-1)
    out = head(q, mem, spans)
    assert torch.allclose(out, spans, atol=1e-2), f"not identity at init: max diff {(out - spans).abs().max()}"


class _Const(torch.nn.Module):
    """Offset stub that always emits a fixed value, to force a boundary inversion."""

    def __init__(self, value: float):
        super().__init__()
        self.value = value

    def forward(self, x):
        return torch.full((*x.shape[:-1], 1), self.value)


def test_widths_nonnegative_under_inverting_offsets():
    """Even when the offset MLPs push start past end, the refined span must keep
    end >= start (no negative width reaching the gIoU assert)."""
    B, Q, L, D = 1, 3, 10, 16
    head = BoundaryRefinementHead(D)
    # force a strong inversion: start pushed toward 1, end toward 0
    head.start_mlp = _Const(5.0)
    head.end_mlp = _Const(-5.0)
    q = torch.zeros(B, Q, D)
    mem = torch.zeros(B, L, D)
    spans = torch.tensor([[[0.5, 0.2], [0.5, 0.2], [0.5, 0.2]]])  # cxw mid spans
    out = head(q, mem, spans)
    width = out[..., 1]
    assert (width >= -1e-6).all(), f"negative width produced: {width}"


def test_gradients_flow_to_inputs_and_params():
    """Guard for the wiring step: memory and query must stay differentiable
    (not detached) and the head's params must receive gradient."""
    B, Q, L, D = 2, 3, 12, 16
    head = BoundaryRefinementHead(D)
    # nudge off the zero-init identity so the full memory/query path carries signal
    for mlp in (head.start_mlp, head.end_mlp):
        linears = [m for m in mlp.modules() if isinstance(m, torch.nn.Linear)]
        torch.nn.init.normal_(linears[-1].weight, std=0.1)
    q = torch.randn(B, Q, D, requires_grad=True)
    mem = torch.randn(B, L, D, requires_grad=True)
    spans = torch.rand(B, Q, 2) * 0.6 + 0.2
    head(q, mem, spans).sum().backward()
    assert q.grad is not None and q.grad.abs().sum() > 0
    assert mem.grad is not None and mem.grad.abs().sum() > 0
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in head.parameters())
