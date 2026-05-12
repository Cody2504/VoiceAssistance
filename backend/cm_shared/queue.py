"""Redis Queue (RQ) helpers."""
from functools import lru_cache

from redis import Redis
from rq import Queue

from cm_shared.settings import get_base_settings

VIDEO_INDEX_QUEUE = "video_index"


@lru_cache
def get_redis() -> Redis:
    s = get_base_settings()
    return Redis(host=s.redis_host, port=s.redis_port, decode_responses=False)


@lru_cache
def get_queue(name: str = VIDEO_INDEX_QUEUE) -> Queue:
    return Queue(name=name, connection=get_redis())
