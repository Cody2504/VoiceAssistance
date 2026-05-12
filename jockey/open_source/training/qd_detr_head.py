"""
QD-DETR-style temporal grounding head.

Architectural contrast with `grounding_head.GroundingHead`:

    grounding_head : query is prepended as a token, mixes via self-attention only
                     → query and clips compete for attention slots; cross-clip
                       reasoning is query-agnostic at the lowest layer.

    qd_detr_head   : query is injected into every clip via CROSS-attention BEFORE
                     self-attention → every clip token becomes query-dependent,
                     i.e. the same video produces different representations for
                     different queries. This is the QD-DETR core insight
                     (Moon et al. CVPR 2023).

Inputs:
    visual [B, N, V]   per-clip features (InternVideo2-aligned, V depends on model)
    query  [B, Q]      text query embedding (must be in the same space as visual,
                       i.e. produced by the SAME backbone's text tower)

Outputs:
    saliency_logits  [B, N]    per-clip relevance (sigmoid → BCE target)
    boundary_pred    [B, 2]    normalized (start, end) ∈ [0, 1]

Notes:
  - Audio / caption / global modalities are intentionally NOT supported here.
    The point of this head is to test whether a unified VLM encoder alone
    matches the multi-modal stack. Re-add modalities only if the ablation
    shows the unified encoder is insufficient.
  - Negative-pair saliency loss is exposed but optional (default off in the
    skeleton; flip on for the proper QD-DETR training recipe).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

# Reuse loss + metric primitives from the existing head — they're correct and
# task-defining, no reason to fork them.
from jockey.open_source.training.grounding_head import (
    PositionalEncoding,
    temporal_iou_1d,
    recall_at_iou,
    mean_iou,
)


@dataclass
class QDDETRConfig:
    visual_dim: int = 768        # InternVideo2-Stage2_1B CLIP-aligned dim (verify at load)
    query_dim: int = 768         # Same backbone as visual (aligned space)
    hidden_dim: int = 256
    num_self_layers: int = 2     # Self-attn transformer over query-conditioned clips
    num_heads: int = 8
    max_shots: int = 256
    dropout: float = 0.1
    use_moment_query: bool = True  # DETR-style learnable moment query for boundary head


class QDDETRHead(nn.Module):
    """Query-Dependent temporal grounding head.

    Param budget (default config, hidden=256, 2 self-attn layers): ~3-5M trainable.
    Fits Colab T4 trivially. Increase hidden_dim/num_self_layers to grow.
    """

    def __init__(self, cfg: QDDETRConfig):
        super().__init__()
        self.cfg = cfg
        h = cfg.hidden_dim

        # Projections into shared hidden space
        self.proj_visual = nn.Linear(cfg.visual_dim, h)
        self.proj_query = nn.Linear(cfg.query_dim, h)
        self.input_norm = nn.LayerNorm(h)
        self.input_dropout = nn.Dropout(cfg.dropout)

        # Cross-attention block: clip tokens (Q) attend to broadcast query (K, V)
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=h, num_heads=cfg.num_heads, dropout=cfg.dropout, batch_first=True,
        )
        self.cross_norm = nn.LayerNorm(h)

        # FFN after cross-attention (transformer-block style: residual + FFN + norm)
        self.cross_ffn = nn.Sequential(
            nn.Linear(h, h * 4),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(h * 4, h),
            nn.Dropout(cfg.dropout),
        )
        self.cross_ffn_norm = nn.LayerNorm(h)

        # Self-attention transformer over query-conditioned clip tokens
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=h,
            nhead=cfg.num_heads,
            dim_feedforward=h * 4,
            dropout=cfg.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.self_attn = nn.TransformerEncoder(encoder_layer, num_layers=cfg.num_self_layers)

        self.pos_enc = PositionalEncoding(h, max_len=cfg.max_shots + 8, dropout=cfg.dropout)

        # Saliency head (per-clip)
        self.saliency_head = nn.Sequential(
            nn.Linear(h, h),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(h, 1),
        )

        # Boundary head — two flavors:
        #   (a) DETR-style: learnable moment query attends to encoded clips,
        #       decoded vector goes through a 2-dim regression head.
        #   (b) Pool-only: mean-pool encoded clips, then 2-dim regression.
        # (a) is QD-DETR-faithful and learns to focus on the relevant region.
        if cfg.use_moment_query:
            self.moment_query = nn.Parameter(torch.randn(1, 1, h) * 0.02)
            self.moment_decoder = nn.MultiheadAttention(
                embed_dim=h, num_heads=cfg.num_heads, dropout=cfg.dropout, batch_first=True,
            )
            self.moment_norm = nn.LayerNorm(h)
        self.boundary_head = nn.Sequential(
            nn.Linear(h, h),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(h, 2),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def num_trainable_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def forward(
        self,
        visual: torch.Tensor,                       # [B, N, V]
        query: torch.Tensor,                        # [B, Q]
        shot_mask: Optional[torch.Tensor] = None,   # [B, N] bool, True = valid
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, N, _ = visual.shape

        clip_tok = self.input_dropout(self.input_norm(self.proj_visual(visual)))   # [B, N, h]
        query_tok = self.proj_query(query).unsqueeze(1)                            # [B, 1, h]

        # PyTorch convention: True = ignore in key_padding_mask.
        clip_kpm = (~shot_mask) if shot_mask is not None else None

        # --- Cross-attention: clip tokens attend to the query ---
        attn_out, _ = self.cross_attn(
            query=clip_tok, key=query_tok, value=query_tok, need_weights=False,
        )  # [B, N, h]
        x = self.cross_norm(clip_tok + attn_out)
        x = self.cross_ffn_norm(x + self.cross_ffn(x))

        # --- Positional encoding + self-attention over query-conditioned clips ---
        x = self.pos_enc(x)
        x = self.self_attn(x, src_key_padding_mask=clip_kpm)                        # [B, N, h]

        # --- Saliency head: per-clip relevance ---
        saliency_logits = self.saliency_head(x).squeeze(-1)                         # [B, N]

        # --- Boundary head: DETR-style moment decoder or pooled regression ---
        if self.cfg.use_moment_query:
            mq = self.moment_query.expand(B, -1, -1)                                # [B, 1, h]
            decoded, _ = self.moment_decoder(
                query=mq, key=x, value=x, key_padding_mask=clip_kpm, need_weights=False,
            )
            moment = self.moment_norm(decoded).squeeze(1)                           # [B, h]
        else:
            if shot_mask is not None:
                m = shot_mask.float().unsqueeze(-1)
                moment = (x * m).sum(dim=1) / m.sum(dim=1).clamp(min=1.0)
            else:
                moment = x.mean(dim=1)
        boundary_pred = torch.sigmoid(self.boundary_head(moment))                   # [B, 2]

        return saliency_logits, boundary_pred


# ---------------------------------------------------------------------------
# Loss
# ---------------------------------------------------------------------------

def qd_detr_loss(
    saliency_logits: torch.Tensor,      # [B, N]
    boundary_pred: torch.Tensor,        # [B, 2] in [0, 1]
    gt_relevance: torch.Tensor,         # [B, N] in [0, 1] (soft) or {0, 1}
    gt_boundary_norm: torch.Tensor,     # [B, 2] in [0, 1]
    shot_mask: Optional[torch.Tensor] = None,
    w_sal: float = 1.0,
    w_l1: float = 10.0,
    w_iou: float = 1.0,
    neg_saliency_logits: Optional[torch.Tensor] = None,  # [B, N] from a wrong-query pair
    w_neg: float = 1.0,
) -> Dict[str, torch.Tensor]:
    """Saliency BCE + boundary L1 + 1D-IoU; optional negative-pair saliency.

    Default weights follow Moment-DETR / QD-DETR conventions (boundary L1
    heavily weighted vs. saliency so the boundary head escapes the
    "predict the mean moment" failure mode).

    Negative-pair term (when provided): expects `neg_saliency_logits` from
    feeding the same video with a *different* query. We push them toward 0.
    """
    # Saliency BCE
    sal_per = F.binary_cross_entropy_with_logits(
        saliency_logits, gt_relevance, reduction="none"
    )
    if shot_mask is not None:
        m = shot_mask.float()
        sal_loss = (sal_per * m).sum() / m.sum().clamp(min=1.0)
    else:
        sal_loss = sal_per.mean()

    # Boundary L1
    l1_loss = F.l1_loss(boundary_pred, gt_boundary_norm)

    # 1D temporal IoU (enforce ordering)
    pred_lo = torch.min(boundary_pred[:, 0], boundary_pred[:, 1])
    pred_hi = torch.max(boundary_pred[:, 0], boundary_pred[:, 1])
    iou = temporal_iou_1d(pred_lo, pred_hi, gt_boundary_norm[:, 0], gt_boundary_norm[:, 1])
    iou_loss = (1.0 - iou).mean()

    total = w_sal * sal_loss + w_l1 * l1_loss + w_iou * iou_loss

    # Negative-pair saliency: punish any positive activation when the query
    # doesn't belong to this video.
    neg_loss = None
    if neg_saliency_logits is not None:
        zeros = torch.zeros_like(neg_saliency_logits)
        neg_per = F.binary_cross_entropy_with_logits(
            neg_saliency_logits, zeros, reduction="none"
        )
        if shot_mask is not None:
            m = shot_mask.float()
            neg_loss = (neg_per * m).sum() / m.sum().clamp(min=1.0)
        else:
            neg_loss = neg_per.mean()
        total = total + w_neg * neg_loss

    out: Dict[str, torch.Tensor] = {
        "total": total,
        "sal": sal_loss.detach(),
        "l1": l1_loss.detach(),
        "iou_loss": iou_loss.detach(),
        "mIoU": iou.mean().detach(),
    }
    if neg_loss is not None:
        out["neg"] = neg_loss.detach()
    return out


# Re-export the eval helpers for convenience.
__all__ = [
    "QDDETRConfig",
    "QDDETRHead",
    "qd_detr_loss",
    "recall_at_iou",
    "mean_iou",
]
