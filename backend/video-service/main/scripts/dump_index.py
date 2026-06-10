"""One-shot debug dump: for every ready video, list shots stored in Qdrant + asr text + duration.

Usage (inside jockey-video container):
    python -m main.scripts.dump_index > /tmp/index.json
"""
import asyncio
import json
import sys
from uuid import UUID

from sqlalchemy import select

from cm_shared.db import get_sessionmaker
from main.models.video import Video
from main.settings import get_settings


async def _videos_by_status() -> list[dict]:
    async with get_sessionmaker()() as session:
        rows = (await session.execute(select(Video))).scalars().all()
        return [
            {
                "id": str(v.id),
                "user_id": str(v.user_id),
                "original_filename": v.original_filename,
                "duration_s": v.duration_s,
                "shot_count": v.shot_count,
                "status": v.status,
                "error": v.error,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in rows
        ]


def _qdrant_shots_for(video_id: str) -> list[dict]:
    from main.qdrant_util import get_qdrant_client
    from qdrant_client.http import models as qm

    s = get_settings()
    client = get_qdrant_client()
    points, _ = client.scroll(
        collection_name=s.qdrant_collection,
        scroll_filter=qm.Filter(must=[qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id)))]),
        with_payload=True,
        with_vectors=False,
        limit=1000,
    )
    return [
        {
            "shot_idx": p.payload.get("shot_idx"),
            "t_start": p.payload.get("t_start"),
            "t_end": p.payload.get("t_end"),
            "duration_s": (p.payload.get("t_end") or 0) - (p.payload.get("t_start") or 0),
            "asr_text": p.payload.get("asr_text", ""),
        }
        for p in sorted(points, key=lambda x: x.payload.get("shot_idx", 0))
    ]


def _collection_info() -> dict:
    from main.qdrant_util import get_qdrant_client

    s = get_settings()
    client = get_qdrant_client()
    try:
        info = client.get_collection(s.qdrant_collection)
        # Sum up point count via count API for accuracy.
        count = client.count(s.qdrant_collection, exact=True).count
        return {
            "collection_name": s.qdrant_collection,
            "vector_size": info.config.params.vectors.size if hasattr(info.config.params.vectors, "size") else None,
            "distance": str(info.config.params.vectors.distance) if hasattr(info.config.params.vectors, "distance") else None,
            "total_points": count,
        }
    except Exception as exc:
        return {"collection_name": s.qdrant_collection, "error": str(exc)}


async def main():
    videos = await _videos_by_status()
    coll = _collection_info()
    out = {
        "qdrant_collection": coll,
        "videos": [
            {**v, "shots_in_qdrant": _qdrant_shots_for(v["id"]) if v["status"] == "ready" else []}
            for v in videos
        ],
    }
    json.dump(out, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
