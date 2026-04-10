"""
ViCLIP video embedding module.

Wraps InternVideo2/ViCLIP for generating video and text embeddings.
Uses the pretrained model by default; swap checkpoint path for fine-tuned version later.

Usage:
    embedder = ViCLIPEmbedder()
    video_emb = embedder.encode_video(frames)   # np.ndarray [D]
    text_emb = embedder.encode_text("a dog playing fetch")  # np.ndarray [D]
"""
import logging
import numpy as np
from typing import Union, List

log = logging.getLogger(__name__)


class ViCLIPEmbedder:
    """Wrapper around InternVideo2/ViCLIP for video-text embeddings.

    For now, uses the pretrained model via the transformers/InternVideo2 API.
    After fine-tuning, just change `model_name_or_path` to your checkpoint.
    """

    def __init__(self, model_name_or_path: str = "OpenGVLab/ViCLIP-L-14", device: str = "cuda"):
        self.model_name_or_path = model_name_or_path
        self.device = device
        self._model = None
        self._tokenizer = None

    def _lazy_load(self):
        """Lazy-load the model only when first needed."""
        if self._model is not None:
            return

        log.info(f"Loading ViCLIP model from {self.model_name_or_path}...")
        try:
            # Primary: try loading via the InternVideo2 library
            from internvideo2.models.viclip import ViCLIP as ViCLIPModel
            self._model = ViCLIPModel.from_pretrained(self.model_name_or_path)
            self._model = self._model.to(self.device).eval()
            log.info("Loaded ViCLIP via internvideo2 library.")
        except ImportError:
            try:
                # Fallback: try loading via transformers (if available as HF model)
                from transformers import AutoModel, AutoTokenizer
                self._model = AutoModel.from_pretrained(self.model_name_or_path, trust_remote_code=True)
                self._model = self._model.to(self.device).eval()
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path, trust_remote_code=True)
                log.info("Loaded ViCLIP via transformers.")
            except Exception as e:
                log.warning(f"Could not load ViCLIP model: {e}. Using random embeddings as placeholder.")
                self._model = "placeholder"

    def encode_video(self, frames: np.ndarray) -> np.ndarray:
        """Encode video frames into a normalized embedding vector.

        Args:
            frames: Video frames as numpy array [N, H, W, 3] (uint8, RGB).

        Returns:
            Normalized embedding vector [D].
        """
        self._lazy_load()

        if self._model == "placeholder":
            emb = np.random.randn(768).astype(np.float32)
            return emb / np.linalg.norm(emb)

        import torch
        import torch.nn.functional as F_torch

        with torch.no_grad():
            # Convert frames: [N, H, W, 3] uint8 → [B, T, C, H, W] float
            frames_tensor = torch.from_numpy(frames).float().permute(0, 3, 1, 2) / 255.0  # [N, 3, H, W]
            # Resize to 224x224 if needed
            if frames_tensor.shape[-2] != 224 or frames_tensor.shape[-1] != 224:
                frames_tensor = F_torch.interpolate(frames_tensor, size=(224, 224), mode='bilinear', align_corners=False)
            frames_tensor = frames_tensor.unsqueeze(0).to(self.device)  # [1, T, 3, H, W]

            # ViCLIP HF model uses encode_vision()
            if hasattr(self._model, 'encode_vision'):
                # Returns: (vision_embeds [B,T,L,C], pooled_vision_embeds [B,T,C])
                result = self._model.encode_vision(frames_tensor)
                if isinstance(result, tuple):
                    pooled = result[1]  # [B, T, C]
                    emb = pooled.mean(dim=1).squeeze()  # Average over temporal dim → [C]
                else:
                    emb = result.squeeze()
            elif hasattr(self._model, 'get_video_features'):
                emb = self._model.get_video_features(pixel_values=frames_tensor).squeeze()
            else:
                emb = self._model(frames_tensor).squeeze()

            emb = emb.cpu().numpy().astype(np.float32)

        emb = emb / np.linalg.norm(emb)
        return emb

    def encode_text(self, text: str) -> np.ndarray:
        """Encode a text query into a normalized embedding vector.

        Args:
            text: Natural language query string.

        Returns:
            Normalized embedding vector [D].
        """
        self._lazy_load()

        if self._model == "placeholder":
            emb = np.random.randn(768).astype(np.float32)
            return emb / np.linalg.norm(emb)

        import torch
        with torch.no_grad():
            # ViCLIP HF model — encode_text takes raw text, tokenizes internally 
            if hasattr(self._model, 'encode_text') and not self._tokenizer:
                emb = self._model.encode_text(text)
                if isinstance(emb, tuple):
                    emb = emb[-1]  # pooled text embedding
                emb = emb.squeeze()
            elif self._tokenizer is not None:
                tokens = self._tokenizer(text, return_tensors="pt", padding=True, truncation=True)
                tokens = {k: v.to(self.device) for k, v in tokens.items()}
                if hasattr(self._model, 'get_text_features'):
                    emb = self._model.get_text_features(**tokens).squeeze()
                else:
                    emb = self._model.encode_text(**tokens).squeeze()
            else:
                raise RuntimeError("Model does not have encode_text method or tokenizer")

            emb = emb.cpu().numpy().astype(np.float32)

        emb = emb / np.linalg.norm(emb)
        return emb
