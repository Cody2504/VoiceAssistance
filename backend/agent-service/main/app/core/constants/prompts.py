"""Prompt loading — reads markdown source-of-truth from main/prompts/."""
import os
from functools import lru_cache

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")


def _read(name: str) -> str:
    with open(os.path.join(PROMPTS_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


@lru_cache
def router_prompt() -> str:
    return _read("router.md")


@lru_cache
def reflect_prompt() -> str:
    return _read("reflect.md")
