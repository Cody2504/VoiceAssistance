"""Video-search stirrup — Qdrant-backed retrieval over an open-source index.

Exposes one tool today:
  - `simple-video-search` — cross-corpus retrieval via VideoSearch.search()

Phase 3 adds:
  - `find-moment`         — intra-video temporal localization via the grounding factory

Both tools share `MarengoSearchInput` / `FindMomentInput` pydantic schemas
to keep the LLM tool-call contract stable. `index_id` is now a Qdrant
collection name (the legacy TwelveLabs index UUID also works, since it's
just a string key).
"""
import asyncio
import json
import os
from enum import Enum
from typing import Dict, List, Optional, Union

from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool

from jockey.prompts import DEFAULT_VIDEO_SEARCH_FILE_PATH
from jockey.stirrups.stirrup import Stirrup


# --------------------------------------------------------------------------- schemas

class GroupByEnum(str, Enum):
    CLIP = "clip"
    VIDEO = "video"


class SearchOptionsEnum(str, Enum):
    """Advisory in single-vector mode; load-bearing once multi-vector storage lands."""
    VISUAL = "visual"
    CONVERSATION = "conversation"


class MarengoSearchInput(BaseModel):
    """LLM-facing schema for the search tool. Kept Marengo-compatible."""
    query: Union[str, dict] = Field(description="Search query to run on a collection of videos.")
    index_id: str = Field(description="Qdrant collection name holding the corpus.")
    top_n: int = Field(description="Get the top N clips or videos as search results.",
                       gt=0, le=10, default=3)
    group_by: GroupByEnum = Field(description="Search for clips or videos.",
                                  default=GroupByEnum.CLIP)
    search_options: List[SearchOptionsEnum] = Field(
        description="Which modalities to consider. Advisory in single-vector mode.",
        default=[SearchOptionsEnum.VISUAL, SearchOptionsEnum.CONVERSATION],
    )
    video_filter: Optional[List[str]] = Field(
        description="Restrict search to these video IDs.", default=None,
    )


# --------------------------------------------------------------------------- search backend (lazy)

_video_search = None


def _get_video_search():
    """Lazily build a process-singleton `VideoSearch`."""
    global _video_search
    if _video_search is not None:
        return _video_search

    from qdrant_client import QdrantClient
    from jockey.open_source.config import config
    from jockey.open_source.search import TextEmbedder, VideoSearch
    from jockey.open_source.viclip_embedder import ViCLIPEmbedder

    qdrant = QdrantClient(
        host=config.qdrant_url,
        port=config.qdrant_port,
        api_key=config.qdrant_api_key,
    )
    viclip = ViCLIPEmbedder(
        model_name_or_path=config.viclip_model_name,
        device=config.viclip_device,
    )
    text_embedder = TextEmbedder(
        api_key=config.openrouter_api_key,
        model=config.text_embedding_model,
        base_url=config.openrouter_base_url,
    )
    _video_search = VideoSearch(
        qdrant_client=qdrant,
        viclip_embedder=viclip,
        text_embedder=text_embedder,
        config=config,
    )
    return _video_search


# --------------------------------------------------------------------------- simple-video-search

@tool("simple-video-search", args_schema=MarengoSearchInput, return_direct=True)
async def simple_video_search(
    query: Union[str, dict],
    index_id: str,
    top_n: int = 3,
    group_by: GroupByEnum = GroupByEnum.CLIP,
    search_options: Optional[List[SearchOptionsEnum]] = None,
    video_filter: Optional[List[str]] = None,
) -> Union[List[Dict], str]:
    """Run a search query against an indexed corpus of videos.
    Query example: "a dog playing with a yellow and white tennis ball"."""
    search = _get_video_search()
    # `query` is occasionally a structured dict from the planner; coerce to str.
    if isinstance(query, dict):
        query = query.get("text") or json.dumps(query)
    result = await search.search(
        query=query,
        index_id=index_id,
        top_n=top_n,
        group_by=group_by.value if isinstance(group_by, Enum) else group_by,
        video_filter=video_filter,
    )
    return result


# --------------------------------------------------------------------------- find-moment (Phase 3)

class FindMomentInput(BaseModel):
    """LLM-facing schema for the moment-localization tool."""
    query: str = Field(description="Natural-language description of the moment to find.")
    video_id: str = Field(description="The video to localize within (already indexed).")
    index_id: str = Field(description="Qdrant collection the video belongs to.")


_grounder = None


def _get_grounder():
    global _grounder
    if _grounder is not None:
        return _grounder
    from jockey.open_source.config import config
    from jockey.open_source.grounding_factory import build_grounder
    _grounder = build_grounder(config)
    return _grounder


@tool("find-moment", args_schema=FindMomentInput, return_direct=True)
async def find_moment(query: str, video_id: str, index_id: str) -> str:
    """Find the start/end timestamps of a specific moment INSIDE a known video.

    Use when the user already chose a video and wants to locate a specific
    segment by description. For cross-corpus retrieval ("find any video with
    X"), use `simple-video-search` instead.
    """
    search = _get_video_search()
    meta = search.get_video_metadata(index_id=index_id, video_id=video_id)
    video_path = meta.get("video_path") if isinstance(meta, dict) else None
    if not video_path or not os.path.isfile(video_path):
        return json.dumps({
            "error": f"Could not resolve a local video_path for video_id={video_id} "
                     f"in index_id={index_id}. Metadata returned: {meta!r}",
        })

    grounder = _get_grounder()
    # `localize` may be sync or async depending on backend; handle both.
    result = grounder.localize(query, video_path)
    if asyncio.iscoroutine(result):
        result = await result

    return json.dumps({
        "video_id": result.video_id,
        "query": result.query,
        "start": result.start_sec,
        "end": result.end_sec,
        "confidence": result.confidence,
        "duration": result.duration,
        "video_url": video_path,
    })


# --------------------------------------------------------------------------- worker config

video_search_worker_config = {
    "tools": [simple_video_search, find_moment],
    "worker_prompt_file_path": DEFAULT_VIDEO_SEARCH_FILE_PATH,
    "worker_name": "video-search",
}
VideoSearchWorker = Stirrup(**video_search_worker_config)
