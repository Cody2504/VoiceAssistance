"""Video text-generation stirrup — runs gist/summarize/freeform via local VideoQA.

Replaces the TwelveLabs Pegasus REST endpoints (gist/, summarize/, generate/)
with the local `jockey.open_source.video_qa.VideoQA` class, which calls
OpenRouter Qwen3-VL-8B with sampled frames. LLM tool-call contract
(input pydantic schemas) is unchanged so prompts continue to work.
"""
import asyncio
import json
import os
from enum import Enum
from typing import List, Optional, Union

from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool

from jockey.prompts import DEFAULT_VIDEO_TEXT_GENERATION_FILE_PATH
from jockey.stirrups.stirrup import Stirrup


# --------------------------------------------------------------------------- schemas (Pegasus-shape, unchanged)

class GistEndpointsEnum(str, Enum):
    TOPIC = "topic"
    HASHTAG = "hashtag"
    TITLE = "title"


class SummarizeEndpointEnum(str, Enum):
    SUMMARY = "summary"
    HIGHLIGHT = "highlight"
    CHAPTER = "chapter"


class PegasusGistInput(BaseModel):
    video_id: str = Field(description="The ID of the video to generate text from.")
    index_id: str = Field(description="Index ID which contains a collection of videos.")
    endpoint_options: List[GistEndpointsEnum] = Field(description="Determines what outputs to generate.")


class PegasusSummarizeInput(BaseModel):
    video_id: str = Field(description="The ID of the video to generate text from.")
    index_id: str = Field(description="Index ID which contains a collection of videos.")
    endpoint_option: SummarizeEndpointEnum = Field(description="Determines what output to generate.")
    prompt: Optional[str] = Field(
        description="Additional generation instructions.", max_length=300, default=None,
    )


class PegasusFreeformInput(BaseModel):
    video_id: str = Field(description="The ID of the video to generate text from.")
    index_id: str = Field(description="Index ID which contains a collection of videos.")
    prompt: str = Field(description="Instructions on what text output to generate.",
                        max_length=300)


# --------------------------------------------------------------------------- VideoQA singleton

_video_qa = None
_video_search_for_meta = None  # for video_id → video_path resolution


def _get_video_qa():
    global _video_qa
    if _video_qa is not None:
        return _video_qa
    from jockey.open_source.config import config
    from jockey.open_source.video_qa import VideoQA
    _video_qa = VideoQA.from_config(config)
    return _video_qa


def _resolve_video_path(video_id: str, index_id: str) -> Optional[str]:
    """Look up the local file path for a (video_id, index_id) via Qdrant payload."""
    global _video_search_for_meta
    if _video_search_for_meta is None:
        # Reuse the same lazy singleton from video_search to avoid a second Qdrant client.
        from jockey.stirrups.video_search import _get_video_search
        _video_search_for_meta = _get_video_search()
    meta = _video_search_for_meta.get_video_metadata(index_id=index_id, video_id=video_id)
    if not isinstance(meta, dict):
        return None
    path = meta.get("video_path")
    return path if path and os.path.isfile(path) else None


def _meta_error(video_id: str, index_id: str) -> str:
    return json.dumps({
        "error": f"Could not resolve a local video_path for video_id={video_id} "
                 f"in index_id={index_id}. Make sure the video has been indexed.",
    })


# --------------------------------------------------------------------------- tools

@tool("gist-text-generation", args_schema=PegasusGistInput)
async def gist_text_generation(
    video_id: str, index_id: str, endpoint_options: List[GistEndpointsEnum],
) -> str:
    """Generate gist output (title, topic, hashtag) for a single video."""
    video_path = _resolve_video_path(video_id, index_id)
    if not video_path:
        return _meta_error(video_id, index_id)

    qa = _get_video_qa()
    options = [
        opt.value if isinstance(opt, Enum) else opt
        for opt in endpoint_options
    ]
    result_str = await qa.gist(video_path=video_path, options=options)
    # VideoQA.gist already returns JSON; merge metadata for symmetry with TL response.
    try:
        parsed = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        parsed = {"text": result_str}
    parsed["video_url"] = video_path
    parsed["video_id"] = video_id
    parsed["index_id"] = index_id
    return json.dumps(parsed)


@tool("summarize-text-generation", args_schema=PegasusSummarizeInput)
async def summarize_text_generation(
    video_id: str,
    index_id: str,
    endpoint_option: SummarizeEndpointEnum,
    prompt: Optional[str] = None,
) -> str:
    """Generate summary, highlight, or chapter output for a single video."""
    video_path = _resolve_video_path(video_id, index_id)
    if not video_path:
        return _meta_error(video_id, index_id)

    qa = _get_video_qa()
    mode = endpoint_option.value if isinstance(endpoint_option, Enum) else endpoint_option
    result_str = await qa.summarize(video_path=video_path, mode=mode, prompt=prompt)
    try:
        parsed = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        parsed = {"text": result_str}
    parsed.setdefault("type", mode)
    parsed["video_url"] = video_path
    parsed["video_id"] = video_id
    parsed["index_id"] = index_id
    return json.dumps(parsed)


@tool("freeform-text-generation", args_schema=PegasusFreeformInput)
async def free_text_generation(video_id: str, index_id: str, prompt: str) -> str:
    """Generate any text output for a single video, given an arbitrary prompt."""
    video_path = _resolve_video_path(video_id, index_id)
    if not video_path:
        return _meta_error(video_id, index_id)

    qa = _get_video_qa()
    result_str = await qa.freeform(video_path=video_path, prompt=prompt)
    try:
        parsed = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        parsed = {"text": result_str}
    parsed["video_url"] = video_path
    parsed["video_id"] = video_id
    parsed["index_id"] = index_id
    return json.dumps(parsed)


# --------------------------------------------------------------------------- worker config

video_text_generation_worker_config = {
    "tools": [gist_text_generation, summarize_text_generation, free_text_generation],
    "worker_prompt_file_path": DEFAULT_VIDEO_TEXT_GENERATION_FILE_PATH,
    "worker_name": "video-text-generation",
}
VideoTextGenerationWorker = Stirrup(**video_text_generation_worker_config)
