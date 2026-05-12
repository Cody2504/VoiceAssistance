"""Base Pydantic Settings shared by all services."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Variables every service reads. Subclass per service for extras."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # ---- General ----
    deploy_env: str = "local"
    cors_allow_origins: str = "http://localhost:5173,http://localhost:85"

    # ---- JWT ----
    secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 60
    refresh_token_ttl_days: int = 14

    # ---- Postgres ----
    postgres_user: str = "jockey"
    postgres_password: str = "jockey_dev"
    postgres_db: str = "jockey"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # ---- Redis ----
    redis_host: str = "redis"
    redis_port: int = 6379

    # ---- Service URLs ----
    iam_base_url: str = "http://iam:1100"
    video_service_base_url: str = "http://video-service:1101"
    agent_service_base_url: str = "http://agent-service:1102"
    token_usage_base_url: str = "http://token-usage:1103"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_base_settings() -> BaseServiceSettings:
    return BaseServiceSettings()
