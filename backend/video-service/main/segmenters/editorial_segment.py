"""Cut 2 / Task 11.11 — editorial_segment.

Structural / narrative segmentation built on top of the cached ASR + caption
data. No GPU, no remote inference — runs entirely through OpenRouter against
text we already have.

Approach
--------
1. Pack shots into ~90s chunks (large enough that the LLM has narrative
   context, small enough to fit a single prompt comfortably).
2. For each chunk, ask the LLM to label it with one of a small set of
   editorial roles (intro / segment / interview / b-roll / outro / etc.)
   plus a one-line summary.
3. Merge adjacent chunks with the same role into one segment.

The role taxonomy can be customised by the user via the `role` field's
`enum`. If no enum is provided we fall back to a sensible default.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition
from main.settings import get_settings

from .qdrant_io import read_shots

log = logging.getLogger(__name__)

CHUNK_SECONDS = 90.0
MAX_CHUNKS = 24
DEFAULT_ROLES = ["intro", "segment", "interview", "b_roll", "ad_break", "outro"]


def _pack_chunks(shots: list[dict[str, Any]], chunk_s: float) -> list[list[dict[str, Any]]]:
    if not shots:
        return []
    chunks: list[list[dict[str, Any]]] = [[]]
    chunk_start = shots[0]["t_start"]
    for sh in shots:
        if sh["t_end"] - chunk_start > chunk_s and chunks[-1]:
            chunks.append([])
            chunk_start = sh["t_start"]
        chunks[-1].append(sh)
    return chunks


def _format_chunk(chunk: list[dict[str, Any]]) -> str:
    lines = []
    for sh in chunk:
        cap = (sh.get("chunk_caption") or "").strip()
        asr = (sh.get("asr_text") or "").strip()
        if not cap and not asr:
            continue
        lines.append(f"[{sh['t_start']:.1f}-{sh['t_end']:.1f}s] cap={cap} | asr={asr}"[:240])
    return "\n".join(lines) or "(no captions or speech in this window)"


def _call_llm(api_key: str, model: str, context: str, roles: list[str]) -> dict[str, Any] | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You label structural roles of windows from a video. "
                        f"Pick exactly one role from {roles}. "
                        "Also produce a one-sentence editorial summary (≤25 words). "
                        "Reply with JSON only — keys: role (string), summary (string)."
                    ),
                },
                {"role": "user", "content": context},
            ],
            max_tokens=200,
            temperature=0.1,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("editorial_segment:llm call failed: %s", exc)
        return None


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    if not shots:
        return []

    chunks = _pack_chunks(shots, CHUNK_SECONDS)[:MAX_CHUNKS]
    if not chunks:
        return []

    field_names = {f.name for f in definition.fields}
    role_field = next((f for f in definition.fields if f.name == "role"), None)
    roles = role_field.enum if role_field and role_field.enum else DEFAULT_ROLES

    s = get_settings()
    api_key = (s.openrouter_api_key or "").strip()
    model = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")

    if not api_key:
        # No LLM available → return one segment per chunk with empty metadata.
        return [
            {"t_start": ch[0]["t_start"], "t_end": ch[-1]["t_end"], "metadata": {}}
            for ch in chunks
        ]

    def _process(ch: list[dict[str, Any]]) -> tuple[float, float, dict[str, Any]] | None:
        ctx = _format_chunk(ch)
        raw = _call_llm(api_key, model, ctx, roles) or {}
        role = raw.get("role")
        if role not in roles:
            role = None
        summary = str(raw.get("summary", "")).strip()
        meta: dict[str, Any] = {}
        if "role" in field_names and role:
            meta["role"] = role
        if "summary" in field_names:
            meta["summary"] = summary
        # Twelve Labs `editorial_narratives` schema aliases. The LLM call here
        # only asks for role + summary; richer fields (editorial_subjects /
        # visual_subjects / names) would need a second LLM pass with the full
        # chunk context — left empty until that's added. `confidence` is fixed
        # to HIGH when the role classification succeeded, LOW otherwise.
        if "segment_title" in field_names:
            meta["segment_title"] = summary[:60].rstrip(",. ") if summary else (role or "")
        if "description" in field_names:
            meta["description"] = summary
        if "confidence" in field_names:
            meta["confidence"] = "HIGH" if role else "LOW"
        return ch[0]["t_start"], ch[-1]["t_end"], meta

    with ThreadPoolExecutor(max_workers=8) as pool:
        per_chunk = [r for r in pool.map(_process, chunks) if r is not None]

    # Merge contiguous chunks with the same role.
    out: list[dict[str, Any]] = []
    for start, end, meta in per_chunk:
        if out and out[-1]["metadata"].get("role") == meta.get("role") and meta.get("role"):
            out[-1]["t_end"] = end
            # keep the first summary; alternatively concatenate
        else:
            out.append({"t_start": start, "t_end": end, "metadata": meta})
    return out
