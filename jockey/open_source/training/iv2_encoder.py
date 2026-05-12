"""
InternVideo2 encoder wrapper — visual + text features in a shared space.

Replaces the ViCLIP + wav2vec2 + Whisper visual/text stack with a single
contrastively-aligned video-language model. Same forward feeds both the
retrieval head (this module) and any downstream generation head (Video-LLaVA,
VideoLLaMA-3) that accepts InternVideo2 features.

Default model: `OpenGVLab/InternVideo2-Stage2_1B-224p-f4` (Apache-2.0, ~1B params,
fp16 weights ≈ 2 GB, fits T4 16 GB with batch=1 video at 4 frames/clip).

Two installation paths — try them in order:

  PATH A (preferred, simplest):
      pip install transformers>=4.40 timm einops decord
      The HF `AutoModel.from_pretrained(..., trust_remote_code=True)` flow runs
      the model's bundled modeling code. This works for most OpenGVLab repos.

  PATH B (fallback, if PATH A errors):
      git clone https://github.com/OpenGVLab/InternVideo
      cd InternVideo/InternVideo2/multi_modality && pip install -e .
      Then set `IV2_BACKEND=opengvlab` and adapt `_load_model` below to import
      the repo's `InternVideo2` class directly.

The wrapper exposes a placeholder mode (random embeddings) when the model
cannot be loaded — same pattern as `viclip_embedder.py` — so the rest of the
pipeline (Dataset, head, training loop) can be developed and unit-tested
without a GPU.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Sequence

import numpy as np

log = logging.getLogger(__name__)


# InternVideo2-Stage2_1B's CLIP-aligned projection dim. Verified empirically at
# load time (see `_check_dim`) — if the model returns a different size we
# overwrite this attribute on the instance.
DEFAULT_EMBEDDING_DIM = 768

# Standard ImageNet normalization — also what InternVideo2 expects.
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)


class InternVideo2Encoder:
    """InternVideo2 model wrapper (vision tower + text tower, shared embedding space).

    Frames-in / features-out interface. Frames must already be sampled (this
    module does not extract frames from video files — use `extract_frames` from
    `jockey.open_source.indexer` for that).

    Visual frames per clip: `frames_per_clip` (default 4). InternVideo2-1B was
    trained with 4-frame clips at 224×224. Use 8 for slightly stronger features
    at 2× VRAM.
    """

    def __init__(
        self,
        model_name_or_path: str = "OpenGVLab/InternVideo2-Stage2_1B-224p-f4",
        device: str = "cuda",
        frames_per_clip: int = 4,
        image_size: int = 224,
        dtype: str = "fp16",
    ):
        self.model_name_or_path = model_name_or_path
        self.device = device
        self.frames_per_clip = frames_per_clip
        self.image_size = image_size
        self.dtype_str = dtype

        self._model = None
        self._tokenizer = None
        self._torch_dtype = None
        self.embedding_dim: int = DEFAULT_EMBEDDING_DIM

        # HF auth — InternVideo2 weights are public, but the user may have a
        # token configured for rate-limit reasons.
        self._hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HF_API_KEY")

    # ------------------------------------------------------------------ load --

    def _resolve_device(self) -> str:
        if self.device.startswith("cuda"):
            try:
                import torch
                if not torch.cuda.is_available():
                    log.warning(
                        "CUDA requested for InternVideo2 but no CUDA driver found. "
                        "Falling back to CPU (very slow — placeholder mode recommended)."
                    )
                    self.device = "cpu"
            except ImportError:
                self.device = "cpu"
        return self.device

    def _torch_dtype_from_str(self):
        import torch
        return {
            "fp32": torch.float32,
            "fp16": torch.float16,
            "bf16": torch.bfloat16,
        }.get(self.dtype_str, torch.float16)

    def _load_model(self):
        """Lazy-load the model. Falls back to placeholder on any failure."""
        if self._model is not None:
            return

        device = self._resolve_device()
        log.info(f"Loading InternVideo2 from {self.model_name_or_path} on {device} ({self.dtype_str})...")

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            self._torch_dtype = self._torch_dtype_from_str()
            self._model = AutoModel.from_pretrained(
                self.model_name_or_path,
                trust_remote_code=True,
                torch_dtype=self._torch_dtype,
                token=self._hf_token,
            ).to(device).eval()

            # Tokenizer for the text tower. Some InternVideo2 configs ship the
            # tokenizer separately (BertTokenizer); others bundle it.
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name_or_path,
                    trust_remote_code=True,
                    token=self._hf_token,
                )
            except Exception as e:
                log.warning(
                    f"AutoTokenizer failed for {self.model_name_or_path}: {e}. "
                    f"Text encoding will use the model's bundled tokenize fn if present."
                )
                self._tokenizer = None

            n_params = sum(p.numel() for p in self._model.parameters())
            log.info(f"InternVideo2 loaded: {n_params/1e6:.1f}M params on {device}")
            self._check_dim()
        except Exception as e:
            log.warning(
                f"InternVideo2 load failed: {e}\n"
                f"  → Falling back to PLACEHOLDER mode (random embeddings). "
                f"This lets you unit-test downstream code, but features are noise.\n"
                f"  → To actually load the model, see the docstring at the top of "
                f"this file (PATH A / PATH B)."
            )
            self._model = "placeholder"

    def _check_dim(self):
        """Probe the model with a dummy input to discover the embedding dim."""
        try:
            import torch
            dummy_frames = [
                np.zeros((self.frames_per_clip, self.image_size, self.image_size, 3), dtype=np.uint8)
            ]
            v = self.encode_video_batch(dummy_frames)
            if v.ndim == 2 and v.shape[1] > 0:
                self.embedding_dim = int(v.shape[1])
                log.info(f"  embedding_dim = {self.embedding_dim}")
        except Exception as e:
            log.warning(f"  embedding_dim probe failed ({e}); using default {self.embedding_dim}.")

    # ----------------------------------------------------------- preprocessing --

    def _preprocess_frames(self, frames: np.ndarray) -> "torch.Tensor":
        """Resize + normalize a [T, H, W, 3] uint8 RGB array into [T, 3, H', W'] float.

        InternVideo2 expects ImageNet-normalized 224x224 frames in CHW order.
        Pads / truncates the temporal axis to `frames_per_clip`.
        """
        import torch
        import torch.nn.functional as F

        t = frames.shape[0]
        # Time-axis pad/truncate to exactly `frames_per_clip`
        if t < self.frames_per_clip:
            pad_count = self.frames_per_clip - t
            pad = np.repeat(frames[-1:], pad_count, axis=0) if t > 0 else np.zeros(
                (pad_count, self.image_size, self.image_size, 3), dtype=np.uint8
            )
            frames = np.concatenate([frames, pad], axis=0)
        elif t > self.frames_per_clip:
            indices = np.linspace(0, t - 1, self.frames_per_clip, dtype=int)
            frames = frames[indices]

        x = torch.from_numpy(frames).float() / 255.0  # [T, H, W, 3]
        x = x.permute(0, 3, 1, 2)  # [T, 3, H, W]

        if x.shape[-1] != self.image_size or x.shape[-2] != self.image_size:
            x = F.interpolate(
                x, size=(self.image_size, self.image_size),
                mode="bilinear", align_corners=False,
            )

        mean = torch.tensor(_IMAGENET_MEAN).view(1, 3, 1, 1)
        std = torch.tensor(_IMAGENET_STD).view(1, 3, 1, 1)
        x = (x - mean) / std
        return x  # [T, 3, H, W]

    # ------------------------------------------------------- video / text fwd --

    def encode_video_batch(self, frames_list: Sequence[np.ndarray]) -> np.ndarray:
        """Encode a batch of clips. Returns L2-normalized [N, D] features.

        Each item in `frames_list` is one clip's frames as [T, H, W, 3] uint8 RGB.
        Empty/None items return a zero row.
        """
        self._load_model()
        n = len(frames_list)
        if n == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        # Track which clips are non-empty so empty slots get zeros, not random noise.
        valid_idx, valid_clips = [], []
        for i, f in enumerate(frames_list):
            if f is None or getattr(f, "size", 0) == 0:
                continue
            valid_idx.append(i)
            valid_clips.append(f)

        if self._model == "placeholder":
            out = np.zeros((n, self.embedding_dim), dtype=np.float32)
            for i in valid_idx:
                r = np.random.randn(self.embedding_dim).astype(np.float32)
                out[i] = r / max(np.linalg.norm(r), 1e-12)
            return out

        if not valid_clips:
            return np.zeros((n, self.embedding_dim), dtype=np.float32)

        import torch

        # Stack clips: [B, T, 3, H, W]
        clips = torch.stack([self._preprocess_frames(c) for c in valid_clips], dim=0)
        clips = clips.to(self.device, dtype=self._torch_dtype)

        # InternVideo2's HF API varies between checkpoints. Try the common
        # method names in order. The user can override this dispatch table if
        # their checkpoint exposes a different name.
        feats = self._call_vision_tower(clips)  # [B, D]

        feats_np = feats.detach().to(torch.float32).cpu().numpy()
        norms = np.linalg.norm(feats_np, axis=1, keepdims=True).clip(min=1e-12)
        feats_np = feats_np / norms

        out = np.zeros((n, feats_np.shape[1]), dtype=np.float32)
        for j, i in enumerate(valid_idx):
            out[i] = feats_np[j]
        return out

    def _call_vision_tower(self, clips: "torch.Tensor") -> "torch.Tensor":
        """Dispatch to the model's vision encoder. Tries several common names.

        InternVideo2 HF repos have shipped under at least these method names:
          - `encode_vision(clips, test=True)` returning (feat, proj) tuple
          - `get_vid_feat(clips)` returning [B, D]
          - `forward_visual(clips)` returning [B, D]
        """
        import torch

        with torch.no_grad():
            # 1. encode_vision (tuple return)
            if hasattr(self._model, "encode_vision"):
                out = self._model.encode_vision(clips, test=True)
                # Typical return: (visual_feat, visual_proj) where proj is the
                # CLIP-aligned vector we want for retrieval.
                if isinstance(out, (tuple, list)) and len(out) >= 2:
                    return out[1]
                return out

            # 2. get_vid_feat
            if hasattr(self._model, "get_vid_feat"):
                return self._model.get_vid_feat(clips)

            # 3. forward_visual
            if hasattr(self._model, "forward_visual"):
                return self._model.forward_visual(clips)

            # 4. fallback: call the model and look for a vision head in output
            out = self._model(clips)
            for attr in ("vision_proj", "image_embeds", "pooler_output"):
                v = getattr(out, attr, None) if not isinstance(out, torch.Tensor) else None
                if v is not None:
                    return v
            if isinstance(out, torch.Tensor):
                return out

        raise RuntimeError(
            "Cannot find vision encoding method on InternVideo2 model. Tried: "
            "encode_vision, get_vid_feat, forward_visual, __call__. "
            "Inspect dir(model) and add the right name to _call_vision_tower."
        )

    def encode_text_batch(self, texts: List[str]) -> np.ndarray:
        """Encode text queries. Returns L2-normalized [N, D] aligned with video features."""
        self._load_model()
        n = len(texts)
        if n == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        if self._model == "placeholder":
            r = np.random.randn(n, self.embedding_dim).astype(np.float32)
            return r / np.linalg.norm(r, axis=1, keepdims=True).clip(min=1e-12)

        import torch

        # Empty strings → space so tokenizer doesn't choke.
        safe = [t if (t and t.strip()) else " " for t in texts]

        if self._tokenizer is None:
            raise RuntimeError(
                "InternVideo2 tokenizer not loaded. Either (1) the checkpoint "
                "doesn't bundle one — supply --tokenizer separately; or (2) "
                "AutoTokenizer load failed. See logs at startup."
            )

        with torch.no_grad():
            tok = self._tokenizer(
                safe, return_tensors="pt", padding=True, truncation=True, max_length=77,
            )
            tok = {k: v.to(self.device) for k, v in tok.items()}
            feats = self._call_text_tower(tok, safe)  # [N, D]

        feats_np = feats.detach().to(torch.float32).cpu().numpy()
        feats_np = feats_np / np.linalg.norm(feats_np, axis=1, keepdims=True).clip(min=1e-12)
        return feats_np

    def _call_text_tower(self, tok_inputs, raw_texts) -> "torch.Tensor":
        """Dispatch to the model's text encoder. Tries common method names."""
        import torch

        with torch.no_grad():
            if hasattr(self._model, "encode_text"):
                out = self._model.encode_text(
                    tok_inputs.get("input_ids"),
                    tok_inputs.get("attention_mask"),
                )
                if isinstance(out, (tuple, list)) and len(out) >= 2:
                    return out[1]
                return out
            if hasattr(self._model, "get_txt_feat"):
                return self._model.get_txt_feat(raw_texts)
            if hasattr(self._model, "forward_text"):
                return self._model.forward_text(**tok_inputs)

        raise RuntimeError(
            "Cannot find text encoding method on InternVideo2 model. Tried: "
            "encode_text, get_txt_feat, forward_text. "
            "Inspect dir(model) and add the right name to _call_text_tower."
        )

    # ----------------------------------------------------- single-clip convenience --

    def encode_video(self, frames: np.ndarray) -> np.ndarray:
        return self.encode_video_batch([frames])[0]

    def encode_text(self, text: str) -> np.ndarray:
        return self.encode_text_batch([text])[0]
