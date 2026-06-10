"""Shared Qdrant access helpers.

Before this module the same three idioms were copy-pasted across ~20 call sites:
building a ``QdrantClient`` from settings, the "create collection only if it
doesn't exist yet" check, and batched upserts. They are consolidated here.

Qdrant is used only by video-service, so this lives under ``main`` rather than
``cm_shared``. Lazy imports keep ``qdrant-client`` out of import paths that don't
need it (and out of the test harness unless a test exercises a real client).
"""
from __future__ import annotations


def get_qdrant_client(timeout=None):
    """Build a ``QdrantClient`` from the active settings.

    ``timeout`` is passed through verbatim. When ``None`` the kwarg is omitted so
    the client keeps its library default (~5 s) — this preserves the behavior of
    the fast query-path call sites that never set a timeout. Long-running callers
    (ingest 300 s, query tiles 60 s, etc.) pass their value explicitly.
    """
    from qdrant_client import QdrantClient

    from main.settings import get_settings

    s = get_settings()
    if timeout is None:
        return QdrantClient(host=s.qdrant_host, port=s.qdrant_port)
    return QdrantClient(host=s.qdrant_host, port=s.qdrant_port, timeout=timeout)


def ensure_collection(client, name, dim, *, distance=None, existing=None):
    """Create the collection ``name`` (COSINE, ``dim``-d) only if it is missing.

    Pass ``existing`` (a set of collection names already fetched by the caller) to
    avoid an extra ``get_collections()`` round-trip when ensuring several
    collections in a row — used by the ingest path.
    """
    from qdrant_client.http import models as qm

    names = existing if existing is not None else {c.name for c in client.get_collections().collections}
    if name not in names:
        client.create_collection(
            name,
            vectors_config=qm.VectorParams(size=dim, distance=distance or qm.Distance.COSINE),
        )


def batched_upsert(client, collection, points, batch_size=32):
    """Upsert ``points`` in fixed-size batches so a single oversized request
    doesn't blow the Cloudflare-tunnel body limit and partial failure stays
    recoverable."""
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=collection, points=points[i:i + batch_size])


def to_vector_list(v):
    """Coerce a vector (numpy array or sequence) to a plain ``list`` for Qdrant."""
    return v.tolist() if hasattr(v, "tolist") else list(v)
