"""Rewired stirrups — each is a langchain BaseTool that calls video-service over HTTP.

Twelve Labs fallback is selected at import time by env (STIRRUP_SEARCH, STIRRUP_TEXTGEN).
"""
from main.settings import get_settings
from .video_search import build_search_worker
from .video_text_generation import build_textgen_worker
from .video_editing import build_editing_worker
from .video_grounding import build_grounding_worker


def all_workers(worker_llm):
    s = get_settings()
    return [
        build_search_worker(worker_llm, use_local=s.stirrup_search == "local"),
        build_textgen_worker(worker_llm, use_local=s.stirrup_textgen == "local"),
        build_editing_worker(worker_llm),
        build_grounding_worker(worker_llm),
    ]
