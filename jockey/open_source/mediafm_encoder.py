"""
MediaFM Context Encoder — Transformer-based contextualized shot representations.

Inspired by Netflix's MediaFM architecture:
  Input:  [CLS] [GLOBAL] [shot_1] [shot_2] ... [shot_n]
    → Linear projection to hidden_dim
    → + Positional embeddings
    → Transformer Encoder (3 layers, 8 heads)
    → Linear projection back to fused_dim
  Output: Contextualized shot representations

The Transformer learns to contextualize each shot's embedding based on
surrounding shots and the title-level [GLOBAL] context.

Usage:
    encoder = MediaFMEncoder(fused_dim=4608)
    ctx_shots, cls_emb = encoder.forward(shot_embeddings, global_embedding)
"""
import logging
import math
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

log = logging.getLogger(__name__)


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding (same as original Transformer)."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # [1, max_len, d_model]
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, seq_len, d_model]"""
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class MediaFMEncoder(nn.Module):
    """MediaFM-inspired Transformer encoder for contextualized shot representations.

    Architecture (matching the diagram):
        Input:  [CLS] [GLOBAL] [shot_1] [shot_2] ... [shot_n]
        ↓ Linear projection (fused_dim → hidden_dim)
        ↓ + Positional encoding
        ↓ Transformer Encoder (num_layers layers, num_heads heads)
        ↓ Linear projection (hidden_dim → fused_dim)
        Output: Contextualized shot representations

    Special tokens:
        [CLS]    — Learnable; output becomes the video-level representation
        [GLOBAL] — From title metadata encoder; provides context to all shots
        [MASK]   — Learnable; used during Masked Shot Modeling training
    """

    def __init__(
        self,
        fused_dim: int = 4608,
        hidden_dim: int = 512,
        num_layers: int = 3,
        num_heads: int = 8,
        max_shots: int = 256,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.fused_dim = fused_dim
        self.hidden_dim = hidden_dim

        # Learnable special tokens (in fused space, before projection)
        self.cls_token = nn.Parameter(torch.randn(1, 1, fused_dim) * 0.02)
        self.mask_token = nn.Parameter(torch.randn(1, 1, fused_dim) * 0.02)

        # Projection layers
        self.input_proj = nn.Linear(fused_dim, hidden_dim)
        self.output_proj = nn.Linear(hidden_dim, fused_dim)

        # Positional encoding
        self.pos_encoding = PositionalEncoding(hidden_dim, max_len=max_shots + 2, dropout=dropout)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Layer norm
        self.layer_norm = nn.LayerNorm(hidden_dim)

        self._init_weights()

    def _init_weights(self):
        """Initialize weights with small values."""
        for module in [self.input_proj, self.output_proj]:
            nn.init.xavier_uniform_(module.weight)
            nn.init.zeros_(module.bias)

    def forward(
        self,
        shot_embeddings: torch.Tensor,
        global_embedding: Optional[torch.Tensor] = None,
        mask_indices: Optional[List[int]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass through the MediaFM Transformer encoder.

        Args:
            shot_embeddings: Per-shot fused embeddings [B, N, fused_dim] or [N, fused_dim].
                             If 2D, a batch dimension is added.
            global_embedding: Title metadata embedding [B, fused_dim] or [fused_dim].
                              If None, a zero vector is used.
            mask_indices: Optional list of shot indices to mask (for MSM training).
                          Masked shots are replaced with the learnable [MASK] token.

        Returns:
            Tuple of:
                contextualized_shots: [B, N, fused_dim] — contextualized shot embeddings
                cls_output: [B, fused_dim] — video-level representation from [CLS]
        """
        # Handle dimensions
        if shot_embeddings.dim() == 2:
            shot_embeddings = shot_embeddings.unsqueeze(0)  # [1, N, D]

        B, N, D = shot_embeddings.shape
        device = shot_embeddings.device

        # Apply masking if requested (for MSM training)
        if mask_indices is not None:
            shot_embeddings = shot_embeddings.clone()
            mask = self.mask_token.expand(B, -1, -1)  # [B, 1, D]
            for idx in mask_indices:
                if idx < N:
                    shot_embeddings[:, idx, :] = mask.squeeze(1)

        # Build sequence: [CLS] [GLOBAL] [shot_1] ... [shot_n]
        cls = self.cls_token.expand(B, -1, -1)  # [B, 1, D]

        if global_embedding is not None:
            if global_embedding.dim() == 1:
                global_embedding = global_embedding.unsqueeze(0)  # [1, D]
            if global_embedding.dim() == 2:
                global_embedding = global_embedding.unsqueeze(1)  # [B, 1, D]
            if global_embedding.size(0) == 1 and B > 1:
                global_embedding = global_embedding.expand(B, -1, -1)
            sequence = torch.cat([cls, global_embedding, shot_embeddings], dim=1)  # [B, 2+N, D]
        else:
            # Use zeros for [GLOBAL] if no metadata provided
            global_zeros = torch.zeros(B, 1, D, device=device, dtype=shot_embeddings.dtype)
            sequence = torch.cat([cls, global_zeros, shot_embeddings], dim=1)  # [B, 2+N, D]

        # Project to hidden dim
        hidden = self.input_proj(sequence)  # [B, 2+N, hidden_dim]

        # Add positional encoding
        hidden = self.pos_encoding(hidden)

        # Transformer encoding
        hidden = self.transformer(hidden)  # [B, 2+N, hidden_dim]
        hidden = self.layer_norm(hidden)

        # Project back to fused dim
        output = self.output_proj(hidden)  # [B, 2+N, fused_dim]

        # Extract outputs
        cls_output = output[:, 0, :]           # [B, fused_dim] — video-level
        contextualized = output[:, 2:, :]      # [B, N, fused_dim] — shot-level (skip CLS + GLOBAL)

        return contextualized, cls_output


