"""LLM token/cost metering for chat — accumulate streamed usage, log to token-usage."""
import logging
from typing import Any

from cm_shared.internal import post_request

log = logging.getLogger(__name__)

# USD per 1,000 tokens: (input, output). Approximate; update freely.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
}


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    pin = pout = 0.0
    for key in sorted(PRICING, key=len, reverse=True):  # longest prefix wins (mini before 4o)
        if model.startswith(key):
            pin, pout = PRICING[key]
            break
    return round(input_tokens / 1000 * pin + output_tokens / 1000 * pout, 6)


class UsageAccumulator:
    def __init__(self) -> None:
        self._totals: dict[str, dict[str, int]] = {}

    def add(self, model: str, input_tokens: int, output_tokens: int) -> None:
        t = self._totals.setdefault(model, {"input": 0, "output": 0})
        t["input"] += int(input_tokens or 0)
        t["output"] += int(output_tokens or 0)

    def totals(self) -> dict[str, dict[str, int]]:
        return self._totals


def extract_usage(event: dict) -> tuple[str, int, int] | None:
    """Pull (model, input_tokens, output_tokens) from an on_chat_model_end event."""
    if event.get("event") != "on_chat_model_end":
        return None
    output: Any = (event.get("data") or {}).get("output")
    um = getattr(output, "usage_metadata", None)
    if not um:
        return None
    model = (getattr(output, "response_metadata", None) or {}).get("model_name") or "unknown"
    return (model, int(um.get("input_tokens", 0)), int(um.get("output_tokens", 0)))


async def post_usage(user_id, conversation_id, acc: UsageAccumulator) -> None:
    """Best-effort: one /usage/log row per model. Never raises into the caller."""
    for model, t in acc.totals().items():
        if t["input"] == 0 and t["output"] == 0:
            continue
        payload = {
            "user_id": str(user_id),
            "conversation_id": str(conversation_id) if conversation_id else None,
            "model": model,
            "prompt_tokens": t["input"],
            "completion_tokens": t["output"],
            "cost_usd": cost_for(model, t["input"], t["output"]),
        }
        try:
            await post_request("token-usage", "/api/v1/usage/log", json=payload)
        except Exception:
            log.warning("usage log failed for model %s", model, exc_info=True)
