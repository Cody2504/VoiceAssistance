"""
Configuration for the open-source Jockey pipeline.
Loads from .env file and environment variables.

API models (via OpenRouter):
  - Text embeddings: openai/text-embedding-3-large
  - Video QA / VLM: qwen/qwen3-vl-8b-instruct

Local models (via HuggingFace):
  - Video encoder: OpenGVLab/ViCLIP
  - Audio encoder: facebook/wav2vec2-base-960h
"""
import os
from dataclasses import dataclass
from typing import Optional

# Load .env file from jockey/ directory
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


@dataclass
class PipelineConfig:
    """Central configuration for all open-source pipeline components."""

    # --- OpenRouter API ---
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- HuggingFace ---
    hf_api_key: str = os.environ.get("HF_API_KEY", "")

    # --- Qdrant ---
    qdrant_url: str = os.environ.get("QDRANT_URL", "localhost")
    qdrant_port: int = int(os.environ.get("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = os.environ.get("QDRANT_API_KEY", None)

    # --- ViCLIP (Video Embeddings — Local HuggingFace) ---
    viclip_model_name: str = os.environ.get("VICLIP_MODEL", "openai/clip-vit-large-patch14")
    viclip_device: str = os.environ.get("VICLIP_DEVICE", "cuda")
    viclip_embedding_dim: int = 768

    # --- Audio Encoder (wav2vec2 — Local HuggingFace) ---
    audio_encoder_model: str = os.environ.get("AUDIO_ENCODER_MODEL", "facebook/wav2vec2-base-960h")
    audio_encoder_device: str = os.environ.get("AUDIO_ENCODER_DEVICE", "cuda")
    audio_embedding_dim: int = 768

    # --- Text Embeddings (via OpenRouter API) ---
    text_embedding_model: str = os.environ.get("TEXT_EMBEDDING_MODEL", "openai/text-embedding-3-large")
    text_embedding_dim: int = 3072  # text-embedding-3-large output dimension

    # --- Fused Embedding ---
    @property
    def fused_embedding_dim(self) -> int:
        """Total dimension after concatenating all modality embeddings."""
        if self.mediafm_enabled:
            return self.viclip_embedding_dim + self.audio_embedding_dim + self.text_embedding_dim
        else:
            return self.viclip_embedding_dim + self.text_embedding_dim

    # --- VLM / Video QA (via OpenRouter API) ---
    vlm_model: str = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")

    # --- MediaFM Context Encoder ---
    mediafm_enabled: bool = os.environ.get("MEDIAFM_ENABLED", "true").lower() in ("true", "1", "yes")
    mediafm_hidden_dim: int = int(os.environ.get("MEDIAFM_HIDDEN_DIM", "512"))
    mediafm_num_layers: int = int(os.environ.get("MEDIAFM_NUM_LAYERS", "3"))
    mediafm_num_heads: int = int(os.environ.get("MEDIAFM_NUM_HEADS", "8"))
    mediafm_device: str = os.environ.get("MEDIAFM_DEVICE", "cuda")
    mediafm_checkpoint: Optional[str] = os.environ.get("MEDIAFM_CHECKPOINT", None)

    # --- ZipFormer ASR ---
    zipformer_model_dir: str = os.environ.get(
        "ZIPFORMER_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "models", "zipformer")
    )

    # --- Video Storage ---
    video_data_dir: str = os.environ.get("VIDEO_DATA_DIR", os.environ.get("HOST_PUBLIC_DIR", "/tmp/jockey_videos"))

    # --- Shot Detection ---
    shot_detection_threshold: float = float(os.environ.get("SHOT_DETECTION_THRESHOLD", "27.0"))

    # --- Frame Sampling ---
    max_frames_per_shot: int = int(os.environ.get("MAX_FRAMES_PER_SHOT", "8"))


# Singleton config
config = PipelineConfig()
