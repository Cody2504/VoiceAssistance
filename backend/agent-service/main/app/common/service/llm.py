"""LLM provider factory — replaces main/agent/app.py::build_llms()."""
from typing import Literal, Union

from langchain_openai import AzureChatOpenAI, ChatOpenAI

from main.app.common.conf.app_conf import get_settings

Role = Literal["router", "reflect"]


def get_llm_client(role: Role) -> Union[ChatOpenAI, AzureChatOpenAI]:
    """Return a streaming, temperature-0 LLM tagged for SSE event filtering."""
    s = get_settings()

    if s.llm_provider.upper() == "AZURE":
        deployment = s.azure_planner_deployment if role == "router" else s.azure_worker_deployment
        return AzureChatOpenAI(
            deployment_name=deployment,
            streaming=True,
            temperature=0,
            tags=[role],
            stream_usage=True,
        )

    model = s.openai_planner_model if role == "router" else s.openai_worker_model
    return ChatOpenAI(
        model=model,
        streaming=True,
        temperature=0,
        tags=[role],
        api_key=s.openai_api_key,
        stream_usage=True,
    )
