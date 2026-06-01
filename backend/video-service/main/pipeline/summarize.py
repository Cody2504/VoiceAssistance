"""Hierarchical summarization for the Analyze tile's long-context Q&A path.

Builds three layers from the per-segment data the ingest pipeline already
produces (caption + transcript + audio tags):

  1. segment_summary  — per 30-second segment, one sentence. Deterministic
                        stitch of caption + transcript; no LLM call.
  2. window_summary   — per 2-minute window (~4 segments), 2-3 sentences.
                        One LLM call per window. Sized so the full ordered
                        list of windows for a 2hr video fits in ~3K tokens
                        and can always be included in the Analyze prompt.
  3. global_summary   — one paragraph covering the whole video. One LLM call
                        over the concatenated window summaries.

Window summaries live in Qdrant point payloads keyed by (video_id, window_idx).
Global summary lives in `videos.global_summary`. Segment summaries live as the
``segment_summary`` field on each Qdrant point.

The Analyze pipeline assembles its LLM prompt by reading exactly these three
layers, so any change to the prompt shape should start here.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Sequence

from main.settings import Settings, get_settings

log = logging.getLogger(__name__)


@dataclass
class SegmentRecord:
    """Subset of per-segment data needed to summarize. The ingest pipeline
    builds these in-memory before handing them to the summarizer; nothing
    here gets persisted as-is — we serialize the summaries onto Qdrant."""

    idx: int
    t_start: float
    t_end: float
    caption: str = ""
    transcript: str = ""
    audio_tags: list[dict] = field(default_factory=list)

    def to_segment_summary(self) -> str:
        """Deterministic stitch — no LLM. Captures everything the per-segment
        retrieval needs without paying per-segment LLM cost (would be 60+
        calls for a 30-min video, 240+ for a 2hr video)."""
        parts: list[str] = []
        if self.caption.strip():
            parts.append(self.caption.strip())
        if self.transcript.strip():
            parts.append(f"Said: {self.transcript.strip()}")
        if self.audio_tags:
            top = [t.get("label") for t in self.audio_tags[:3] if t.get("label")]
            if top:
                parts.append(f"Audio: {', '.join(top)}")
        return " | ".join(parts) if parts else "(silent / no detected content)"


@dataclass
class WindowSummary:
    idx: int
    t_start: float
    t_end: float
    segment_indices: list[int]
    summary: str


@dataclass
class HierarchicalSummary:
    """Output of HierarchicalSummarizer.run — caller persists to Qdrant + DB."""
    segment_summaries: dict[int, str]
    windows: list[WindowSummary]
    global_summary: str


class HierarchicalSummarizer:
    """LLM-driven 2-tier summary on top of the deterministic per-segment stitch.

    Heavy import (openai client) deferred to the call site so the module can
    be imported safely without an API key (the test suite runs without one).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(self, segments: Sequence[SegmentRecord], video_title: str = "") -> HierarchicalSummary:
        """Produce all three summary layers in one shot.

        Returns the full structured payload; the caller is responsible for
        writing it into Qdrant point payloads (per window) and the
        `videos.global_summary` column.
        """
        if not segments:
            return HierarchicalSummary({}, [], "")

        seg_summaries = {s.idx: s.to_segment_summary() for s in segments}

        windows = self._group_into_windows(segments)
        log.info("summarize:windows=%d segments=%d", len(windows), len(segments))

        client = self._llm_client()
        window_summaries: list[WindowSummary] = []
        for w in windows:
            text = self._summarize_window(client, w, seg_summaries, video_title)
            window_summaries.append(
                WindowSummary(
                    idx=w["idx"],
                    t_start=w["t_start"],
                    t_end=w["t_end"],
                    segment_indices=w["segment_indices"],
                    summary=text,
                )
            )

        global_summary = self._summarize_global(client, window_summaries, video_title)
        return HierarchicalSummary(
            segment_summaries=seg_summaries,
            windows=window_summaries,
            global_summary=global_summary,
        )

    # ---------------------------------------------------------------- helpers

    def _group_into_windows(self, segments: Sequence[SegmentRecord]) -> list[dict]:
        """Bin segments into fixed-size windows by their start time. We don't
        align to shot cuts here — the window grid is purely for the LLM's
        sense of "what happened in this part of the video"."""
        size = self.settings.summary_window_size_sec
        max_segs = self.settings.summary_max_segments_per_window
        if not segments:
            return []
        windows: dict[int, dict] = {}
        for seg in segments:
            w_idx = int(math.floor(seg.t_start / size))
            w = windows.setdefault(
                w_idx,
                {
                    "idx": w_idx,
                    "t_start": w_idx * size,
                    "t_end": (w_idx + 1) * size,
                    "segment_indices": [],
                },
            )
            if len(w["segment_indices"]) < max_segs:
                w["segment_indices"].append(seg.idx)
        ordered = [windows[k] for k in sorted(windows)]
        # Snap last window's t_end to the video's actual end.
        if ordered:
            ordered[-1]["t_end"] = max(s.t_end for s in segments)
        return ordered

    def _summarize_window(
        self,
        client,
        window: dict,
        seg_summaries: dict[int, str],
        video_title: str,
    ) -> str:
        bullets = "\n".join(
            f"- segment {i}: {seg_summaries.get(i, '')}"
            for i in window["segment_indices"]
        )
        prompt = (
            f"You are summarizing a 2-minute window of a video"
            f"{f' titled “{video_title}”' if video_title else ''}.\n"
            f"The window covers {_fmt_time(window['t_start'])}–{_fmt_time(window['t_end'])}.\n\n"
            f"Per-segment notes (caption + spoken transcript + audio tags):\n{bullets}\n\n"
            "Write 2–3 sentences capturing what happens in this window — content, "
            "topic, speakers, key visual events, and any notable audio. Be concrete; "
            "no preamble like 'In this window'. ≤ 60 words."
        )
        return self._llm_complete(client, prompt, max_tokens=120)

    def _summarize_global(
        self, client, windows: list[WindowSummary], video_title: str
    ) -> str:
        skeleton = "\n".join(
            f"- {_fmt_time(w.t_start)}–{_fmt_time(w.t_end)}: {w.summary}"
            for w in windows
        )
        prompt = (
            f"You are writing a single paragraph summarizing a full video"
            f"{f' titled “{video_title}”' if video_title else ''}.\n\n"
            f"Window-by-window notes:\n{skeleton}\n\n"
            "Write one paragraph (≤ 150 words) describing what the video is "
            "about overall: subject, structure (intro / main / conclusion if "
            "applicable), and the key points or events. Use neutral, factual "
            "phrasing. Don't list every window; synthesize."
        )
        return self._llm_complete(client, prompt, max_tokens=300)

    # ----------------------------------------------------------- LLM wiring

    def _llm_client(self):
        from openai import OpenAI
        return OpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )

    def _llm_complete(self, client, prompt: str, max_tokens: int) -> str:
        try:
            resp = client.chat.completions.create(
                model=self.settings.summary_llm_model,
                messages=[
                    {"role": "system", "content": "You write concise factual video summaries."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            # Don't crash ingest on summary failure — degrade gracefully so
            # the rest of the per-segment data still becomes queryable.
            log.warning("summarize:llm call failed: %s", exc)
            return ""


def _fmt_time(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60:02d}:{s % 60:02d}"
