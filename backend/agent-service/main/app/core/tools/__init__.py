"""Flat tool registry — every @tool the router can call lives here."""
from .concept_mentions import find_concept_mentions
from .concept_relations import find_concept_relations
from .index_concepts import find_index_concepts
from .image_scene import find_scene_by_image, search_scene_by_image
from .index_search import search_index
from .video_editing import combine_clips
from .video_grounding import ground_video
from .video_highlights import get_highlights
from .video_moderate import moderate_video
from .video_motion import search_motion
from .video_qa import ask_video_local
from .video_search import search_corpus, search_video_local
from .video_sequence import find_sequence
from .video_similar import find_similar
from .video_sounds import find_sounds

TOOLS = [
    search_corpus,
    search_motion,
    search_index,
    find_index_concepts,
    find_concept_mentions,
    find_concept_relations,
    search_video_local,
    ask_video_local,
    combine_clips,
    ground_video,
    find_sequence,
    get_highlights,
    find_similar,
    moderate_video,
    find_sounds,
    find_scene_by_image,
    search_scene_by_image,
]

TOOLS_BY_NAME = {t.name: t for t in TOOLS}
