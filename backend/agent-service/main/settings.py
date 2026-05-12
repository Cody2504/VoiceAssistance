from functools import lru_cache

from cm_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "agent-service"
    service_port: int = 1102

    # LLM
    llm_provider: str = "OPENAI"
    openai_api_key: str = ""
    openai_planner_model: str = "gpt-4o"
    openai_worker_model: str = "gpt-4o-mini"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    openai_api_version: str = "2024-08-01-preview"
    azure_planner_deployment: str = "gpt-4o"
    azure_worker_deployment: str = "gpt-4o-mini"

    # Stirrup toggles
    stirrup_search: str = "local"       # local | twelvelabs
    stirrup_textgen: str = "local"
    twelve_labs_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