class MediaFMEncoderWrapper:
    """Non-PyTorch wrapper for using MediaFMEncoder in the indexing pipeline.

    Handles device management, numpy conversion, and checkpoint loading.
    Designed to match the lazy-load pattern used by other pipeline components.
    """

    def __init__(
        self,
        fused_dim: int = 4608,
        hidden_dim: int = 512,
        num_layers: int = 3,
        num_heads: int = 8,
        device: str = "cuda",
        checkpoint_path: Optional[str] = None,
    ):
        self.fused_dim = fused_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.device = device
        self.checkpoint_path = checkpoint_path
        self._encoder = None

    def _lazy_load(self):
        """Lazy-load the encoder."""
        if self._encoder is not None:
            return

        log.info(
            f"Initializing MediaFM encoder "
            f"(dim={self.fused_dim}, hidden={self.hidden_dim}, "
            f"layers={self.num_layers}, heads={self.num_heads})..."
        )

        self._encoder = MediaFMEncoder(
            fused_dim=self.fused_dim,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
            num_heads=self.num_heads,
        )

        if self.checkpoint_path and os.path.isfile(self.checkpoint_path):
            log.info(f"Loading MediaFM checkpoint from {self.checkpoint_path}")
            state_dict = torch.load(self.checkpoint_path, map_location="cpu")
            self._encoder.load_state_dict(state_dict)

        self._encoder = self._encoder.to(self.device).eval()
        param_count = sum(p.numel() for p in self._encoder.parameters())
        log.info(f"MediaFM encoder loaded ({param_count:,} parameters).")

    def contextualize(
        self,
        shot_embeddings: List[np.ndarray],
        global_embedding: Optional[np.ndarray] = None,
    ) -> Tuple[List[np.ndarray], np.ndarray]:
        """Contextualize a sequence of shot embeddings.

        Args:
            shot_embeddings: List of N per-shot fused embeddings, each [fused_dim].
            global_embedding: Optional [GLOBAL] token from metadata encoder [fused_dim].

        Returns:
            Tuple of:
                contextualized_shots: List of N contextualized embeddings, each [fused_dim].
                cls_embedding: Video-level embedding [fused_dim].
        """
        self._lazy_load()

        # Stack shots into tensor
        shots_np = np.stack(shot_embeddings, axis=0)  # [N, fused_dim]
        shots_tensor = torch.from_numpy(shots_np).float().to(self.device)

        global_tensor = None
        if global_embedding is not None:
            global_tensor = torch.from_numpy(global_embedding).float().to(self.device)

        with torch.no_grad():
            ctx_shots, cls_emb = self._encoder(shots_tensor, global_tensor)

        # Convert back to numpy, L2-normalize each
        ctx_shots = ctx_shots.squeeze(0).cpu().numpy()  # [N, fused_dim]
        cls_emb = cls_emb.squeeze(0).cpu().numpy()       # [fused_dim]

        # Normalize
        ctx_list = []
        for i in range(ctx_shots.shape[0]):
            emb = ctx_shots[i]
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            ctx_list.append(emb)

        cls_norm = np.linalg.norm(cls_emb)
        if cls_norm > 0:
            cls_emb = cls_emb / cls_norm

        return ctx_list, cls_emb
