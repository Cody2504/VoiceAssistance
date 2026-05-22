"""Agent-service settings — ported from main/settings.py.

Drops STIRRUP_* toggles and TWELVE_LABS_API_KEY (TwelveLabs path is dead since the
upstream migration). Adds router/reflect role names instead of planner/worker.
"""
from functools import lru_cache

from cm_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "agent-service"
    service_port: int = 1102

    # LLM provider
    llm_provider: str = "OPENAI"  # OPENAI | AZURE

    # OpenAI — env var names kept from the prior layout so existing docker-compose vars still bind.
    # The new graph maps role -> model as: router -> *_planner_model, reflect -> *_worker_model.
    openai_api_key: str = ""
    openai_planner_model: str = "gpt-4o"   # used by router role
    openai_worker_model: str = "gpt-4o-mini"  # used by reflect role

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    openai_api_version: str = "2024-08-01-preview"
    azure_planner_deployment: str = "gpt-4o"   # router
    azure_worker_deployment: str = "gpt-4o-mini"  # reflect

    # Router loop bound — hard cap before forcing reflect.
    router_max_steps: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
