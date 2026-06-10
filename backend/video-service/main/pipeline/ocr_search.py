"""OCR search (roadmap #1) — exact on-screen-text retrieval via a Qdrant
full-text payload index over `ocr_text`.

`ocr_text` is already stored per-segment in the `jockey_segments_text` /
`jockey_shots` payloads at ingest (no re-ingest needed). We add a WORD
full-text index on it and expose a lexical match path — its own retrieval
stream (per `feedback_tool_decomposition`), not fused into CLIP scoring.
"""
from __future__ import annotations

import logging

from main.settings import get_settings

log = logging.getLogger(__name__)

# jockey_segments_text shares the per-segment payload (ocr_text + t_start/t_end + video_id).
OCR_COLLECTION = "jockey_segments_text"


def _qdrant():
    from main.qdrant_util import get_qdrant_client
    return get_qdrant_client(timeout=60)


def ensure_ocr_index(*, client=None, collection: str = OCR_COLLECTION) -> bool:
    """Create a WORD full-text payload index on `ocr_text` (idempotent —
    re-creating an existing index is a no-op error we swallow). Returns True if
    the create call succeeded, False if it errored (e.g. already exists)."""
    from qdrant_client.http import models as qm
    c = client or _qdrant()
    try:
        c.create_payload_index(
            collection_name=collection,
            field_name="ocr_text",
            field_schema=qm.TextIndexParams(
                type=qm.TextIndexType.TEXT,
                tokenizer=qm.TokenizerType.WORD,
                min_token_len=2,
                lowercase=True,
            ),
        )
        return True
    except Exception as exc:  # noqa: BLE001  (already-exists is expected on re-run)
        log.info("ocr:ensure index on %s.ocr_text — %s", collection, exc)
        return False


def ocr_candidates(query: str, video_id=None, *, settings=None, client=None,
                   collection: str = OCR_COLLECTION) -> list[dict]:
    """Full-text match over `ocr_text`. `video_id=None` → cross-video. Returns
    [{t_start, t_end, ocr_text, video_id, score}] (score 1.0 — exact lexical)."""
    from qdrant_client.http import models as qm
    q = (query or "").strip()
    if not q:
        return []
    s = settings or get_settings()
    c = client or _qdrant()
    must = [qm.FieldCondition(key="ocr_text", match=qm.MatchText(text=q))]
    if video_id is not None:
        must.append(qm.FieldCondition(key="video_id", match=qm.MatchValue(value=str(video_id))))
    try:
        points, _ = c.scroll(
            collection_name=collection, scroll_filter=qm.Filter(must=must),
            with_payload=True, with_vectors=False, limit=s.when_top_n,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ocr:scroll failed: %s", exc)
        return []
    out: list[dict] = []
    for p in points:
        pl = p.payload or {}
        txt = (pl.get("ocr_text") or "").strip()
        if not txt:
            continue
        out.append({
            "t_start": float(pl.get("t_start", 0.0)), "t_end": float(pl.get("t_end", 0.0)),
            "ocr_text": txt, "video_id": pl.get("video_id"), "score": 1.0,
        })
    return out
