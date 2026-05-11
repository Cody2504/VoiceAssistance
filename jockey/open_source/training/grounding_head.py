"""
Grounding Head — multimodal temporal-grounding model trained on top of frozen features.

This is the **single trained component** of the thesis. Encoders (ViCLIP, wav2vec2,
text-emb-3-large) stay frozen; this head is what gets fine-tuned on Colab.

Architecture:
    Inputs (precomputed, frozen):
        visual   [B, N, 768]   per-shot ViCLIP/CLIP-L features
        audio    [B, N, 768]   per-shot wav2vec2 features
        caption  [B, N, 3072]  per-shot caption (ASR-text) embeddings
        query    [B, 3072]     text query embedding (the user's search query)
        global   [B, 3072]     [GLOBAL] metadata embedding (optional)

    Forward:
        Project each modality to hidden_dim
        Sum-fuse per-shot active modalities → shot tokens
        Prepend [CLS] [GLOBAL?] [QUERY] special tokens
        + Sinusoidal positional encoding
        TransformerEncoder (num_layers, num_heads)

    Outputs:
        relevance_logits [B, N]   per-shot relevance (sigmoid → BCE target)
        boundary_pred    [B, 2]   normalized (start, end) ∈ [0, 1] from [CLS]

Loss:
    L = w_rel·BCE(relevance, gt_inside_moment)
      + w_l1 ·L1(boundary, gt_boundary_norm)
      + w_iou·(1 − IoU(boundary, gt_boundary_norm))

Eval:
    R@1@IoU=θ  for θ ∈ {0.3, 0.5, 0.7}, mIoU

Designed to be Colab-T4 friendly (~15-25M trainable params, frozen features cached).
"""
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class GroundingConfig:
    """Configuration for the grounding head.

    Note on dimensions and spaces:
        - visual_dim/audio_dim/caption_dim come from the frozen encoders.
        - query_dim must match the encoder used in `precompute_queries.py`.
          Default 768 = CLIP-text (aligned with CLIP-visual → free query↔shot
          alignment, the architecturally correct choice). Set query_dim=3072
          only if you intentionally embed queries with text-embedding-3-large.
    """

    visual_dim: int = 768
    audio_dim: int = 768
    caption_dim: int = 3072
    query_dim: int = 768   # CLIP-text by default — aligned with visual features
    global_dim: int = 3072  # MetadataEncoder uses text-embedding-3-large (separate from query)
    hidden_dim: int = 512
    num_layers: int = 4
    num_heads: int = 8
    max_shots: int = 256
    dropout: float = 0.1
    use_audio: bool = True
    use_caption: bool = True
    use_global: bool = True


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div)
        pe[:, 1::2] = torch.cos(position * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(x + self.pe[:, : x.size(1), :])


class GroundingHead(nn.Module):
    """Multimodal grounding head with fusion transformer + relevance + boundary heads."""

    def __init__(self, cfg: GroundingConfig):
        super().__init__()
        self.cfg = cfg
        h = cfg.hidden_dim

        # Per-modality projections
        self.proj_visual = nn.Linear(cfg.visual_dim, h)
        self.proj_audio = nn.Linear(cfg.audio_dim, h) if cfg.use_audio else None
        self.proj_caption = nn.Linear(cfg.caption_dim, h) if cfg.use_caption else None
        self.proj_query = nn.Linear(cfg.query_dim, h)
        self.proj_global = nn.Linear(cfg.global_dim, h) if cfg.use_global else None

        # Shot-level normalization after sum-fusion
        self.shot_norm = nn.LayerNorm(h)
        self.shot_dropout = nn.Dropout(cfg.dropout)

        # Special tokens
        self.cls_token = nn.Parameter(torch.randn(1, 1, h) * 0.02)

        # Positional encoding (covers prefix + shots)
        self.pos_enc = PositionalEncoding(h, max_len=cfg.max_shots + 8, dropout=cfg.dropout)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=h,
            nhead=cfg.num_heads,
            dim_feedforward=h * 4,
            dropout=cfg.dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=cfg.num_layers)
        self.layer_norm = nn.LayerNorm(h)

        # Output heads
        self.relevance_head = nn.Sequential(
            nn.Linear(h, h),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(h, 1),
        )
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

    def _fuse_shots(
        self,
        visual: torch.Tensor,
        audio: Optional[torch.Tensor],
        caption: Optional[torch.Tensor],
    ) -> torch.Tensor:
        x = self.proj_visual(visual)
        if self.proj_audio is not None and audio is not None:
            x = x + self.proj_audio(audio)
        if self.proj_caption is not None and caption is not None:
            x = x + self.proj_caption(caption)
        return self.shot_dropout(self.shot_norm(x))

    def forward(
        self,
        visual: torch.Tensor,                           # [B, N, V]
        query: torch.Tensor,                            # [B, Q]
        audio: Optional[torch.Tensor] = None,           # [B, N, A]
        caption: Optional[torch.Tensor] = None,         # [B, N, C]
        global_emb: Optional[torch.Tensor] = None,      # [B, Q]
        shot_mask: Optional[torch.Tensor] = None,       # [B, N] bool, True = valid
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (relevance_logits [B, N], boundary_pred [B, 2] in [0, 1])."""
        B = visual.size(0)

        shot_tokens = self._fuse_shots(visual, audio, caption)            # [B, N, h]

        # Prefix tokens: [CLS] [GLOBAL?] [QUERY]
        prefix = [self.cls_token.expand(B, -1, -1)]
        if self.proj_global is not None and global_emb is not None:
            prefix.append(self.proj_global(global_emb).unsqueeze(1))
        prefix.append(self.proj_query(query).unsqueeze(1))
        prefix_tensor = torch.cat(prefix, dim=1)                          # [B, P, h]
        n_prefix = prefix_tensor.size(1)

        sequence = torch.cat([prefix_tensor, shot_tokens], dim=1)         # [B, P+N, h]

        # src_key_padding_mask: True = ignore (PyTorch convention)
        attn_mask = None
        if shot_mask is not None:
            prefix_pad = torch.zeros(
                B, n_prefix, dtype=torch.bool, device=visual.device
            )
            shot_pad = ~shot_mask
            attn_mask = torch.cat([prefix_pad, shot_pad], dim=1)

        sequence = self.pos_enc(sequence)
        out = self.transformer(sequence, src_key_padding_mask=attn_mask)
        out = self.layer_norm(out)

        cls_out = out[:, 0, :]                                            # [B, h]
        shot_out = out[:, n_prefix:, :]                                   # [B, N, h]

        relevance_logits = self.relevance_head(shot_out).squeeze(-1)      # [B, N]
        boundary_pred = torch.sigmoid(self.boundary_head(cls_out))        # [B, 2] in [0,1]

        return relevance_logits, boundary_pred


# ---------------------------------------------------------------------------
# Loss & metrics
# ---------------------------------------------------------------------------

def temporal_iou_1d(
    pred_start: torch.Tensor,
    pred_end: torch.Tensor,
    gt_start: torch.Tensor,
    gt_end: torch.Tensor,
    eps: float = 1e-6,
) -> torch.Tensor:
    """Element-wise 1D IoU between predicted and GT spans. All inputs shape [B]."""
    inter_lo = torch.max(pred_start, gt_start)
    inter_hi = torch.min(pred_end, gt_end)
    inter = torch.clamp(inter_hi - inter_lo, min=0)
    union_lo = torch.min(pred_start, gt_start)
    union_hi = torch.max(pred_end, gt_end)
    union = torch.clamp(union_hi - union_lo, min=eps)
    return inter / union


def grounding_loss(
    relevance_logits: torch.Tensor,        # [B, N]
    boundary_pred: torch.Tensor,           # [B, 2] in [0, 1]
    gt_relevance: torch.Tensor,            # [B, N] in {0, 1}, float
    gt_boundary_norm: torch.Tensor,        # [B, 2] in [0, 1]
    shot_mask: Optional[torch.Tensor] = None,
    w_rel: float = 1.0,
    w_l1: float = 1.0,
    w_iou: float = 0.5,
) -> Dict[str, torch.Tensor]:
    """Combined loss: BCE(relevance) + L1(boundary) + (1 − IoU(boundary))."""
    # Relevance BCE — mask out padded shots
    rel_per = F.binary_cross_entropy_with_logits(
        relevance_logits, gt_relevance, reduction="none"
    )
    if shot_mask is not None:
        m = shot_mask.float()
        rel_loss = (rel_per * m).sum() / m.sum().clamp(min=1.0)
    else:
        rel_loss = rel_per.mean()

    # Boundary L1
    l1_loss = F.l1_loss(boundary_pred, gt_boundary_norm)

    # 1D temporal IoU (forced positive ordering)
    pred_lo = torch.min(boundary_pred[:, 0], boundary_pred[:, 1])
    pred_hi = torch.max(boundary_pred[:, 0], boundary_pred[:, 1])
    iou = temporal_iou_1d(pred_lo, pred_hi, gt_boundary_norm[:, 0], gt_boundary_norm[:, 1])
    iou_loss = (1.0 - iou).mean()

    total = w_rel * rel_loss + w_l1 * l1_loss + w_iou * iou_loss
    return {
        "total": total,
        "rel": rel_loss.detach(),
        "l1": l1_loss.detach(),
        "iou_loss": iou_loss.detach(),
        "mIoU": iou.mean().detach(),
    }


@torch.no_grad()
def recall_at_iou(
    boundary_pred: torch.Tensor,       # [B, 2] in [0, 1]
    gt_boundary_norm: torch.Tensor,    # [B, 2] in [0, 1]
    iou_thresh: float = 0.5,
) -> float:
    """R@1@IoU=θ — fraction of predictions with IoU ≥ θ to GT."""
    pred_lo = torch.min(boundary_pred[:, 0], boundary_pred[:, 1])
    pred_hi = torch.max(boundary_pred[:, 0], boundary_pred[:, 1])
    iou = temporal_iou_1d(pred_lo, pred_hi, gt_boundary_norm[:, 0], gt_boundary_norm[:, 1])
    return (iou >= iou_thresh).float().mean().item()


@torch.no_grad()
def mean_iou(
    boundary_pred: torch.Tensor,
    gt_boundary_norm: torch.Tensor,
) -> float:
    pred_lo = torch.min(boundary_pred[:, 0], boundary_pred[:, 1])
    pred_hi = torch.max(boundary_pred[:, 0], boundary_pred[:, 1])
    iou = temporal_iou_1d(pred_lo, pred_hi, gt_boundary_norm[:, 0], gt_boundary_norm[:, 1])
    return iou.mean().item()
