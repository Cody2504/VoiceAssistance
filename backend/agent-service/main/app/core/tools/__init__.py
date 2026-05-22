"""Flat tool registry — every @tool the router can call lives here."""
from .video_editing import combine_clips
from .video_grounding import ground_video
from .video_highlights import get_highlights
from .video_moderate import moderate_video
from .video_qa import ask_video_local
from .video_search import search_corpus, search_video_local
from .video_similar import find_similar
from .video_sounds import find_sounds

TOOLS = [
    search_corpus,
    search_video_local,
    ask_video_local,
    combine_clips,
    ground_video,
    get_highlights,
    find_similar,
    moderate_video,
    find_sounds,
]

TOOLS_BY_NAME = {t.name: t for t in TOOLS}
