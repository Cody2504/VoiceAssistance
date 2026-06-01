"""Knowledge-graph extraction for cross-video reasoning (Phase 2a).

Per-window LLM call → entity + relation tuples → canonicalise within the index
→ persist to Postgres (entities, entity_mentions, entity_relations) and Qdrant
(jockey_entities). Reuses the existing hierarchical summarizer's window
summaries as the LLM input, so this step is purely LLM + DB-side work — no
video re-decode, no embedding re-extraction beyond a single text-embedding call
per new entity.

Prompt ported from VideoRAG (videorag/prompt.py, "entity_extraction"), itself
adapted from graphrag (https://github.com/microsoft/graphrag). The delimited
output format keeps the parser deterministic and language-agnostic — works on
Vietnamese transcripts as long as the LLM emits the structural tokens
(``("entity"...)``, ``##``, ``<|COMPLETE|>``) in the same shape as the examples.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Sequence
from uuid import UUID, uuid4

import numpy as np

from main.encoders.search import TextEmbedder
from main.models.kg import Entity, EntityMention, EntityRelation
from main.pipeline.summarize import SegmentRecord, WindowSummary
from main.settings import Settings, get_settings

log = logging.getLogger(__name__)


# --- delimiters (kept compatible with VideoRAG's PROMPTS["entity_extraction"]) -
_TUPLE = "<|>"
_RECORD = "##"
_COMPLETION = "<|COMPLETE|>"


_SYSTEM_MSG = (
    "You are an information-extraction assistant. Read a transcript/summary "
    "of a video segment and emit entities + relationships in the requested "
    "delimited format. Preserve the source language for names; technical "
    "terms that originated in English (e.g. 'softmax', 'attention') stay in "
    "English even in a Vietnamese transcript."
)


_PROMPT_TEMPLATE = """-Goal-
Given a window summary from a recorded lecture / instructional video and a list of entity types, identify all entities of those types and the relationships among them.

-Steps-
1. For each entity emit:
("entity"{T}<name>{T}<type>{T}<one-sentence description>)
   - <name>: keep capitalisation that appears in the text; keep English technical terms in English even inside a non-English transcript.
   - <type>: one of [{entity_types}].
   - <description>: one factual sentence about what the entity is and how it shows up here.

2. For each pair of clearly-related entities emit:
("relationship"{T}<src>{T}<dst>{T}<why they are related>{T}<integer 1-10 strength>)

3. Separate every record with {R}.

4. End the output with {C}.

-Format hints-
- Don't repeat the entity_types list back to the user.
- If the window is silent / contains only filler, output just {C}.
- Don't invent entities that don't appear in the window text.

-Window context-
Video: {video_title}
Window: {window_start}-{window_end}
Window summary:
{window_text}

Per-segment notes inside this window:
{segment_bullets}

