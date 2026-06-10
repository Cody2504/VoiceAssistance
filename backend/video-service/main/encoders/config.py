"""
Configuration for the video-service encoders.
Loads from .env file and environment variables.

API models (via OpenRouter):
  - Text embeddings: openai/text-embedding-3-large
  - Video QA / VLM: qwen/qwen3-vl-8b-instruct

Local models (via HuggingFace):
  - Video encoder: openai/clip-vit-large-patch14 (CLIP-L; frames mean-pooled, NOT temporal ViCLIP)
"""
import os
from dataclasses import dataclass
from typing import Optional

# Module lives at backend/video-service/main/encoders/config.py. Walk up to
# find a .env at the conventional locations: the video-service root, the
# backend root, and the repo root. First match wins.
_config_dir = os.path.dirname(os.path.abspath(__file__))
_env_candidates = [
    os.path.join(_config_dir, "..", "..", ".env"),                   # backend/video-service/.env
    os.path.join(_config_dir, "..", "..", "..", ".env"),             # backend/.env
    os.path.join(_config_dir, "..", "..", "..", "..", ".env"),       # repo root /.env
]
for _env_path in _env_candidates:
    _env_path = os.path.normpath(_env_path)
    if os.path.isfile(_env_path):
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
        break

# HF_TOKEN is the canonical name `huggingface_hub` reads on its own; no alias
# dance needed.


def _auto_device() -> str:
    """Default device: cuda if available, else cpu. Avoids silent random-embedding fallback."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


@dataclass
class PipelineConfig:
    """Central configuration for all open-source pipeline components."""

    # --- OpenRouter API ---
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- HuggingFace ---
    hf_token: str = os.environ.get("HF_TOKEN", "")

    # --- Qdrant ---
    qdrant_host: str = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.environ.get("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = os.environ.get("QDRANT_API_KEY", None)

    # --- CLIP-L visual embeddings (openai/clip-vit-large-patch14, Local HF) ---
    # NB: env vars stay VICLIP_MODEL / VICLIP_DEVICE for deployment-contract compat.
    clipl_model_name: str = os.environ.get("VICLIP_MODEL", "openai/clip-vit-large-patch14")
    clipl_device: str = os.environ.get("VICLIP_DEVICE", _auto_device())
    clipl_embedding_dim: int = 768

    # --- Text Embeddings (via OpenRouter API) ---
    text_embedding_model: str = os.environ.get("TEXT_EMBEDDING_MODEL", "openai/text-embedding-3-large")
    text_embedding_dim: int = 3072  # text-embedding-3-large output dimension

    # --- VLM / Video QA (via OpenRouter API) ---
    vlm_model: str = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")

    # --- ASR ---
    # Backend: "whisperx" (default, faster-whisper CTranslate2) | "zipformer" (sherpa-onnx) | "none"
    asr_backend: str = os.environ.get("ASR_BACKEND", "whisperx")
    # WhisperX/faster-whisper uses short model names ("tiny", "base", "small",
    # "medium", "large-v3"), not HF model ids. Default "small" is CPU-friendly
    # (~500 MB int8, near-realtime on a modern x86 core). Bump to "large-v3"
    # on GPU for accuracy benchmarks.
    whisper_model: str = os.environ.get("WHISPER_MODEL", "small")
    whisper_device: str = os.environ.get("WHISPER_DEVICE", _auto_device())
    whisper_language: str = os.environ.get("WHISPER_LANGUAGE", "en")
    # Compute precision — auto: float16 on CUDA, int8 on CPU. Override for
    # ablation: float32 (slower, higher quality), int8_float16 (CUDA, lower VRAM).
    whisper_compute_type: str = os.environ.get(
        "WHISPER_COMPUTE_TYPE",
        "float16" if _auto_device() == "cuda" else "int8",
    )
    whisper_beam_size: int = int(os.environ.get("WHISPER_BEAM_SIZE", "5"))
    # Silero VAD pre-filter inside faster-whisper. Replaces the legacy RMS
    # silence heuristic — drops silent segments before any decoder work runs.
    whisper_vad: bool = os.environ.get("WHISPER_VAD", "true").lower() in ("true", "1", "yes")
    zipformer_model_dir: str = os.environ.get(
        "ZIPFORMER_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "models", "zipformer")
    )

    # --- Video Storage ---
    video_data_dir: str = os.environ.get("VIDEO_DATA_DIR", os.environ.get("HOST_PUBLIC_DIR", "/tmp/jockey_videos"))

    # --- Shot Detection ---
    shot_detection_threshold: float = float(os.environ.get("SHOT_DETECTION_THRESHOLD", "27.0"))

    # --- Sentence-boundary chunk refinement -----------------------------
    # When True, long shots (>max_shot_s) from PySceneDetect are split at
    # sentence boundaries / long pauses using word-level ASR timestamps,
    # instead of equal-length subdivision. Costs one extra Whisper pass per
    # long shot. Falls back to uniform subdivision when speech is absent.
    sentence_refine_enabled: bool = os.environ.get(
        "SENTENCE_REFINE_ENABLED", "false"
    ).lower() in ("true", "1", "yes")

    # --- VLM per-shot captioning (VideoRAG / NVIDIA VSS pattern) ----------
    # When enabled, the indexer generates a short caption per shot via the
    # same Qwen3-VL endpoint the agent already uses for VQA (via OpenRouter,
    # see ``vlm_model`` above). The caption is joined with the ASR
    # transcript before being passed to the text embedder — the single
    # biggest retrieval-quality win for silent shots (B-roll, animations).
    #
    # CAPTION_ENABLED:
    #   "auto"  (default) — on iff OPENROUTER_API_KEY is configured
    #   "true"  — force on (errors out if no API key)
    #   "false" — force off
    caption_enabled_raw: str = os.environ.get("CAPTION_ENABLED", "auto")
    caption_max_new_tokens: int = int(os.environ.get("CAPTION_MAX_NEW_TOKENS", "80"))

    @property
    def caption_enabled(self) -> bool:
        raw = (self.caption_enabled_raw or "").strip().lower()
        if raw == "auto":
            return bool(self.openrouter_api_key)
        return raw in ("true", "1", "yes")

    # --- Uniform-window override -----------------------------------------
    # When set (e.g. 5.0), the indexer SKIPS PySceneDetect and chops the
    # video into fixed-length windows. Necessary for continuous footage
    # (lectures, ego-centric, single-camera) where PySceneDetect collapses
    # the whole video into one shot — making per-shot transcripts useless.
    # When None (default), uses PySceneDetect.
    uniform_window_sec: Optional[float] = (
        float(os.environ["UNIFORM_WINDOW_SEC"])
        if os.environ.get("UNIFORM_WINDOW_SEC") else None
    )

    # --- Frame Sampling ---
    max_frames_per_shot: int = int(os.environ.get("MAX_FRAMES_PER_SHOT", "8"))

    # --- Thesis-side training (offline; not used by the agent runtime) ---
    # Kept here so the existing training code (qd_detr_train.py, MomentLocalizer)
    # reads its paths from the same singleton. Has no effect on the agent.
    qd_detr_checkpoint: str = os.environ.get("QD_DETR_CHECKPOINT", "")
    features_dir: str = os.environ.get("FEATURES_DIR", "features/charades")


# Singleton config
config = PipelineConfig()
