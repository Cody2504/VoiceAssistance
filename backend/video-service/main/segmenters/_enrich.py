"""Shared LLM enrichment step for segmenter outputs.

Each registered segmenter computes BOUNDARIES (its specialty — pyannote
speaker turns, ViCLIP cosine drops, PANN audio-tag groupings, scene cuts,
…). After boundaries, this helper fills the *user's* `definition.fields`
schema by prompting an LLM with the cached shot context within each
segment window. Enum constraints and `description` hints from the schema
are passed verbatim so the model returns properly-typed, schema-conforming
JSON.

This is what `write_my_own.py` does for arbitrary user-authored
definitions; the shared helper here lets every other segmenter produce
the same level of metadata fidelity (Twelve Labs default-builder parity)
without duplicating the LLM prompting code.

Cost: one OpenRouter call per segment, up to 8 in flight in parallel. If
`OPENROUTER_API_KEY` is empty, the helper is a no-op and segments pass
through unchanged.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from main.api.segments_types import SegmentDefinition, SegmentField
from main.settings import get_settings

log = logging.getLogger(__name__)


def _shots_in_window(
    shots: list[dict[str, Any]], t_start: float, t_end: float
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sh in shots:
        ts = float(sh.get("t_start", 0.0))
        te = float(sh.get("t_end", 0.0))
        if te <= t_start or ts >= t_end:
            continue
        out.append(sh)
    return out


def _format_context(shots: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for sh in shots:
        tags = ", ".join(
            t.get("label", "") for t in (sh.get("audio_tags") or [])[:3] if t.get("label")
        )
        bits: list[str] = []
        if sh.get("chunk_caption"):
            bits.append(f"caption={sh['chunk_caption']}")
        if sh.get("asr_text"):
            bits.append(f"asr={sh['asr_text']}")
        if sh.get("ocr_text"):
            bits.append(f"ocr={sh['ocr_text']}")
        if tags:
            bits.append(f"audio=[{tags}]")
        body = " | ".join(bits) or "(silent, no caption)"
        lines.append(
            f"[shot {sh.get('idx', '?')} {float(sh.get('t_start', 0)):.1f}-"
            f"{float(sh.get('t_end', 0)):.1f}s] {body}"
        )
    return "\n".join(lines)


def _schema_prompt(fields: list[SegmentField], already_filled: dict[str, Any]) -> str:
    parts: list[str] = []
    for f in fields:
        if f.name in already_filled and already_filled[f.name] not in (None, "", []):
            continue
        line = f'- "{f.name}" ({f.type or "string"})'
        if f.description:
            line += f": {f.description}"
        if f.enum:
            line += f" — allowed: {', '.join(f.enum)}"
        parts.append(line)
    return "\n".join(parts)


def _coerce(value: Any, type_name: str) -> Any:
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


def _validate(
    raw: dict[str, Any], fields: list[SegmentField], already_filled: dict[str, Any]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        if f.name in already_filled and already_filled[f.name] not in (None, "", []):
            continue
        v = _coerce(raw.get(f.name), f.type or "string")
        if f.enum and v is not None and v not in f.enum:
            # Try case-insensitive match against the enum before discarding.
            lc = str(v).lower()
            v = next((e for e in f.enum if str(e).lower() == lc), None)
        if v is None or v == "":
            continue
        out[f.name] = v
    return out


def _call_llm(
    api_key: str,
    model: str,
    definition: SegmentDefinition,
    schema_prompt: str,
    context: str,
) -> dict[str, Any] | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        user_prompt = (
            f"Segment definition (id={definition.id}):\n"
            f"{definition.description}\n\n"
            f"Fields to fill (omit any you cannot confidently fill from context):\n"
            f"{schema_prompt}\n\n"
            f"Shot context for this segment:\n{context}\n\n"
            "Reply with a single JSON object whose keys exactly match the field names above. "
            "Respect enum constraints. For boolean fields, return true/false (not strings). "
            "If a field cannot be determined from context, omit it from the JSON."
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract structured metadata from a window of a video. "
                        "Reply with valid JSON only — no markdown fences, no commentary."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        log.warning("enrich:llm call failed: %s", exc)
        return None


def enrich_segments(
    segments: list[dict[str, Any]],
    definition: SegmentDefinition,
    shots: list[dict[str, Any]],
    *,
    max_concurrent: int = 8,
) -> list[dict[str, Any]]:
    """Fill missing `definition.fields` in each segment via parallel LLM calls.

    Mutates and returns `segments`. Segments where every requested field is
    already populated by the boundary-computing segmenter are skipped (no LLM
    call). If `OPENROUTER_API_KEY` is empty, returns segments unchanged.
    """
    if not segments or not definition.fields:
        return segments

    s = get_settings()
    api_key = (s.openrouter_api_key or "").strip()
    if not api_key:
        return segments

    model = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")

    def _process(seg: dict[str, Any]) -> dict[str, Any]:
        existing = dict(seg.get("metadata") or {})
        schema_prompt = _schema_prompt(definition.fields, existing)
        if not schema_prompt:
            return seg  # all fields already filled
        shots_in = _shots_in_window(shots, float(seg["t_start"]), float(seg["t_end"]))
        ctx = _format_context(shots_in) if shots_in else "(no cached shots in this window)"
        raw = _call_llm(api_key, model, definition, schema_prompt, ctx) or {}
        filled = _validate(raw, definition.fields, existing)
        if filled:
            seg["metadata"] = {**existing, **filled}
        return seg

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        return list(pool.map(_process, segments))
