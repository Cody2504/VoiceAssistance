"""Analyze tile — long-context Q&A over a single video.

At query time we assemble three layers of context for the LLM:

  1. The video's **global summary** (one paragraph, persisted on
     ``videos.global_summary`` at ingest).
  2. The **full ordered list of window summaries** (~2 min each, fetched from
     Qdrant point payloads — distinct ``window_idx`` only). This is the key
     trick that lets the LLM connect distant parts of a 1–2 hour video. For
     typical content the full window-summary list is ~2–3K tokens.
  3. The **top-K segments retrieved by dense similarity** to the user's
     question — these provide concrete timestamps and verbatim transcripts for
     the LLM to quote.

The LLM is instructed to emit inline ``[mm:ss-mm:ss]`` citations so the
frontend can render them as click-to-seek chips.

A token-budget guard truncates the window-summary list before falling back to
dropping the per-segment transcripts of windows that weren't directly
retrieved — preserves the skeleton, sacrifices the detail in the long tail.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from main.settings import get_settings

log = logging.getLogger(__name__)


@dataclass
class AnalyzeResult:
    video_id: str
    question: str
    answer: str
    citations: list[dict[str, Any]]   # [{t_start, t_end, segment_idx}]
    used_windows: int
    used_segments: int


def run_analyze(video_id: UUID, question: str, global_summary: str | None = None) -> AnalyzeResult:
    """Long-context Q&A. Reads only Qdrant + the videos row; no model load."""
    s = get_settings()
    vid = str(video_id)

    # --- 1. Dense top-K segments ---
    retrieved = _retrieve_top_segments(vid, question, k=s.analyze_top_k_segments)
    log.info("analyze:retrieved=%d for video=%s", len(retrieved), vid)

    # --- 2. Full ordered window-summary skeleton ---
    windows = _fetch_window_summaries(vid)
    log.info("analyze:windows=%d", len(windows))

    # --- 2b. Fine-grained action timeline (vlm_actions + on-screen text) ---
    # Precise per-action [t_start, t_end] moments so the LLM can cite the exact
    # instant an action happens (e.g. "tomato sauce poured" at 1:02) instead of
    # the coarse ~30s segment that merely contains it.
    actions = _fetch_action_events(vid)
    log.info("analyze:actions=%d", len(actions))

    # --- 3. Global summary (passed in by caller from videos.global_summary). ---
    global_text = (global_summary or "").strip() or _fetch_global_summary_from_qdrant(vid)

    # --- 4. Build the LLM prompt with token-budget guard ---
    prompt = _build_prompt(question, global_text, windows, retrieved, actions,
                           token_budget=s.analyze_token_budget)

    # --- 5. Call the LLM ---
    answer = _call_llm(prompt)

    # --- 6. Parse [mm:ss–mm:ss] citations for the frontend chips ---
    citations = _parse_citations(answer, retrieved)

    return AnalyzeResult(
        video_id=vid,
        question=question,
        answer=answer,
        citations=citations,
        used_windows=len(windows),
        used_segments=len(retrieved),
    )


# ---------------------------------------------------------------------------
# Qdrant access
# ---------------------------------------------------------------------------


def _retrieve_top_segments(video_id: str, question: str, k: int) -> list[dict]:
    """Dense top-K segments by caption-embedding similarity to the question.

    The Analyze tile uses the `jockey_segments_text` collection (3072-d
    text-embedding-3-large vectors per segment), which is populated by the
    ingest pipeline alongside the visual collection. One embedding call for
    the question, one Qdrant search — no per-segment loop.
    """
    s = get_settings()
    try:
        from main.encoders.search import TextEmbedder
        from main.encoders.config import config
        from main.qdrant_util import get_qdrant_client, to_vector_list
        from qdrant_client.http import models as qm

        embedder = TextEmbedder(
            api_key=config.openrouter_api_key,
            model=config.text_embedding_model,
            base_url=config.openrouter_base_url,
        )
        client = get_qdrant_client(timeout=60)
        q_vec = embedder.encode(question)
        hits = client.search(
            collection_name="jockey_segments_text",
            query_vector=to_vector_list(q_vec),
            query_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=video_id)),
            ]),
            limit=k,
            with_payload=True,
        )
        return [h.payload for h in hits if h.payload]
    except Exception as exc:
        log.warning("analyze:retrieve failed: %s", exc)
        return []


def _fetch_window_summaries(video_id: str) -> list[dict]:
    """One entry per distinct window_idx, ordered by t_start."""
    s = get_settings()
    try:
        from main.qdrant_util import get_qdrant_client
        from qdrant_client.http import models as qm
        client = get_qdrant_client(timeout=60)
        points, _ = client.scroll(
            collection_name=s.qdrant_collection,
            scroll_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=video_id)),
            ]),
            with_payload=True,
            with_vectors=False,
            limit=4096,
        )
        seen: dict[int, dict] = {}
        for p in points:
            pl = p.payload or {}
            w_idx = pl.get("window_idx")
            if w_idx is None or w_idx in seen:
                continue
            if not (pl.get("window_summary") or "").strip():
                continue
            seen[w_idx] = {
                "window_idx": int(w_idx),
                "t_start": float(pl.get("t_start", w_idx * 120.0)),
                "summary": pl["window_summary"],
            }
        return sorted(seen.values(), key=lambda x: x["window_idx"])
    except Exception as exc:
        log.warning("analyze:fetch_windows failed: %s", exc)
        return []


def _fetch_action_events(video_id: str, limit: int = 80) -> list[dict]:
    """Fine-grained `vlm_actions` + `on_screen_text` moments with PRECISE
    [t_start, t_end] from the timeline-events collection. These let the LLM cite
    the exact instant an action occurs rather than the coarse segment span."""
    s = get_settings()
    try:
        from main.qdrant_util import get_qdrant_client
        from qdrant_client.http import models as qm
        client = get_qdrant_client(timeout=60)
        points, _ = client.scroll(
            collection_name=s.timeline_events_collection,
            scroll_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=video_id)),
            ]),
            with_payload=True,
            with_vectors=False,
            limit=4096,
        )
        out: list[dict] = []
        for p in points:
            pl = p.payload or {}
            if pl.get("track_kind") not in ("vlm_actions", "on_screen_text"):
                continue
            label = (pl.get("label") or "").strip()
            if not label:
                continue
            out.append({
                "t_start": float(pl.get("t_start", 0.0)),
                "t_end": float(pl.get("t_end", 0.0)),
                "label": label,
            })
        out.sort(key=lambda x: x["t_start"])
        return out[:limit]
    except Exception as exc:
        log.warning("analyze:fetch_actions failed: %s", exc)
        return []


def _fetch_global_summary_from_qdrant(video_id: str) -> str:
    s = get_settings()
    try:
        from main.qdrant_util import get_qdrant_client
        from qdrant_client.http import models as qm
        client = get_qdrant_client(timeout=60)
        points, _ = client.scroll(
            collection_name="jockey_videos",
            scroll_filter=qm.Filter(must=[
                qm.FieldCondition(key="video_id", match=qm.MatchValue(value=video_id)),
            ]),
            with_payload=True,
            with_vectors=False,
            limit=1,
        )
        return (points[0].payload.get("global_summary") if points else "") or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Prompt assembly + LLM
# ---------------------------------------------------------------------------


def _build_prompt(
    question: str,
    global_summary: str,
    windows: list[dict],
    retrieved: list[dict],
    actions: list[dict],
    token_budget: int,
) -> str:
    skeleton_lines = "\n".join(
        f"- [{_fmt(w['t_start'])}] {w['summary']}" for w in windows
    )
    # Fine-grained action timeline — small + high value, kept in every fallback.
    action_lines = "\n".join(
        f"- [{_fmt(a['t_start'])}-{_fmt(a['t_end'])}] {a['label']}" for a in actions
    )
    seg_lines_full = "\n".join(
        f"- [{_fmt(p.get('t_start', 0))}-{_fmt(p.get('t_end', 0))}] "
        f"caption: {(p.get('caption') or '').strip()}  "
        f"transcript: {(p.get('transcript') or '').strip()}"
        for p in retrieved
    )
    prompt = _assemble(question, global_summary, skeleton_lines, action_lines, seg_lines_full)
    if _approx_tokens(prompt) <= token_budget:
        return prompt

    # Fall back 1: drop transcripts but keep captions and the full window skeleton.
    seg_lines_short = "\n".join(
        f"- [{_fmt(p.get('t_start', 0))}-{_fmt(p.get('t_end', 0))}] {(p.get('caption') or '').strip()}"
        for p in retrieved
    )
    prompt = _assemble(question, global_summary, skeleton_lines, action_lines, seg_lines_short)
    log.warning("analyze:prompt over budget — dropped transcripts from retrieved segments")
    if _approx_tokens(prompt) <= token_budget:
        return prompt

    # Fall back 2: very long video — interleave-drop windows to halve the
    # skeleton until it fits. Multi-hop reasoning quality degrades gracefully.
    sparse = windows[::2]
    skeleton_short = "\n".join(
        f"- [{_fmt(w['t_start'])}] {w['summary']}" for w in sparse
    )
    prompt = _assemble(question, global_summary, skeleton_short, action_lines, seg_lines_short)
    log.warning("analyze:prompt still over budget — dropping every-other window summary")
    return prompt


def _assemble(question: str, global_summary: str, skeleton_lines: str,
              action_lines: str, seg_lines: str) -> str:
    return (
        "You are answering a question about a video by reading layers "
        "of context that have already been precomputed for you. "
        "Cite timestamps inline as [mm:ss-mm:ss]. If the answer requires "
        "connecting multiple parts of the video, name the parts by their "
        "timestamps explicitly. Do not invent timestamps that aren't in the "
        "context below.\n"
        "IMPORTANT: when the question asks WHEN something happens or about a "
        "specific action/moment, cite the precise [mm:ss-mm:ss] from the ACTION "
        "TIMELINE (fine-grained) rather than the coarser segment span — the "
        "action timeline pinpoints the exact instant.\n\n"
        f"── GLOBAL SUMMARY ──\n{global_summary or '(none)'}\n\n"
        "── VIDEO SKELETON (in order, one bullet per ~2 minutes) ──\n"
        f"{skeleton_lines or '(none)'}\n\n"
        "── ACTION TIMELINE (fine-grained moments, precise timestamps) ──\n"
        f"{action_lines or '(none)'}\n\n"
        "── RELEVANT SEGMENTS (retrieved by similarity to the question) ──\n"
        f"{seg_lines or '(none)'}\n\n"
        f"── QUESTION ──\n{question}\n\n"
        "Answer concisely. Use inline [mm:ss-mm:ss] citations when grounding "
        "a claim in the video — the most specific moment that answers the "
        "question. If the video does not contain the answer, say so plainly."
    )


def _call_llm(prompt: str) -> str:
    from openai import OpenAI
    s = get_settings()
    client = OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)
    try:
        resp = client.chat.completions.create(
            model=s.summary_llm_model,
            messages=[
                {"role": "system", "content": "You answer questions about videos using only the provided context."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.error("analyze:llm call failed: %s", exc)
        return f"(model error: {exc})"


# ---------------------------------------------------------------------------
# Citation parsing
# ---------------------------------------------------------------------------


_CITATION_RE = None


def _parse_citations(answer: str, retrieved: list[dict]) -> list[dict[str, Any]]:
    """Extract `[mm:ss-mm:ss]` spans the LLM emitted, matching each to the
    nearest retrieved segment so the UI can render a click-to-seek chip with
    a thumbnail."""
    import re
    global _CITATION_RE
    if _CITATION_RE is None:
        _CITATION_RE = re.compile(r"\[(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\]")
    out: list[dict[str, Any]] = []
    for m in _CITATION_RE.finditer(answer):
        t0 = int(m.group(1)) * 60 + int(m.group(2))
        t1 = int(m.group(3)) * 60 + int(m.group(4))
        best = None
        best_dist = float("inf")
        for p in retrieved:
            ps = float(p.get("t_start", 0))
            pe = float(p.get("t_end", 0))
            mid_d = abs((ps + pe) / 2 - (t0 + t1) / 2)
            if mid_d < best_dist:
                best, best_dist = p, mid_d
        out.append({
            "t_start": float(t0),
            "t_end": float(t1),
            "segment_idx": int(best.get("segment_idx", -1)) if best else -1,
        })
    return out


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _cosine(a, b) -> float:
    import numpy as np
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def _approx_tokens(s: str) -> int:
    # Cheap heuristic — avoids paying for tiktoken on every analyze call.
    return max(1, len(s) // 4)


def _fmt(t: float) -> str:
    sec = max(0, int(round(t)))
    return f"{sec // 60:02d}:{sec % 60:02d}"
