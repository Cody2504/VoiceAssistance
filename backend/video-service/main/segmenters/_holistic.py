"""Holistic segmenter core — one LLM pass over the whole-video timeline.

Shared by the Segment Builder presets (topic_changes, editorial_segment,
shot_detection, ocr, person_of_focus, sports_highlights, write_my_own). Decides
segment boundaries semantically and fills all requested fields in one call,
mimicking TwelveLabs Pegasus. Falls back to each preset's legacy body on any
failure. See docs/superpowers/specs/2026-06-26-holistic-segmenter-design.md.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable
from uuid import UUID

from main.api.segments_types import SegmentDefinition, SegmentField
from main.settings import get_settings

from .qdrant_io import read_shots

log = logging.getLogger(__name__)


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


def _build_schema_prompt(definition: SegmentDefinition) -> str:
    parts = []
    for f in definition.fields:
        line = f'- "{f.name}" ({f.type or "string"})'
        if f.description:
            line += f": {f.description}"
        if f.enum:
            line += f" — allowed: {', '.join(f.enum)}"
        parts.append(line)
    return "\n".join(parts) if parts else "(no fields requested — emit an empty object per segment)"


def _build_timeline(shots: list[dict[str, Any]], primary_signal: str = "auto") -> str:
    order_map = {
        "ocr": ["ocr", "cap", "asr"],
        "asr": ["asr", "cap", "ocr"],
        "caption": ["cap", "asr", "ocr"],
    }
    order = order_map.get(primary_signal, ["cap", "asr", "ocr"])
    lines = []
    for sh in shots:
        vals = {
            "cap": ("cap", (sh.get("chunk_caption") or "").strip()),
            "asr": ("asr", (sh.get("asr_text") or "").strip()),
            "ocr": ("ocr", (sh.get("ocr_text") or "").strip()),
        }
        bits = [f"{label}={v}" for key in order for (label, v) in [vals[key]] if v]
        tags = ", ".join(
            t.get("label", "") for t in (sh.get("audio_tags") or [])[:3] if t.get("label")
        )
        if tags:
            bits.append(f"audio=[{tags}]")
        text = " | ".join(bits) or "(silent, no caption)"
        lines.append(f"[{sh['t_start']:.1f}-{sh['t_end']:.1f}s] {text}"[:400])
    return "\n".join(lines)


def _snap(t: float, cuts: list[float], tol: float) -> float:
    best = None
    for c in cuts:
        d = abs(c - t)
        if d <= tol and (best is None or d < abs(best - t)):
            best = c
    return best if best is not None else t


def _normalize_segments(
    raw_segments: list[dict[str, Any]],
    definition: SegmentDefinition,
    duration: float,
    shots: list[dict[str, Any]],
    snap_tol: float,
) -> list[dict[str, Any]]:
    cuts = sorted(
        {0.0, float(duration)}
        | {float(sh["t_start"]) for sh in shots}
        | {float(sh["t_end"]) for sh in shots}
    )
    items: list[dict[str, Any]] = []
    for seg in raw_segments:
        if not isinstance(seg, dict):
            continue
        try:
            ts = float(seg.get("start_time"))
            te = float(seg.get("end_time"))
        except (TypeError, ValueError):
            continue
        ts = max(0.0, min(ts, duration))
        te = max(0.0, min(te, duration))
        if te <= ts:
            continue
        items.append({"t_start": ts, "t_end": te, "metadata": _validate_metadata(seg, definition)})
    if not items:
        return []
    items.sort(key=lambda s: s["t_start"])
    for s in items:
        s["t_start"] = _snap(s["t_start"], cuts, snap_tol)
        s["t_end"] = _snap(s["t_end"], cuts, snap_tol)
    items[0]["t_start"] = 0.0
    items[-1]["t_end"] = float(duration)
    for a, b in zip(items, items[1:]):
        if a["t_end"] != b["t_start"]:
            mid = (a["t_end"] + b["t_start"]) / 2.0
            a["t_end"] = mid
            b["t_start"] = mid
    return [s for s in items if s["t_end"] > s["t_start"]]


def _chat_json(api_key: str, model: str, system: str, user: str) -> dict[str, Any] | None:
    """Single OpenRouter JSON call. Returns the parsed object or None on any
    failure (the orchestrator falls back). The only network seam — tests patch this."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=4000,
            temperature=0.1,
        )
        raw = (resp.choices[0].message.content or "").strip()
        lo, hi = raw.find("{"), raw.rfind("}")
        if lo == -1 or hi <= lo:
            return None
        return json.loads(raw[lo : hi + 1])
    except Exception as exc:  # noqa: BLE001
        log.warning("holistic:_chat_json failed: %s", exc)
        return None


_SYSTEM_TMPL = (
    "You segment a video into time-based metadata, like TwelveLabs Pegasus. You are given a "
    "chronological timeline (per-shot captions, speech, on-screen text) and a segmentation "
    "definition. Output a SMALL set of NON-OVERLAPPING segments that together COVER the whole "
    "video [0, {duration:.1f}] seconds. Start a NEW segment ONLY where {guidance} genuinely "
    "changes; MERGE consecutive shots about the same thing — never one segment per shot. For each "
    "segment output start_time and end_time in seconds and ALL requested fields, respecting enum "
    "constraints. {target_hint}. Reply with JSON only: "
    '{{"segments":[{{"start_time":<sec>,"end_time":<sec>, ...fields}}]}}.'
)


def holistic_segments(
    video_id: UUID,
    definition: SegmentDefinition,
    *,
    guidance: str,
    target_hint: str,
    primary_signal: str,
    default_fields: list[SegmentField],
    fallback: Callable[[UUID, SegmentDefinition], list[dict[str, Any]]],
    vision_fields: list[str] | None = None,
    vision_guidance: str = "",
) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    if not shots:
        return []

    s = get_settings()
    api_key = (s.openrouter_api_key or "").strip()
    if not api_key:
        return fallback(video_id, definition)

    eff_def = (
        definition if definition.fields else definition.model_copy(update={"fields": default_fields})
    )
    duration = float(shots[-1]["t_end"])
    timeline = _build_timeline(shots, primary_signal)
    schema = _build_schema_prompt(eff_def)

    system = _SYSTEM_TMPL.format(duration=duration, guidance=guidance, target_hint=target_hint)
    user = (
        f"Definition (id={definition.id}): {definition.description}\n"
        f"A new segment begins when: {guidance}\n"
        f"Video duration: {duration:.1f}s\n\n"
        f"Required fields per segment:\n{schema}\n\n"
        f"Timeline (one line per shot):\n{timeline[:16000]}"
    )

    # Defense-in-depth: the LLM call + normalization must never raise to the API.
    try:
        data = _chat_json(api_key, s.segment_holistic_model, system, user)
        if not data or not isinstance(data.get("segments"), list):
            return fallback(video_id, definition)
        segs = _normalize_segments(
            data["segments"], eff_def, duration, shots, s.segment_snap_tolerance_sec
        )
        if not segs:
            return fallback(video_id, definition)
        # Phase-2: overwrite visual fields from sampled frames (gated by flag).
        if vision_fields and s.segment_vision_refine:
            from ._vision_refine import vision_refine
            segs = vision_refine(
                video_id, eff_def, segs, vision_fields=vision_fields, guidance=vision_guidance
            )
        return segs
    except Exception as exc:  # noqa: BLE001
        log.warning("holistic_segments failed: %s — using fallback", exc)
        return fallback(video_id, definition)
