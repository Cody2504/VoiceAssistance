"""
Video/Image CLIP embedding module.

Uses openai/clip-vit-large-patch14 from HuggingFace transformers.
For video, extracts frames and averages their CLIP embeddings.

Usage:
    embedder = ViCLIPEmbedder(device="cpu")
    video_emb = embedder.encode_video(frames)   # np.ndarray [768]
    text_emb = embedder.encode_text("a dog playing fetch")  # np.ndarray [768]
"""
import logging
import os
import numpy as np
from typing import Union, List

log = logging.getLogger(__name__)

EMBEDDING_DIM = 768  # clip-vit-large-patch14 output dimension


class ViCLIPEmbedder:
    """Wrapper around OpenAI CLIP ViT-L/14 for video-text embeddings.

    Uses the standard CLIP model (768-dim) from HuggingFace transformers.
    Video frames are encoded individually and averaged to produce
    a single video-level embedding (mean pooling over frames).
    """

    def __init__(self, model_name_or_path: str = "openai/clip-vit-large-patch14", device: str = "cuda"):
        self.model_name_or_path = model_name_or_path
        self.device = device
        self._model = None
        self._processor = None
        self._tokenizer = None
        self._hf_token = os.environ.get("HF_API_KEY", None)

    def _lazy_load(self):
        """Lazy-load the model only when first needed."""
        if self._model is not None:
            return

        log.info(f"Loading CLIP model from {self.model_name_or_path}...")
        try:
            from transformers import CLIPModel, CLIPProcessor, CLIPTokenizer

            self._model = CLIPModel.from_pretrained(
                self.model_name_or_path,
                token=self._hf_token,
            )
            self._model = self._model.to(self.device).eval()
            self._processor = CLIPProcessor.from_pretrained(
                self.model_name_or_path,
                token=self._hf_token,
            )
            self._tokenizer = CLIPTokenizer.from_pretrained(
                self.model_name_or_path,
                token=self._hf_token,
            )
            param_count = sum(p.numel() for p in self._model.parameters())
            log.info(f"Loaded CLIP model ({param_count:,} params, device={self.device})")
        except Exception as e:
            log.warning(f"Could not load CLIP model: {e}. Using random embeddings as placeholder.")
            self._model = "placeholder"

    def encode_video(self, frames: np.ndarray) -> np.ndarray:
        """Encode video frames into a normalized embedding vector.

        Processes each frame through CLIP's vision encoder and averages the
        frame embeddings (mean pooling) to produce a single video embedding.

        Args:
            frames: Video frames as numpy array [N, H, W, 3] (uint8, RGB).

        Returns:
            Normalized embedding vector [768].
        """
        self._lazy_load()

        if self._model == "placeholder":
            emb = np.random.randn(EMBEDDING_DIM).astype(np.float32)
            return emb / np.linalg.norm(emb)

        import torch
        from PIL import Image

        with torch.no_grad():
            # Convert numpy frames to PIL images
            pil_images = [Image.fromarray(frame) for frame in frames]

            # Process all frames as a batch
            inputs = self._processor(images=pil_images, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Get image embeddings [N, 768]
            image_features = self._model.get_image_features(**inputs)

            # Mean pool over frames → [768]
            emb = image_features.mean(dim=0).cpu().numpy().astype(np.float32)

        emb = emb / np.linalg.norm(emb)
        return emb

    def encode_text(self, text: str) -> np.ndarray:
        """Encode a text query into a normalized embedding vector.

        Args:
            text: Natural language query string.

        Returns:
            Normalized embedding vector [768].
        """
        self._lazy_load()

        if self._model == "placeholder":
            emb = np.random.randn(EMBEDDING_DIM).astype(np.float32)
            return emb / np.linalg.norm(emb)

        import torch

        with torch.no_grad():
            inputs = self._tokenizer(
                text, return_tensors="pt", padding=True, truncation=True, max_length=77,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            text_features = self._model.get_text_features(**inputs)
            emb = text_features.squeeze().cpu().numpy().astype(np.float32)

        emb = emb / np.linalg.norm(emb)
        return emb
