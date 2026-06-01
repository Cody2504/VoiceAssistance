from functools import lru_cache

from cm_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "billing"
    service_port: int = 1104


@lru_cache
def get_settings() -> Settings:
    return Settings()
