"""Service-to-service HTTP helper (container DNS based)."""
from typing import Any

import httpx

from cm_shared.settings import get_base_settings

_SERVICE_BASE_URLS: dict[str, str] = {}


def _bases() -> dict[str, str]:
    if _SERVICE_BASE_URLS:
        return _SERVICE_BASE_URLS
    s = get_base_settings()
    _SERVICE_BASE_URLS.update(
        {
            "iam": s.iam_base_url,
            "video-service": s.video_service_base_url,
            "agent-service": s.agent_service_base_url,
            "token-usage": s.token_usage_base_url,
        }
    )
    return _SERVICE_BASE_URLS


def _url(service: str, endpoint: str) -> str:
    base = _bases().get(service)
    if not base:
        raise ValueError(f"Unknown service: {service}")
    return f"{base.rstrip('/')}/{endpoint.lstrip('/')}"


async def get_request(service: str, endpoint: str, *, params: dict | None = None, headers: dict | None = None, timeout: float = 30.0) -> Any:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(_url(service, endpoint), params=params, headers=headers)
        r.raise_for_status()
        return r.json()


async def post_request(service: str, endpoint: str, *, json: dict | None = None, headers: dict | None = None, timeout: float = 120.0) -> Any:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(_url(service, endpoint), json=json, headers=headers)
        r.raise_for_status()
        return r.json()
