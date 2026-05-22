"""Cut 1 / Task 11.8 — write_my_own segmenter (a.k.a. "structured rollup").

Lets the user define an arbitrary `SegmentDefinition` and runs an LLM over
groups of consecutive shots' captions/ASR/ocr/audio_tags to fill the schema.

Algorithm
---------
1. Read all shots (no vectors needed — pure text rollup).
2. Pack shots into chunks of ≤ `CHUNK_SECONDS` (default 60s). The chunk
   boundary becomes the segment boundary, so the user's definition decides
   how granular the schema is.
3. For each chunk, build a textual context (per-shot captions + ASR +
   audio_tags) and ask an LLM to emit a JSON object whose keys match the
   user's `fields`. Enum fields → constrained to allowed values in the prompt.
4. Validate the response against the schema. Drop chunks that fail validation
   (logged); the rest become segments.

Parallelization: like `topic_changes`, chunk-level LLM calls run 8-wide
through a ThreadPoolExecutor. Per-call timeout via the OpenAI SDK.

This is the closest analog in our stack to TwelveLabs' Pegasus-driven
"Write My Own" — except we feed text instead of frames, because our visual
context for a shot is already a VLM-generated caption written at index time.
That keeps runtime cost predictable (no per-request VLM frame upload) at
the cost of one indirection between visual data and the rollup model.
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

CHUNK_SECONDS = 60.0
MAX_CHUNKS = 32  # hard cap so an hour-long video can't fan out to 60 calls


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


def _format_chunk_context(chunk: list[dict[str, Any]]) -> str:
    lines = []
    for sh in chunk:
        tags = ", ".join(
            t.get("label", "") for t in (sh.get("audio_tags") or [])[:3] if t.get("label")
        )
        text_bits = []
        if sh.get("chunk_caption"):
            text_bits.append(f"caption={sh['chunk_caption']}")
        if sh.get("asr_text"):
            text_bits.append(f"asr={sh['asr_text']}")
        if sh.get("ocr_text"):
            text_bits.append(f"ocr={sh['ocr_text']}")
        if tags:
            text_bits.append(f"audio=[{tags}]")
        text = " | ".join(text_bits) or "(silent, no caption)"
        lines.append(f"[shot {sh['idx']} {sh['t_start']:.1f}-{sh['t_end']:.1f}s] {text}")
    return "\n".join(lines)


def _build_schema_prompt(definition: SegmentDefinition) -> str:
    """Turn the user's field list into a short prompt fragment describing
    what JSON we want back."""
    parts = []
    for f in definition.fields:
        line = f'- "{f.name}" ({f.type or "string"})'
        if f.description:
            line += f": {f.description}"
        if f.enum:
            line += f" — allowed: {', '.join(f.enum)}"
        parts.append(line)
    return "\n".join(parts) if parts else "(no fields requested — emit an empty object)"


def _coerce_field(value: Any, type_name: str) -> Any:
    t = (type_name or "string").lower()
    if value is None:
        return None
    if t == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if t == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1"}
        return bool(value)
    return str(value)


def _validate_metadata(raw: dict[str, Any], definition: SegmentDefinition) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in definition.fields:
        v = _coerce_field(raw.get(f.name), f.type or "string")
        if f.enum and v is not None and v not in f.enum:
            v = None
        if v is not None:
            out[f.name] = v
    return out


def _call_llm(api_key: str, model: str, definition: SegmentDefinition, context: str) -> dict[str, Any] | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        schema_prompt = _build_schema_prompt(definition)
        user_prompt = (
            f"User-defined segment definition (id={definition.id}):\n"
            f"{definition.description}\n\n"
            f"Required JSON fields:\n{schema_prompt}\n\n"
            f"Shot context:\n{context}\n\n"
            "Reply with a single JSON object containing only the requested fields. "
            "If the chunk does not match the definition at all, reply with an empty object `{}`."
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract structured metadata from short windows of a video. "
                        "Always reply with valid JSON, no markdown fences, no commentary. "
                        "Respect the field list and enum constraints exactly."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=320,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("write_my_own:llm call failed: %s — skipping chunk", exc)
        return None


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    if not shots:
        return []

    chunks = _pack_chunks(shots, CHUNK_SECONDS)[:MAX_CHUNKS]
    if not chunks or not chunks[0]:
        return []

    s = get_settings()
    api_key = (s.openrouter_api_key or "").strip()
    model = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")

    if not api_key:
        # No API key → emit one segment per chunk with empty metadata. The
        # boundaries still let the UI render the track structure.
        return [
            {"t_start": ch[0]["t_start"], "t_end": ch[-1]["t_end"], "metadata": {}}
            for ch in chunks
        ]

    def _process(ch: list[dict[str, Any]]) -> dict[str, Any] | None:
        ctx = _format_chunk_context(ch)
        raw = _call_llm(api_key, model, definition, ctx) or {}
        metadata = _validate_metadata(raw, definition)
        # Empty metadata + no required-field hit → caller treats as "no match".
        if not metadata and definition.fields:
            return None
        return {
            "t_start": ch[0]["t_start"],
            "t_end": ch[-1]["t_end"],
            "metadata": metadata,
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_process, chunks))

    return [r for r in results if r is not None]
