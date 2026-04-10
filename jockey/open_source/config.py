"""
Configuration for the open-source Jockey pipeline.
Environment variables and model paths.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineConfig:
    """Central configuration for all open-source pipeline components."""

    # --- Qdrant ---
    qdrant_url: str = os.environ.get("QDRANT_URL", "localhost")
    qdrant_port: int = int(os.environ.get("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = os.environ.get("QDRANT_API_KEY", None)

    # --- ViCLIP (Video Embeddings) ---
    viclip_model_name: str = os.environ.get("VICLIP_MODEL", "OpenGVLab/ViCLIP-L-14")
    viclip_device: str = os.environ.get("VICLIP_DEVICE", "cuda")
    viclip_embedding_dim: int = 768

    # --- OpenAI Text Embeddings ---
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    text_embedding_model: str = os.environ.get("TEXT_EMBEDDING_MODEL", "text-embedding-3-large")
    text_embedding_dim: int = 3072  # text-embedding-3-large output dimension

    # --- Fused Embedding ---
    @property
    def fused_embedding_dim(self) -> int:
        return self.viclip_embedding_dim + self.text_embedding_dim

    # --- ZipFormer ASR ---
    zipformer_model_dir: str = os.environ.get(
        "ZIPFORMER_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "models", "zipformer")
    )

    # --- Qwen2-VL (Video Q&A) ---
    qwen2vl_model_name: str = os.environ.get("QWEN2VL_MODEL", "Qwen/Qwen2-VL-7B-Instruct")
    qwen2vl_device: str = os.environ.get("QWEN2VL_DEVICE", "cuda")

    # --- Video Storage ---
    video_data_dir: str = os.environ.get("VIDEO_DATA_DIR", os.environ.get("HOST_PUBLIC_DIR", "/tmp/jockey_videos"))

    # --- Shot Detection ---
    shot_detection_threshold: float = float(os.environ.get("SHOT_DETECTION_THRESHOLD", "27.0"))

    # --- Frame Sampling ---
    max_frames_per_shot: int = int(os.environ.get("MAX_FRAMES_PER_SHOT", "8"))


# Singleton config
config = PipelineConfig()
