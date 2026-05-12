"""LLM provider switch — ported from jockey/app.py."""
from typing import Union

from langchain_openai import AzureChatOpenAI, ChatOpenAI

from main.settings import get_settings


def build_llms() -> tuple[Union[ChatOpenAI, AzureChatOpenAI], Union[ChatOpenAI, AzureChatOpenAI], Union[ChatOpenAI, AzureChatOpenAI]]:
    """Returns (planner_llm, supervisor_llm, worker_llm). Both routes stream tokens for SSE."""
    s = get_settings()

    if s.llm_provider.upper() == "AZURE":
        planner = AzureChatOpenAI(deployment_name=s.azure_planner_deployment, streaming=True, temperature=0, tags=["planner"])
        supervisor = AzureChatOpenAI(deployment_name=s.azure_planner_deployment, streaming=True, temperature=0, tags=["supervisor"])
        worker = AzureChatOpenAI(deployment_name=s.azure_worker_deployment, streaming=True, temperature=0, tags=["worker"])
    else:
        planner = ChatOpenAI(model=s.openai_planner_model, streaming=True, temperature=0, tags=["planner"], api_key=s.openai_api_key)
        supervisor = ChatOpenAI(model=s.openai_planner_model, streaming=True, temperature=0, tags=["supervisor"], api_key=s.openai_api_key)
        worker = ChatOpenAI(model=s.openai_worker_model, streaming=True, temperature=0, tags=["worker"], api_key=s.openai_api_key)

    return planner, supervisor, worker
