"""Cut 1 / Task 11.6 — topic_changes segmenter.

Splits a video into topic/step segments. The PRIMARY signal is SEMANTIC: an LLM
reads the ordered per-shot captions + transcripts and marks where the activity /
step / subject changes — so fixed-camera procedural videos (cooking demos,
lectures, how-tos) split by step even when the picture barely changes. The
FALLBACK (no API key, no text, single shot, or LLM failure) is the original
VISUAL signal below: cosine on consecutive shot ViCLIP embeddings (768-d float,
CPU, no model load).

Algorithm
---------
1. Read shots in order with their visual vectors + captions + ASR.
2. Compute cosine(vec_i, vec_{i+1}) for adjacent shots.
3. A "topic change" lands between shot i and i+1 when the similarity drops
   below `TOPIC_SIM_THRESHOLD`. Robust to single-shot outliers because the
   subsequent shot starts a new group from i+1; if the next pair re-bonds
   visually that group will be short and the one after long.
4. Group contiguous shots into topic segments. Each segment's boundary is
   `(t_start of first shot, t_end of last shot)`.
5. (Optional) For each segment, if the user requested a `topic_summary`
   field, call OpenRouter for a one-line topic label built from joined
   captions + ASR. Falls back to a heuristic title (joined caption head)
   when the API key is absent.

The threshold and minimum-segment shot count are tunable; defaults picked
to avoid one-shot topics on shot-heavy montage footage.
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition
from main.settings import get_settings

from .qdrant_io import read_shots

log = logging.getLogger(__name__)

TOPIC_SIM_THRESHOLD = 0.78
MIN_SHOTS_PER_TOPIC = 1


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _heuristic_title(shots: list[dict[str, Any]]) -> str:
    """Cheap title when we can't call the LLM — first non-empty caption,
    truncated to a single line."""
    for sh in shots:
        cap = (sh.get("chunk_caption") or "").strip()
        if cap:
            head = cap.split(".")[0]
            return head[:80]
    for sh in shots:
        asr = (sh.get("asr_text") or "").strip()
        if asr:
            return asr.split(".")[0][:80]
    return f"Topic ({len(shots)} shots)"


def _llm_topic_title(joined_text: str, api_key: str) -> str | None:
    """One-line topic title via OpenRouter. Returns None on any failure so
    the caller can fall back to the heuristic. Best-effort, never raises.

    Model picked to match the repo standard (`qwen3-vl-8b-instruct`, also the
    captioner default). A "thinking" variant was tried first and ate the
    token budget producing empty content — avoid those for short outputs.
    """
    import os

    model = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate a single short noun-phrase title (≤8 words) "
                        "for a video segment based on per-shot captions and transcripts. "
                        "Output the title only, no quotes, no punctuation at the end."
                    ),
                },
                {"role": "user", "content": joined_text[:4000]},
            ],
            max_tokens=24,
            temperature=0.2,
        )
        msg = (resp.choices[0].message.content or "").strip()
        return msg or None
    except Exception as exc:  # noqa: BLE001
        log.warning("topic_changes:llm rollup failed: %s — using heuristic", exc)
        return None


def _segment_from_shots(
    shots_in_topic: list[dict[str, Any]],
    want_summary: bool,
    want_topic: bool,
    api_key: str,
) -> dict[str, Any]:
    t_start = shots_in_topic[0]["t_start"]
    t_end = shots_in_topic[-1]["t_end"]
    metadata: dict[str, Any] = {
        "shot_count": len(shots_in_topic),
        "shot_range": [shots_in_topic[0]["idx"], shots_in_topic[-1]["idx"]],
    }
    # Both legacy `topic_summary` and Twelve Labs `topic` get the same LLM
    # rollup. `subtopics` / `key_points` would need richer LLM context per
    # group; `transition_type` (hard_cut/gradual/host_introduction/natural_flow)
    # would need adjacent-shot analysis. Both left for a future enrichment pass.
    if want_summary or want_topic:
        joined = "\n".join(
            f"[{sh['idx']}] {(sh.get('chunk_caption') or sh.get('asr_text') or '').strip()}"
            for sh in shots_in_topic
            if (sh.get("chunk_caption") or sh.get("asr_text"))
        )
        title = None
        if api_key and joined:
            title = _llm_topic_title(joined, api_key)
        title = title or _heuristic_title(shots_in_topic)
        if want_summary:
            metadata["topic_summary"] = title
        if want_topic:
            metadata["topic"] = title
    return {"t_start": t_start, "t_end": t_end, "metadata": metadata}


def _visual_groups(shots: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Fallback grouping: split where adjacent ViCLIP cosine drops below the
    threshold (the original visual-only behavior). Used when there is no LLM
    available / no text to read."""
    groups: list[list[dict[str, Any]]] = [[shots[0]]]
    for prev, curr in zip(shots, shots[1:]):
        sim = _cosine(prev.get("vector") or [], curr.get("vector") or [])
        if sim < TOPIC_SIM_THRESHOLD:
            groups.append([curr])
        else:
            groups[-1].append(curr)
    if MIN_SHOTS_PER_TOPIC > 1:
        merged: list[list[dict[str, Any]]] = []
        for g in groups:
            if merged and len(g) < MIN_SHOTS_PER_TOPIC:
                merged[-1].extend(g)
            else:
                merged.append(g)
        groups = merged
    return groups


