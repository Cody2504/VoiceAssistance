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

# Fallback used only in placeholder mode (when the model couldn't load).
# The real dim is discovered from `model.config.projection_dim` on _lazy_load:
#   clip-vit-base-patch32 → 512
#   clip-vit-large-patch14 → 768
DEFAULT_EMBEDDING_DIM = 768


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
        # Discovered from the loaded model's projection_dim; populated by _lazy_load.
        # Defaults to the placeholder fallback until the model is actually loaded.
        self.embedding_dim = DEFAULT_EMBEDDING_DIM
        self._hf_token = os.environ.get("HF_TOKEN") or None

    def _resolve_device(self) -> str:
        """Resolve device with CUDA-availability fallback to CPU.

        Without this fallback, a CPU-only box silently degrades to random
        embeddings, which is invisible until training fails downstream.
        """
        if self.device.startswith("cuda"):
            try:
                import torch
                if not torch.cuda.is_available():
                    log.warning(
                        f"CUDA requested for CLIP but no CUDA driver found. "
                        f"Falling back to CPU (slow but correct)."
                    )
                    self.device = "cpu"
            except ImportError:
                self.device = "cpu"
        return self.device

    def _lazy_load(self):
        """Lazy-load the model only when first needed."""
        if self._model is not None:
            return

        device = self._resolve_device()
        log.info(f"Loading CLIP model from {self.model_name_or_path} on {device}...")
        try:
            from transformers import CLIPModel, CLIPProcessor, CLIPTokenizer

            self._model = CLIPModel.from_pretrained(
                self.model_name_or_path,
                token=self._hf_token,
            )
            self._model = self._model.to(device).eval()
            self._processor = CLIPProcessor.from_pretrained(
                self.model_name_or_path,
                token=self._hf_token,
            )
            self._tokenizer = CLIPTokenizer.from_pretrained(
                self.model_name_or_path,
                token=self._hf_token,
            )
            # Discover the actual projection dim (B/32 → 512, L/14 → 768).
            try:
                proj_dim = int(self._model.config.projection_dim)
                if proj_dim != self.embedding_dim:
                    log.info(f"CLIP projection_dim = {proj_dim} (was {self.embedding_dim})")
                self.embedding_dim = proj_dim
            except AttributeError:
                log.warning(
                    f"Could not read projection_dim from model config; "
                    f"keeping default {self.embedding_dim}."
                )

            param_count = sum(p.numel() for p in self._model.parameters())
            log.info(f"Loaded CLIP model ({param_count:,} params, device={self.device}, dim={self.embedding_dim})")
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
            emb = np.random.randn(self.embedding_dim).astype(np.float32)
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
            output = self._model.get_image_features(**inputs)
            # transformers >=5.x returns BaseModelOutputWithPooling; extract tensor
            image_features = self._extract_features(output, modality="image")

            # Mean pool over frames → [768]
            emb = image_features.mean(dim=0).cpu().numpy().astype(np.float32)

        emb = emb / np.linalg.norm(emb)
        return emb

    @staticmethod
    def _extract_features(output, modality: str = "image"):
        """Extract the embedding tensor from CLIPModel output.

        Handles both old transformers (<5.x, returns tensor directly)
        and new transformers (>=5.x, returns BaseModelOutputWithPooling).
        """
        import torch
        if isinstance(output, torch.Tensor):
            return output
        # transformers >=5.x: try known attributes
        for attr in ("image_embeds", "text_embeds", "pooler_output", "last_hidden_state"):
            val = getattr(output, attr, None)
            if val is not None:
                if attr == "last_hidden_state":
                    return val.mean(dim=1)  # pool over sequence
                return val
        raise TypeError(f"Cannot extract {modality} features from {type(output).__name__}")

    def encode_video_batch(self, frames_list):
        """Encode multiple shots' frames in a single CLIP forward pass.

        Args:
            frames_list: List of N_shots arrays, each [N_frames, H, W, 3] uint8 RGB.

        Returns:
            np.ndarray [N_shots, 768] of L2-normalized per-shot embeddings.
        """
        self._lazy_load()
        n_shots = len(frames_list)
        if n_shots == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        import torch
        from PIL import Image

        # Flatten all frames across shots; remember per-shot counts to re-group.
        # Done first so the placeholder branch can respect None/empty shots the same way.
        flat_pil = []
        shot_counts = []
        for frames in frames_list:
            if frames is None or frames.size == 0:
                shot_counts.append(0)
                continue
            shot_counts.append(int(frames.shape[0]))
            for f in frames:
                flat_pil.append(Image.fromarray(f))

        if self._model == "placeholder":
            out = np.zeros((n_shots, self.embedding_dim), dtype=np.float32)
            for i, n in enumerate(shot_counts):
                if n == 0:
                    continue
                r = np.random.randn(self.embedding_dim).astype(np.float32)
                out[i] = r / max(np.linalg.norm(r), 1e-12)
            return out

        result = np.zeros((n_shots, self.embedding_dim), dtype=np.float32)
        if not flat_pil:
            return result

        with torch.no_grad():
            inputs = self._processor(images=flat_pil, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            output = self._model.get_image_features(**inputs)
            frame_features = self._extract_features(output, modality="image")  # [TotalFrames, 768]

        # Group frames back into shots and mean-pool per shot.
        offset = 0
        for i, n in enumerate(shot_counts):
            if n == 0:
                continue
            shot_emb = frame_features[offset:offset + n].mean(dim=0).cpu().numpy().astype(np.float32)
            norm = np.linalg.norm(shot_emb)
            result[i] = shot_emb / max(norm, 1e-12)
            offset += n
        return result

    def encode_text_batch(self, texts):
        """Encode multiple text strings into CLIP-text embeddings in one forward.

        CLIP text is aligned with CLIP vision in the same dot-product space — use
        this (NOT text-embedding-3-large) for QUERY embeddings in the grounding
        head, so the query lives in the same space as the visual features.

        Args:
            texts: List of strings.

        Returns:
            np.ndarray [N, 768] L2-normalized CLIP text embeddings.
        """
        self._lazy_load()
        n = len(texts)
        if n == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        if self._model == "placeholder":
            r = np.random.randn(n, self.embedding_dim).astype(np.float32)
            return r / np.linalg.norm(r, axis=1, keepdims=True).clip(min=1e-12)

        import torch

        # Replace empty strings with a space — tokenizer chokes on truly empty input.
        safe = [t if (t and t.strip()) else " " for t in texts]
        with torch.no_grad():
            inputs = self._tokenizer(
                safe, return_tensors="pt", padding=True, truncation=True, max_length=77,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            output = self._model.get_text_features(**inputs)
            features = self._extract_features(output, modality="text")  # [N, 768]
            emb = features.cpu().numpy().astype(np.float32)
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-12)
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
            emb = np.random.randn(self.embedding_dim).astype(np.float32)
            return emb / np.linalg.norm(emb)

        import torch

        with torch.no_grad():
            inputs = self._tokenizer(
                text, return_tensors="pt", padding=True, truncation=True, max_length=77,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            output = self._model.get_text_features(**inputs)
            text_features = self._extract_features(output, modality="text")
            emb = text_features.squeeze().cpu().numpy().astype(np.float32)

        emb = emb / np.linalg.norm(emb)
        return emb
