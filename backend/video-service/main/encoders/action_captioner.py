"""
Action re-captioner — timestamped in-shot ACTION captions via the same
OpenRouter Qwen3-VL endpoint the agent VQA / VLMCaptioner already use.

Unlike VLMCaptioner (one appearance sentence per 30 s segment), this asks the
VLM for the *actions/events* inside a clip and *when* (seconds from the clip
start) each happens, returned as a JSON array. The pipeline maps those to
absolute video time and indexes them as the `vlm_actions` timeline track —
the short-action-precision path ("when is the tomato added").

Public API:
    cap = ActionCaptioner.from_config(config)
    if cap.is_available():
        events = cap.caption_actions(frames, clip_start=30.0, clip_dur=30.0,
                                     span_sec=2.0)
        # -> [{"t_start": 44.0, "t_end": 46.0, "action": "adds tomato to pan"}]
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from typing import List, Optional

import numpy as np

from main.encoders.video_qa import _frames_to_base64_images

log = logging.getLogger(__name__)

_UNAVAILABLE = "unavailable"
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _is_rate_limit(exc: Exception) -> bool:
    """True for an OpenRouter/OpenAI rate-limit (429) or transient overload, so
    the caller backs off + retries instead of dropping the segment. Matches on
    status_code when present and on common message substrings otherwise."""
    if getattr(exc, "status_code", None) == 429 or getattr(exc, "code", None) == 429:
        return True
    m = str(exc).lower()
    return "429" in m or "rate limit" in m or "rate_limit" in m or "too many requests" in m or "overloaded" in m


def _build_action_prompt(clip_dur: float) -> str:
    return (
        f"You are watching a short video clip about {clip_dur:.0f} seconds long. "
        "List the distinct visible ACTIONS or EVENTS that occur, in order. For "
        "each, give the time in SECONDS from the START of THIS clip when it "
        "happens.\n"
        'Respond with ONLY a JSON array, for example: '
        '[{"t": 3.0, "action": "a person picks up a tomato"}, '
        '{"t": 14.0, "action": "the tomato is added to the pan"}].\n'
        "Use short, factual action phrases. No prose, no markdown — JSON only."
    )


def _parse_actions(raw: str, clip_start: float, clip_dur: float, span_sec: float) -> list[dict]:
    """Extract the first JSON array from `raw`, then map each {t, action} item to
    absolute video time. Clamps t to [0, clip_dur] and t_end to the clip end;
    skips items with no action text or an unparseable t. Never raises."""
    if not raw:
        return []
    m = _JSON_ARRAY_RE.search(raw)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except (ValueError, TypeError):
        return []
    if not isinstance(arr, list):
        return []
    out: list[dict] = []
    clip_end = clip_start + clip_dur
    for item in arr:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).strip()
        if not action:
            continue
        try:
            t = float(item.get("t"))
        except (TypeError, ValueError):
            continue
        t = max(0.0, min(t, clip_dur))
        t_start = clip_start + t
        t_end = min(clip_end, t_start + span_sec)
        out.append({
            "t_start": round(t_start, 2),
            "t_end": round(t_end, 2),
            "action": action[:200],
        })
    # Dedup repeated action phrases within this clip — the VLM sometimes emits the
    # same action many times (often all stamped at the clip start). Keep the
    # earliest occurrence per normalized phrase; return ordered by time.
    deduped: dict[str, dict] = {}
    for item in out:
        key = " ".join(item["action"].lower().split())
        if key not in deduped or item["t_start"] < deduped[key]["t_start"]:
            deduped[key] = item
    return sorted(deduped.values(), key=lambda x: x["t_start"])


class ActionCaptioner:
    """Timestamped action captioner over the OpenRouter Qwen3-VL endpoint."""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        max_frames: int = 32,
        max_tokens: int = 256,
        max_retries: int = 4,
        retry_base_s: float = 2.0,
    ):
        self.api_key = api_key
        self.model = model or os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")
        self.base_url = base_url
        self.max_frames = max_frames
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_base_s = retry_base_s
        self._client = None

    @classmethod
    def from_config(cls, config) -> "ActionCaptioner":
        return cls(
            api_key=config.openrouter_api_key,
            model=config.vlm_model,
            base_url=config.openrouter_base_url,
        )

    def _lazy_load(self) -> None:
        if self._client is not None:
            return
        if not self.api_key:
            self._client = _UNAVAILABLE
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            log.info("ActionCaptioner ready (model=%s)", self.model)
        except Exception as exc:  # noqa: BLE001
            log.warning("ActionCaptioner unavailable: %s", exc)
            self._client = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._client not in (None, _UNAVAILABLE)

    def caption_actions(self, frames: np.ndarray, *, clip_start: float, clip_dur: float,
                        span_sec: float = 2.0) -> list[dict]:
        """Send sampled frames to the VLM and parse a JSON array of timestamped
        actions into absolute-time events. Best-effort: returns [] on any failure."""
        self._lazy_load()
        if self._client in (None, _UNAVAILABLE):
            return []
        images = _frames_to_base64_images(frames, max_images=self.max_frames)
        if not images:
            return []
        content: list[dict] = [{"type": "text", "text": _build_action_prompt(clip_dur)}]
        for b64 in images:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        # Retry on 429 / transient overload with exponential backoff + jitter so
        # the parallel per-segment calls don't drop segments when OpenRouter rate-
        # limits a burst. Non-rate-limit errors fail fast (return []).
        raw = ""
        for attempt in range(self.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=self.max_tokens,
                    temperature=0.0,
                )
                raw = resp.choices[0].message.content or ""
                break
            except Exception as exc:  # noqa: BLE001
                if _is_rate_limit(exc) and attempt < self.max_retries - 1:
                    delay = self.retry_base_s * (2 ** attempt) + random.uniform(0, self.retry_base_s)
                    log.warning("ActionCaptioner: rate-limited, backing off %.1fs (attempt %d/%d)",
                                delay, attempt + 1, self.max_retries)
                    time.sleep(delay)
                    continue
                log.warning("ActionCaptioner: VLM call failed: %s", exc)
                return []
        return _parse_actions(raw, clip_start, clip_dur, span_sec)
