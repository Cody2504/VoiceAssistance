from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from cm_shared.queue import VIDEO_INDEX_QUEUE, get_queue
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import TokenPayload, require_user
from cm_shared.db import get_session
from cm_shared.response import success_response
from main.models.index import Index, IndexVideo
from main.models.kg import Entity, EntityMention, EntityRelation
from main.models.video import Video
from main.settings import get_settings

router = APIRouter(prefix="/api/v1/indexes", tags=["indexes"])


class IndexCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    description: str | None = None
    language: str = Field(default="auto", max_length=16)


class IndexOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str | None
    description: str | None
    language: str
    created_at: datetime
    video_count: int
    total_duration_s: float | None = None


class IndexVideoAdd(BaseModel):
    video_id: UUID
    position: int | None = None


class IndexVideoOut(BaseModel):
    video_id: UUID
    position: int
    original_filename: str
    duration_s: float | None
    status: str


class IndexScopedSearch(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    video_ids: list[UUID] = Field(default_factory=list)
    top_n: int = Field(default=10, ge=1, le=50)
    group_by: Literal["clip", "video"] = "clip"


class ConceptSearchQuery(BaseModel):
    """Semantic search over the index's knowledge-graph entities."""
    query: str = Field(min_length=1, max_length=512)
    top_k: int = Field(default=10, ge=1, le=50)
    entity_types: list[str] | None = Field(
        default=None,
        description="Optional filter — only return entities of these types. e.g. ['concept','method'].",
    )


class ConceptOut(BaseModel):
    entity_id: UUID
    canonical_name: str
    entity_type: str | None
    description: str | None
    score: float
    mention_count: int
    video_count: int


class ConceptMentionOut(BaseModel):
    video_id: UUID
    video_title: str
    video_position: int
    segment_idx: int
    t_start: float | None
    t_end: float | None
    transcript: str
    caption: str
    weight: float


class RelatedConceptOut(BaseModel):
    entity_id: UUID
    canonical_name: str
    entity_type: str | None
    description: str | None
    relation: str
    relation_description: str | None
    weight: float
    direction: Literal["outgoing", "incoming"]


class GraphNodeOut(BaseModel):
    id: UUID
    label: str
    type: str | None
    description: str | None
    mention_count: int


class GraphEdgeOut(BaseModel):
    source: UUID
    target: UUID
    relation: str
    description: str | None
    weight: float


async def _load_owned(session: AsyncSession, index_id: UUID, user_id: UUID) -> Index:
    row = await session.get(Index, index_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(404, "Index not found")
    return row


async def _resolve_video_ids(
    session: AsyncSession, index_id: UUID, requested: list[UUID]
) -> list[UUID]:
    """When the caller provides an empty list, expand to all videos in the index.
    Otherwise, enforce that every requested id belongs to the index."""
    if requested:
        rows = (
            await session.execute(
                select(IndexVideo.video_id).where(
                    IndexVideo.index_id == index_id,
                    IndexVideo.video_id.in_(requested),
                )
            )
        ).scalars().all()
        if len(rows) != len(set(requested)):
            raise HTTPException(400, "Some video_ids are not in this index")
        return list(rows)

    rows = (
        await session.execute(
            select(IndexVideo.video_id)
            .where(IndexVideo.index_id == index_id)
            .order_by(IndexVideo.position.asc())
        )
    ).scalars().all()
    return list(rows)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_index(
    body: IndexCreate,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    idx = Index(
        id=uuid4(),
        user_id=user_id,
        title=body.title,
        description=body.description,
        language=body.language,
    )
    session.add(idx)
    await session.commit()
    await session.refresh(idx)
    return success_response(
        IndexOut(
            id=idx.id,
            user_id=idx.user_id,
            title=idx.title,
            description=idx.description,
            language=idx.language,
            created_at=idx.created_at,
            video_count=0,
            total_duration_s=0.0,
        ).model_dump(mode="json")
    )


@router.get("")
async def list_indexes(
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    aggregate = (
        select(
            Index,
            func.count(IndexVideo.video_id).label("video_count"),
            func.coalesce(func.sum(Video.duration_s), 0.0).label("total_duration_s"),
        )
        .select_from(Index)
        .outerjoin(IndexVideo, IndexVideo.index_id == Index.id)
        .outerjoin(Video, Video.id == IndexVideo.video_id)
        .where(Index.user_id == user_id)
        .group_by(Index.id)
        .order_by(Index.created_at.desc())
    )
    rows = (await session.execute(aggregate)).all()
    items = [
        IndexOut(
            id=r.Index.id,
            user_id=r.Index.user_id,
            title=r.Index.title,
            description=r.Index.description,
            language=r.Index.language,
            created_at=r.Index.created_at,
            video_count=int(r.video_count or 0),
            total_duration_s=float(r.total_duration_s or 0.0),
        ).model_dump(mode="json")
        for r in rows
    ]
    return success_response(items)


@router.get("/{index_id}")
async def get_index(
    index_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    idx = await _load_owned(session, index_id, user_id)
    agg = (
        await session.execute(
            select(
                func.count(IndexVideo.video_id),
                func.coalesce(func.sum(Video.duration_s), 0.0),
            )
            .select_from(IndexVideo)
            .outerjoin(Video, Video.id == IndexVideo.video_id)
            .where(IndexVideo.index_id == index_id)
        )
    ).one()
    return success_response(
        IndexOut(
            id=idx.id,
            user_id=idx.user_id,
            title=idx.title,
            description=idx.description,
            language=idx.language,
            created_at=idx.created_at,
            video_count=int(agg[0] or 0),
            total_duration_s=float(agg[1] or 0.0),
        ).model_dump(mode="json")
    )


@router.delete("/{index_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_index(
    index_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    idx = await _load_owned(session, index_id, user_id)
    await session.delete(idx)
    await session.commit()
    return None


@router.post("/{index_id}/videos", status_code=status.HTTP_201_CREATED)
async def add_video_to_index(
    index_id: UUID,
    body: IndexVideoAdd,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)

    video = await session.get(Video, body.video_id)
    if video is None or video.user_id != user_id:
        raise HTTPException(404, "Video not found")

    # 1 video = 1 index: reject if the video already belongs to ANY index.
    already = (
        await session.execute(
            select(IndexVideo.index_id).where(IndexVideo.video_id == body.video_id).limit(1)
        )
    ).first()
    if already is not None:
        raise HTTPException(409, "Video already belongs to an index")

    if body.position is None:
        next_pos = (
            await session.execute(
                select(func.coalesce(func.max(IndexVideo.position), -1) + 1).where(
                    IndexVideo.index_id == index_id
                )
            )
        ).scalar_one()
        pos = int(next_pos)
    else:
        pos = body.position

    link = IndexVideo(index_id=index_id, video_id=body.video_id, position=pos)
    session.add(link)

    # Add-to-index is the processing trigger. A still-stored video gets the full
    # IV2/TransNet/SG-DETR/KG pipeline now; the worker self-discovers this (single)
    # index membership via IndexVideo (ingest._run_kg_for_video_indexes) and builds
    # KG for it. An already-processed video would only re-associate — but the 1:1
    # guard above means that path can't be reached.
    if video.status == "stored":
        video.status = "queued"
        session.add(video)

    await session.commit()

    if video.status == "queued":
        get_queue(VIDEO_INDEX_QUEUE).enqueue(
            "main.workers.queue_worker.index_video",
            str(body.video_id),
            job_timeout=3600,
        )

    return success_response(
        IndexVideoOut(
            video_id=body.video_id,
            position=pos,
            original_filename=video.original_filename,
            duration_s=video.duration_s,
            status=video.status,
        ).model_dump(mode="json")
    )


@router.get("/{index_id}/videos")
async def list_index_videos(
    index_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)

    rows = (
        await session.execute(
            select(IndexVideo, Video)
            .join(Video, Video.id == IndexVideo.video_id)
            .where(IndexVideo.index_id == index_id)
            .order_by(IndexVideo.position.asc())
        )
    ).all()
    items = [
        IndexVideoOut(
            video_id=link.video_id,
            position=link.position,
            original_filename=video.original_filename,
            duration_s=video.duration_s,
            status=video.status,
        ).model_dump(mode="json")
        for link, video in rows
    ]
    return success_response(items)


@router.delete("/{index_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_video_from_index(
    index_id: UUID,
    video_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)
    await session.execute(
        sa_delete(IndexVideo).where(
            IndexVideo.index_id == index_id, IndexVideo.video_id == video_id
        )
    )
    await session.commit()
    return None


@router.post("/{index_id}/search")
async def search_within_index(
    index_id: UUID,
    body: IndexScopedSearch,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Scoped TEXT-similarity retrieval over an Index.

    Searches `jockey_segments_text` (text-embedding-3-large of caption +
    transcript per 30-second segment), filtered to the resolved set of videos
    in the index. For talking-head / lecture content this is a stronger
    ranking signal than the CLIP-L visual similarity used by the global
    /api/v1/videos/search endpoint.

    **Single-purpose: this endpoint does NOT consult the knowledge graph.**
    Entity-graph retrieval, mention lookup, and relation walks live on their
    own endpoints (/concepts/search, /entities/{id}/mentions,
    /entities/{id}/related) and are exposed to the agent as separate tools.
    Letting the router pick the right tool for the question beats fusing
    everything into one ranked list — see CROSS_VIDEO_LECTURE_PLAN.md §4.
    """
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)

    resolved = await _resolve_video_ids(session, index_id, body.video_ids)
    if not resolved:
        return success_response({"query": body.query, "shots": []})

    video_meta_rows = (
        await session.execute(
            select(Video.id, Video.original_filename, Video.duration_s).where(
                Video.id.in_(resolved), Video.status == "ready"
            )
        )
    ).all()
    video_meta = {
        str(r.id): {"original_filename": r.original_filename, "duration_s": r.duration_s}
        for r in video_meta_rows
    }
    if not video_meta:
        return success_response({"query": body.query, "shots": []})

    from main.encoders.search import TextEmbedder
    from main.qdrant_util import get_qdrant_client
    from qdrant_client.http import models as qm

    s = get_settings()
    embedder = TextEmbedder(api_key=s.openrouter_api_key)
    qvec = embedder.encode(body.query).tolist()

    client = get_qdrant_client(timeout=30)
    video_id_filter = qm.Filter(
        must=[qm.FieldCondition(key="video_id", match=qm.MatchAny(any=list(video_meta.keys())))]
    )
    fetch_limit = body.top_n * 5 if body.group_by == "video" else body.top_n

    try:
        hits = client.search(
            collection_name="jockey_segments_text",
            query_vector=qvec,
            query_filter=video_id_filter,
            limit=fetch_limit,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "index_search:jockey_segments_text query failed (%s) — returning empty",
            exc,
        )
        hits = []

    shots: list[dict] = []
    seen_videos: set[str] = set()
    for h in hits:
        vid = h.payload["video_id"]
        if body.group_by == "video":
            if vid in seen_videos:
                continue
            seen_videos.add(vid)
        meta = video_meta.get(vid, {})
        shots.append(
            {
                "video_id": vid,
                "original_filename": meta.get("original_filename", ""),
                "video_duration_s": meta.get("duration_s"),
                "idx": h.payload.get("segment_idx", h.payload.get("shot_idx", 0)),
                "t_start": h.payload["t_start"],
                "t_end": h.payload["t_end"],
                "transcript": h.payload.get("transcript") or h.payload.get("asr_text", ""),
                "caption": h.payload.get("caption", ""),
                "ocr_text": h.payload.get("ocr_text", ""),
                "audio_tags": h.payload.get("audio_tags", []),
                "score": float(h.score),
            }
        )
        if len(shots) >= body.top_n:
            break
    return success_response(
        {
            "query": body.query,
            "index_id": str(index_id),
            "group_by": body.group_by,
            "shots": shots,
        }
    )


# Knowledge-graph endpoints (Phase 2a)
# Single-purpose primitives — each one is a clean handle the LangGraph agent
# can call via its own tool. See CROSS_VIDEO_LECTURE_PLAN.md §4 for the design
# rationale (separate tools beat fused scores).


async def _entity_in_index(
    session: AsyncSession, index_id: UUID, entity_id: UUID
) -> Entity:
    row = await session.get(Entity, entity_id)
    if row is None or row.index_id != index_id:
        raise HTTPException(404, "Entity not found in this index")
    return row


@router.post("/{index_id}/concepts/search")
async def search_concepts(
    index_id: UUID,
    body: ConceptSearchQuery,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Semantic search across the index's KG entities.

    Returns top-k entities matching `query`, each with how many segments and
    distinct videos mention it. Used by the agent's `find_index_concepts`
    tool. Vector lookup runs against the `jockey_entities` Qdrant collection;
    metadata (mention_count, video_count) is filled in from Postgres.
    """
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)

    from main.encoders.search import TextEmbedder
    from main.qdrant_util import get_qdrant_client
    from qdrant_client.http import models as qm

    s = get_settings()
    client = get_qdrant_client(timeout=30)
    try:
        existing = {c.name for c in client.get_collections().collections}
    except Exception:
        existing = set()
    if s.kg_qdrant_collection not in existing:
        return success_response(
            {
                "query": body.query,
                "index_id": str(index_id),
                "concepts": [],
                "kg_available": False,
            }
        )

    embedder = TextEmbedder(api_key=s.openrouter_api_key)
    qvec = embedder.encode(body.query).tolist()
    must = [qm.FieldCondition(key="index_id", match=qm.MatchValue(value=str(index_id)))]
    must_not = []
    if body.entity_types:
        must.append(
            qm.FieldCondition(
                key="entity_type",
                match=qm.MatchAny(any=[t.lower() for t in body.entity_types]),
            )
        )
    else:
        # No explicit type filter → this is a "main concepts/topics" query. Exclude
        # clearly-non-topic entity types so the list isn't polluted by characters,
        # orgs and pedagogy props (e.g. "CS Student"=person, "3Blue1Brown"=organization,
        # "Visual Aids"=tool). NB: keep `object` — core nouns like "vector"/"matrix"
        # are typed object by the extractor and ARE central concepts.
        must_not.append(
            qm.FieldCondition(
                key="entity_type",
                match=qm.MatchAny(any=["person", "organization", "location", "event", "tool"]),
            )
        )
    try:
        hits = client.search(
            collection_name=s.kg_qdrant_collection,
            query_vector=qvec,
            query_filter=qm.Filter(must=must, must_not=must_not or None),
            limit=body.top_k,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("search_concepts:qdrant failed: %s", exc)
        hits = []

    if not hits:
        return success_response(
            {
                "query": body.query,
                "index_id": str(index_id),
                "concepts": [],
                "kg_available": True,
            }
        )

    entity_ids = [UUID(h.payload["entity_id"]) for h in hits if h.payload]
    score_by_id = {UUID(h.payload["entity_id"]): float(h.score) for h in hits if h.payload}

    # Pull entity rows + aggregate mention/video counts in one go.
    entities = (
        await session.execute(select(Entity).where(Entity.id.in_(entity_ids)))
    ).scalars().all()
    counts_rows = (
        await session.execute(
            select(
                EntityMention.entity_id,
                func.count(EntityMention.segment_idx).label("mention_count"),
                func.count(func.distinct(EntityMention.video_id)).label("video_count"),
            )
            .where(EntityMention.entity_id.in_(entity_ids))
            .group_by(EntityMention.entity_id)
        )
    ).all()
    counts_by_id = {
        r.entity_id: {"mention_count": int(r.mention_count), "video_count": int(r.video_count)}
        for r in counts_rows
    }

    concepts: list[dict] = []
    for e in entities:
        c = counts_by_id.get(e.id, {"mention_count": 0, "video_count": 0})
        concepts.append(
            ConceptOut(
                entity_id=e.id,
                canonical_name=e.canonical_name,
                entity_type=e.entity_type,
                description=e.description,
                score=score_by_id.get(e.id, 0.0),
                mention_count=c["mention_count"],
                video_count=c["video_count"],
            ).model_dump(mode="json")
        )
    concepts.sort(key=lambda r: r["score"], reverse=True)

    return success_response(
        {
            "query": body.query,
            "index_id": str(index_id),
            "concepts": concepts,
            "kg_available": True,
        }
    )


@router.get("/{index_id}/entities/{entity_id}/mentions")
async def list_entity_mentions(
    index_id: UUID,
    entity_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    video_ids: str | None = None,
    limit: int = 50,
):
    """Every segment where `entity_id` was mentioned, ordered by the video's
    position within the index, then by segment index within the video.

    The optional `video_ids` query string narrows the scope (comma-separated
    UUIDs) — handy when the agent only wants mentions in earlier-positioned
    videos for a comparative answer ("how was X explained in the previous
    lecture"). `limit` caps the response size.
    """
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)
    await _entity_in_index(session, index_id, entity_id)

    scope_ids: list[UUID] | None = None
    if video_ids:
        try:
            scope_ids = [UUID(s.strip()) for s in video_ids.split(",") if s.strip()]
        except ValueError:
            raise HTTPException(400, "video_ids must be a comma-separated list of UUIDs")

    q = (
        select(
            EntityMention,
            Video.original_filename,
            IndexVideo.position,
        )
        .join(Video, Video.id == EntityMention.video_id)
        .join(
            IndexVideo,
            (IndexVideo.video_id == EntityMention.video_id)
            & (IndexVideo.index_id == index_id),
        )
        .where(EntityMention.entity_id == entity_id)
        .order_by(IndexVideo.position.asc(), EntityMention.segment_idx.asc())
        .limit(max(1, min(limit, 500)))
    )
    if scope_ids:
        q = q.where(EntityMention.video_id.in_(scope_ids))

    rows = (await session.execute(q)).all()

    # Pull per-segment transcript+caption from Qdrant payloads for the
    # segments we actually return. Single batched retrieve call.
    from main.qdrant_util import get_qdrant_client
    s = get_settings()
    client = get_qdrant_client(timeout=30)
    point_ids = [str(r.EntityMention.qdrant_point_id) for r in rows]
    payload_by_id: dict[str, dict] = {}
    if point_ids:
        try:
            retrieved = client.retrieve(
                collection_name="jockey_segments_text",
                ids=point_ids,
                with_payload=True,
                with_vectors=False,
            )
            payload_by_id = {str(p.id): (p.payload or {}) for p in retrieved}
        except Exception:
            payload_by_id = {}

    mentions: list[dict] = []
    for r in rows:
        m = r.EntityMention
        pl = payload_by_id.get(str(m.qdrant_point_id), {})
        mentions.append(
            ConceptMentionOut(
                video_id=m.video_id,
                video_title=r.original_filename or "",
                video_position=int(r.position),
                segment_idx=m.segment_idx,
                t_start=m.t_start,
                t_end=m.t_end,
                transcript=pl.get("transcript") or pl.get("asr_text", "") or "",
                caption=pl.get("caption", "") or "",
                weight=float(m.weight),
            ).model_dump(mode="json")
        )

    return success_response(
        {
            "index_id": str(index_id),
            "entity_id": str(entity_id),
            "mentions": mentions,
        }
    )


@router.get("/{index_id}/entities/{entity_id}/related")
async def list_entity_relations(
    index_id: UUID,
    entity_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    direction: Literal["both", "outgoing", "incoming"] = "both",
    top_k: int = 20,
):
    """Entities connected to `entity_id` via `entity_relations` rows.

    `direction='outgoing'` → relations where this entity is the source.
    `direction='incoming'` → relations where this entity is the target.
    Default `'both'` returns the union and tags each result with its
    direction. Sorted by relation weight desc.
    """
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)
    await _entity_in_index(session, index_id, entity_id)

    results: list[RelatedConceptOut] = []
    if direction in ("outgoing", "both"):
        rows = (
            await session.execute(
                select(EntityRelation, Entity)
                .join(Entity, Entity.id == EntityRelation.dst_entity_id)
                .where(
                    EntityRelation.index_id == index_id,
                    EntityRelation.src_entity_id == entity_id,
                )
                .order_by(EntityRelation.weight.desc())
                .limit(max(1, min(top_k, 100)))
            )
        ).all()
        for rel, other in rows:
            results.append(
                RelatedConceptOut(
                    entity_id=other.id,
                    canonical_name=other.canonical_name,
                    entity_type=other.entity_type,
                    description=other.description,
                    relation=rel.relation,
                    relation_description=rel.description,
                    weight=float(rel.weight),
                    direction="outgoing",
                )
            )

    if direction in ("incoming", "both"):
        rows = (
            await session.execute(
                select(EntityRelation, Entity)
                .join(Entity, Entity.id == EntityRelation.src_entity_id)
                .where(
                    EntityRelation.index_id == index_id,
                    EntityRelation.dst_entity_id == entity_id,
                )
                .order_by(EntityRelation.weight.desc())
                .limit(max(1, min(top_k, 100)))
            )
        ).all()
        for rel, other in rows:
            results.append(
                RelatedConceptOut(
                    entity_id=other.id,
                    canonical_name=other.canonical_name,
                    entity_type=other.entity_type,
                    description=other.description,
                    relation=rel.relation,
                    relation_description=rel.description,
                    weight=float(rel.weight),
                    direction="incoming",
                )
            )

    results.sort(key=lambda r: r.weight, reverse=True)
    if len(results) > top_k:
        results = results[:top_k]

    return success_response(
        {
            "index_id": str(index_id),
            "entity_id": str(entity_id),
            "related": [r.model_dump(mode="json") for r in results],
        }
    )


def build_graph_payload(entities, relations, mention_counts, max_nodes: int = 300) -> dict:
    """Pure transform behind GET /{index_id}/graph.

    Turns entity rows + relation rows (+ a ``{entity_id: mention_count}`` map)
    into the ``{nodes, edges, truncated, total_nodes}`` payload the frontend
    renders. When the index has more than ``max_nodes`` entities, keep the
    most-connected ones (edge degree desc, then mention_count) and drop edges to
    pruned nodes so the whole-graph view stays responsive. Kept dependency-free
    (ORM rows in, plain dicts out) so it can be unit-tested without a DB.
    """
    entities = list(entities)
    relations = list(relations)
    total_nodes = len(entities)

    # Degree = number of relation endpoints touching each entity.
    degree: dict = {}
    for r in relations:
        degree[r.src_entity_id] = degree.get(r.src_entity_id, 0) + 1
        degree[r.dst_entity_id] = degree.get(r.dst_entity_id, 0) + 1

    kept = entities
    if total_nodes > max_nodes:
        kept = sorted(
            entities,
            key=lambda e: (degree.get(e.id, 0), mention_counts.get(e.id, 0), str(e.id)),
            reverse=True,
        )[:max_nodes]
    kept_ids = {e.id for e in kept}

    nodes = [
        GraphNodeOut(
            id=e.id,
            label=e.canonical_name,
            type=e.entity_type,
            description=e.description,
            mention_count=int(mention_counts.get(e.id, 0)),
        ).model_dump(mode="json")
        for e in kept
    ]
    edges = [
        GraphEdgeOut(
            source=r.src_entity_id,
            target=r.dst_entity_id,
            relation=r.relation,
            description=r.description,
            weight=float(r.weight),
        ).model_dump(mode="json")
        for r in relations
        if r.src_entity_id in kept_ids and r.dst_entity_id in kept_ids
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": total_nodes > len(kept_ids),
        "total_nodes": total_nodes,
    }


@router.get("/{index_id}/graph")
async def get_index_graph(
    index_id: UUID,
    payload: TokenPayload = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    max_nodes: int = 300,
):
    """Whole knowledge graph for an index — every entity (node) and relation
    (edge) — for the full-page graph view.

    Capped at the ``max_nodes`` most-connected entities so a large index stays
    renderable; ``truncated``/``total_nodes`` tell the UI when nodes were
    dropped. Returns ``kg_available: false`` (not an error) when the index has
    no extracted entities yet, mirroring the concepts/search contract.
    """
    user_id = UUID(payload.sub)
    await _load_owned(session, index_id, user_id)
    max_nodes = max(1, min(max_nodes, 1000))

    entities = (
        await session.execute(select(Entity).where(Entity.index_id == index_id))
    ).scalars().all()

    if not entities:
        return success_response(
            {
                "index_id": str(index_id),
                "kg_available": False,
                "nodes": [],
                "edges": [],
                "truncated": False,
                "total_nodes": 0,
            }
        )

    relations = (
        await session.execute(
            select(EntityRelation).where(EntityRelation.index_id == index_id)
        )
    ).scalars().all()

    entity_ids = [e.id for e in entities]
    count_rows = (
        await session.execute(
            select(
                EntityMention.entity_id,
                func.count(EntityMention.segment_idx).label("mention_count"),
            )
            .where(EntityMention.entity_id.in_(entity_ids))
            .group_by(EntityMention.entity_id)
        )
    ).all()
    mention_counts = {r.entity_id: int(r.mention_count) for r in count_rows}

    graph = build_graph_payload(entities, relations, mention_counts, max_nodes=max_nodes)
    return success_response({"index_id": str(index_id), "kg_available": True, **graph})