Output:
"""


# ---------------------------------------------------------------- parsing -----

_ENTITY_RX = re.compile(
    r'\(\s*"entity"\s*' + re.escape(_TUPLE)
    + r"\s*(?P<name>[^" + re.escape(_TUPLE) + r"]+?)\s*" + re.escape(_TUPLE)
    + r"\s*(?P<type>[^" + re.escape(_TUPLE) + r"]+?)\s*" + re.escape(_TUPLE)
    + r"\s*(?P<desc>.+?)\s*\)",
    re.DOTALL,
)

_REL_RX = re.compile(
    r'\(\s*"relationship"\s*' + re.escape(_TUPLE)
    + r"\s*(?P<src>[^" + re.escape(_TUPLE) + r"]+?)\s*" + re.escape(_TUPLE)
    + r"\s*(?P<dst>[^" + re.escape(_TUPLE) + r"]+?)\s*" + re.escape(_TUPLE)
    + r"\s*(?P<desc>.+?)\s*" + re.escape(_TUPLE)
    + r"\s*(?P<strength>\d+(?:\.\d+)?)\s*\)",
    re.DOTALL,
)


@dataclass
class _RawEntity:
    name: str
    type: str
    description: str


@dataclass
class _RawRelation:
    src: str
    dst: str
    description: str
    strength: float


def _parse_extraction(raw: str) -> tuple[list[_RawEntity], list[_RawRelation]]:
    body = raw.split(_COMPLETION)[0]
    entities: list[_RawEntity] = []
    for m in _ENTITY_RX.finditer(body):
        name = _strip_quotes(m.group("name"))
        etype = _strip_quotes(m.group("type"))
        desc = _strip_quotes(m.group("desc"))
        if not name:
            continue
        entities.append(_RawEntity(name=name, type=etype.lower(), description=desc))
    relations: list[_RawRelation] = []
    for m in _REL_RX.finditer(body):
        try:
            strength = float(m.group("strength"))
        except ValueError:
            strength = 1.0
        src = _strip_quotes(m.group("src"))
        dst = _strip_quotes(m.group("dst"))
        if not src or not dst:
            continue
        relations.append(
            _RawRelation(
                src=src,
                dst=dst,
                description=_strip_quotes(m.group("desc")),
                strength=strength,
            )
        )
    return entities, relations


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        s = s[1:-1]
    return s.strip()


# --------------------------------------------------------------- LLM client --

def _llm_client(settings: Settings):
    from openai import OpenAI
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


def _llm_extract(
    client,
    settings: Settings,
    window: WindowSummary,
    segments_in_window: Sequence[SegmentRecord],
    video_title: str,
) -> str:
    segment_bullets = "\n".join(
        f"- segment {s.idx} ({_fmt(s.t_start)}-{_fmt(s.t_end)}): "
        f"{(s.caption or '').strip()} | said: {(s.transcript or '').strip()}"
        for s in segments_in_window
    ) or "(no per-segment notes)"
    prompt = _PROMPT_TEMPLATE.format(
        T=_TUPLE,
        R=_RECORD,
        C=_COMPLETION,
        entity_types=", ".join(settings.kg_entity_types),
        video_title=video_title or "(untitled)",
        window_start=_fmt(window.t_start),
        window_end=_fmt(window.t_end),
        window_text=window.summary or "(no summary)",
        segment_bullets=segment_bullets,
    )
    try:
        resp = client.chat.completions.create(
            model=settings.summary_llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1200,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("kg_extract:llm call failed for window=%s: %s", window.idx, exc)
        return ""


def _fmt(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60:02d}:{s % 60:02d}"


# -------------------------------------------------------- canonicalisation ---

def _normalise(name: str) -> str:
    """Lowercase + collapse whitespace; what we hash for exact-match lookups."""
    return " ".join(name.lower().split())


def _embed_entity_text(embedder: TextEmbedder, name: str, description: str) -> np.ndarray:
    return embedder.encode(f"{name}: {description}")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ---------------------------------------------- main entry point used by ingest

@dataclass
class KGExtractResult:
    entities_added: int
    entities_reused: int
    mentions: int
    relations: int


def run_kg_extract(
    *,
    video_id: UUID,
    index_id: UUID,
    user_id: UUID,
    video_title: str,
    segments: Sequence[SegmentRecord],
    windows: Sequence[WindowSummary],
    qdrant_point_id_for: callable,  # (segment_idx: int) -> str — UUID5 from ingest
    db_session,                     # sync SQLAlchemy session
    settings: Settings | None = None,
) -> KGExtractResult:
    """Extract a knowledge graph for one video into the index it belongs to.

    The function is best-effort: any LLM / parse failure on an individual window
    is logged and skipped; we never crash the parent ingest job over a bad KG
    extraction (the rest of the video still becomes searchable).
    """
    settings = settings or get_settings()
    if not settings.openrouter_api_key:
        log.info("kg_extract: skipped — no OPENROUTER_API_KEY configured")
        return KGExtractResult(0, 0, 0, 0)
    if not windows:
        log.info("kg_extract: skipped — no window summaries (video_id=%s)", video_id)
        return KGExtractResult(0, 0, 0, 0)

    client = _llm_client(settings)
    embedder = TextEmbedder(api_key=settings.openrouter_api_key)

    # Pre-load every entity already in this index so we can canonicalise without
    # round-tripping the DB per call. Few thousand rows at most, fits in memory.
    existing = (
        db_session.query(Entity).filter(Entity.index_id == index_id).all()
    )
    existing_by_norm: dict[str, Entity] = {_normalise(e.canonical_name): e for e in existing}
    existing_vectors: dict[UUID, np.ndarray] = {}

    segments_by_idx = {s.idx: s for s in segments}

    raw_entities_seen: dict[str, _RawEntity] = {}
    mentions_seen: set[tuple[UUID, int]] = set()  # (entity_id, segment_idx)
    relations_seen: dict[tuple[UUID, UUID, str], _RawRelation] = {}

    new_entities: list[Entity] = []
    new_mentions: list[EntityMention] = []
    relation_pairs: list[tuple[UUID, UUID, str, _RawRelation, list[str]]] = []

    qdrant_payloads: list[dict] = []  # for jockey_entities upsert at the end

    entities_added = 0
    entities_reused = 0

    for w in windows:
        win_segments = [segments_by_idx[i] for i in w.segment_indices if i in segments_by_idx]
        raw = _llm_extract(client, settings, w, win_segments, video_title)
        if not raw:
            continue
        ents, rels = _parse_extraction(raw)

        # Resolve every entity to a row id (existing or new).
        local_ids: dict[str, UUID] = {}
        for e in ents:
            norm = _normalise(e.name)
            if not norm:
                continue
            row = existing_by_norm.get(norm)
            if row is None:
                # Try fuzzy match by cosine on the embedding.
                vec = _embed_entity_text(embedder, e.name, e.description)
                best_id: UUID | None = None
                best_score = 0.0
                for other in existing_by_norm.values():
                    if other.entity_type and e.type and other.entity_type != e.type:
                        continue
                    ov = existing_vectors.get(other.id)
                    if ov is None:
                        continue
                    score = _cosine(vec, ov)
                    if score > best_score:
                        best_score = score
                        best_id = other.id
                if best_id is not None and best_score >= settings.kg_canonical_sim_threshold:
                    row = next(o for o in existing if o.id == best_id)
                else:
                    new_id = uuid4()
                    point_id = uuid4()
                    row = Entity(
                        id=new_id,
                        index_id=index_id,
                        canonical_name=e.name,
                        entity_type=e.type or None,
                        description=e.description or None,
                        qdrant_point_id=point_id,
                    )
                    new_entities.append(row)
                    existing.append(row)
                    existing_by_norm[norm] = row
                    existing_vectors[new_id] = vec
                    qdrant_payloads.append(
                        {
                            "id": str(point_id),
                            "vector": vec.tolist(),
                            "payload": {
                                "entity_id": str(new_id),
                                "index_id": str(index_id),
                                "user_id": str(user_id),
                                "canonical_name": e.name,
                                "entity_type": e.type or "",
                                "video_ids": [str(video_id)],
                                "mention_count": 1,
                            },
                        }
                    )
                    entities_added += 1
            else:
                entities_reused += 1
            local_ids[e.name] = row.id
            raw_entities_seen[e.name] = e

            # Attach a mention to every segment in this window — coarse but
            # cheap. Phase 3's hybrid scorer narrows by similarity anyway.
            for s in win_segments:
                key = (row.id, s.idx)
                if key in mentions_seen:
                    continue
                mentions_seen.add(key)
                new_mentions.append(
                    EntityMention(
                        entity_id=row.id,
                        video_id=video_id,
                        segment_idx=s.idx,
                        qdrant_point_id=UUID(qdrant_point_id_for(s.idx)),
                        t_start=s.t_start,
                        t_end=s.t_end,
                        weight=1.0,
                    )
                )

        # Relations are resolved using the local_ids map; any name we didn't
        # see as an entity in this window is silently dropped (the LLM
        # occasionally invents one side of a relation).
        win_segment_ids = [qdrant_point_id_for(s.idx) for s in win_segments]
        for r in rels:
            src_id = local_ids.get(r.src) or local_ids.get(_normalise(r.src))
            dst_id = local_ids.get(r.dst) or local_ids.get(_normalise(r.dst))
            if not src_id or not dst_id or src_id == dst_id:
                continue
            relation = (r.description.split(".")[0])[:120].lower().strip() or "related_to"
            key = (src_id, dst_id, relation)
            existing_rel = relations_seen.get(key)
            if existing_rel is None:
                relations_seen[key] = r
                relation_pairs.append((src_id, dst_id, relation, r, list(win_segment_ids)))

    # --- persist ----------------------------------------------------------
    if new_entities:
        db_session.add_all(new_entities)
    if new_mentions:
        db_session.add_all(new_mentions)

    # Relations: insert or accumulate weight if already present.
    for src_id, dst_id, relation, r, segs in relation_pairs:
        existing_relation = (
            db_session.query(EntityRelation)
            .filter(
                EntityRelation.index_id == index_id,
                EntityRelation.src_entity_id == src_id,
                EntityRelation.dst_entity_id == dst_id,
                EntityRelation.relation == relation,
            )
            .one_or_none()
        )
        if existing_relation is None:
            db_session.add(
                EntityRelation(
                    index_id=index_id,
                    src_entity_id=src_id,
                    dst_entity_id=dst_id,
                    relation=relation,
                    description=r.description,
                    weight=r.strength,
                    source_segment_ids=segs,
                )
            )
        else:
            existing_relation.weight = max(existing_relation.weight, r.strength)
            existing_relation.source_segment_ids = list(
                {*(existing_relation.source_segment_ids or []), *segs}
            )
    db_session.commit()

    # Mention-count bump on entities reused across the run.
    if qdrant_payloads:
        _upsert_entity_points(qdrant_payloads, settings)

    log.info(
        "kg_extract: video=%s index=%s entities=+%d reused=%d mentions=%d relations=%d",
        video_id,
        index_id,
        entities_added,
        entities_reused,
        len(new_mentions),
        len(relation_pairs),
    )
    return KGExtractResult(
        entities_added=entities_added,
        entities_reused=entities_reused,
        mentions=len(new_mentions),
        relations=len(relation_pairs),
    )


def _upsert_entity_points(points: Iterable[dict], settings: Settings) -> None:
    """Upsert entity-level embeddings into jockey_entities. Lazy import keeps
    qdrant-client out of the test harness."""
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm

    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout=300,  # mirrors ingest.py's defensive timeout
    )
    collection = settings.kg_qdrant_collection
    existing_collections = {c.name for c in client.get_collections().collections}
    points = list(points)
    if not points:
        return
    dim = len(points[0]["vector"])
    if collection not in existing_collections:
        client.create_collection(
            collection,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
    # Upsert in modest batches to stay well under any body-size limit.
    BATCH = 64
    for i in range(0, len(points), BATCH):
        chunk = points[i : i + BATCH]
        client.upsert(
            collection_name=collection,
            points=[
                qm.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
                for p in chunk
            ],
        )
