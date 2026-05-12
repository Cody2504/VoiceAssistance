from functools import lru_cache

from cm_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "video-service"
    service_port: int = 1101

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "jockey_shots"

    # MinIO / S3
    minio_endpoint: str = "http://minio:9000"
    minio_root_user: str = "jockey"
    minio_root_password: str = "jockey_dev_secret"
    minio_bucket_videos: str = "videos"
    minio_bucket_edits: str = "edits"
    minio_bucket_thumbs: str = "thumbs"

    # Grounding head
    grounding_checkpoint: str = "/models/grounding/best.pt"
    grounding_device: str = "cpu"           # "cuda" if GPU available
    grounding_hidden_dim: int = 512
    grounding_num_layers: int = 4
    grounding_num_heads: int = 8

    # OpenRouter (used by video_qa + text-embedding caller)
    openrouter_api_key: str = ""
    openai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