def _groups_from_boundaries(
    shots: list[dict[str, Any]], starts: list[int]
) -> list[list[dict[str, Any]]]:
    """Build contiguous shot groups from a sorted list of group-START indices."""
    groups: list[list[dict[str, Any]]] = []
    for gi, start in enumerate(starts):
        end = starts[gi + 1] if gi + 1 < len(starts) else len(shots)
        chunk = shots[start:end]
        if chunk:
            groups.append(chunk)
    return groups


def _semantic_boundaries(shots: list[dict[str, Any]], api_key: str) -> list[int] | None:
    """Ask the LLM where topics/steps change based on per-shot captions + ASR.

    Returns sorted group-START indices (always beginning with 0), or None on any
    failure / empty text so the caller falls back to visual-similarity. This is
    the signal that splits FIXED-CAMERA procedural videos (e.g. a cooking demo:
    rice prep -> rolling -> cutting -> serving) that visual similarity can't see
    because the picture barely changes between steps.
    """
    import json
    import os

    lines: list[str] = []
    for i, sh in enumerate(shots):
        cap = (sh.get("chunk_caption") or "").strip()
        asr = (sh.get("asr_text") or "").strip()
        piece = cap
        if asr:
            piece = f"{cap} | transcript: {asr}" if cap else f"transcript: {asr}"
        lines.append(f"{i}: {piece[:300]}")
    joined = "\n".join(line for line in lines if line.split(": ", 1)[-1].strip())
    if not joined.strip():
        return None

    model = os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You split a video into topics/steps from per-shot captions and "
                        "transcripts. A NEW topic begins when the activity, step, or subject "
                        "changes -- EVEN IF the scene/camera looks identical (e.g. a cooking "
                        "demo: rice prep, rolling, cutting and serving are distinct steps). "
                        "Group consecutive shots of the same step together; do not over-split. "
                        "Return ONLY a JSON array of the shot indices where a new topic begins, "
                        "always including 0, strictly increasing and within range."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{len(shots)} shots (index: caption | transcript):\n{joined[:6000]}\n\n"
                        "Boundary indices as a JSON array, e.g. [0, 3, 7]."
                    ),
                },
            ],
            max_tokens=120,
            temperature=0.1,
        )
        raw = (resp.choices[0].message.content or "").strip()
        lo, hi = raw.find("["), raw.rfind("]")
        if lo == -1 or hi <= lo:
            return None
        arr = json.loads(raw[lo : hi + 1])
        idxs = sorted(
            {int(x) for x in arr if isinstance(x, (int, float)) and 0 <= int(x) < len(shots)}
        )
        if 0 not in idxs:
            idxs = [0, *idxs]
        return idxs or None
    except Exception as exc:  # noqa: BLE001
        log.warning("topic_changes:semantic split failed: %s -- using visual fallback", exc)
        return None


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=True)
    if not shots:
        return []

    field_names = {f.name for f in definition.fields}
    want_summary = "topic_summary" in field_names
    want_topic = "topic" in field_names

    s = get_settings()
    api_key = (s.openrouter_api_key or "").strip()

    # PRIMARY: semantic boundaries from captions/ASR — splits procedural /
    # fixed-camera videos by STEP even when the visuals barely change (a cooking
    # demo, a lecture, a how-to). Falls back to visual-similarity grouping when
    # there's no API key, no text, a single shot, or the LLM call fails.
    groups: list[list[dict[str, Any]]] | None = None
    if api_key and len(shots) > 1:
        bounds = _semantic_boundaries(shots, api_key)
        if bounds:
            groups = _groups_from_boundaries(shots, bounds)
    if not groups:
        groups = _visual_groups(shots)
    needs_llm = (want_summary or want_topic) and api_key
    if not needs_llm or len(groups) == 0:
        return [_segment_from_shots(g, want_summary, want_topic, api_key) for g in groups]
    # LLM rollups parallelized — one OpenRouter call per group, up to 8 in
    # flight. Single-threaded loop was the bottleneck on shot-heavy footage
    # (each call ~3-10s; 20+ groups → 60-200s sequential vs ~8-20s parallel).
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(
            pool.map(lambda g: _segment_from_shots(g, want_summary, want_topic, api_key), groups)
        )
