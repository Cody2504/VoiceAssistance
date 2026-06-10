from __future__ import annotations

import logging

from main.pipeline.timeline.types import GeneratedTrack, TimelineEvent, merge_consecutive
from main.pipeline.highlights_v2 import run_highlights_v2

log = logging.getLogger(__name__)


def gen_audio_events(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    """One event per run of segments whose top PANN tag is the same and scores
    above threshold (cheering/whistle/applause/etc. are surfaced as-is)."""
    min_score = settings.timeline_audio_event_min_score
    spans: list[tuple[float, float, str, float]] = []
    for (t0, t1), tags in zip(artifacts.segments, artifacts.audio_tags_per_segment):
        if not tags:
            continue
        top = tags[0]  # tag_audio_segment returns desc-sorted [{label, score}]
        label, score = top.get("label", ""), float(top.get("score", 0.0))
        if not label or score < min_score:
            continue
        spans.append((float(t0), float(t1), label, score))
    events = merge_consecutive(spans, source="audio_events")
    return GeneratedTrack(kind="audio_events", label="Audio events", events=events)


def gen_on_screen_text(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    spans: list[tuple[float, float, str, float]] = []
    for (t0, t1), txt in zip(artifacts.segments, artifacts.ocr_texts):
        t = (txt or "").strip()
        if not t:
            continue
        spans.append((float(t0), float(t1), t[:200], 1.0))
    events = merge_consecutive(spans, source="on_screen_text")
    for e in events:
        e.metadata = {"text": e.label}
    return GeneratedTrack(kind="on_screen_text", label="On-screen text", events=events)


def gen_shots(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    """One event per segment (the 30 s grid is already shot-aligned at ingest)."""
    events = [
        TimelineEvent(t_start=float(t0), t_end=float(t1), label=f"Scene {i + 1}",
                      source="shots", score=1.0)
        for i, (t0, t1) in enumerate(artifacts.segments)
    ]
    return GeneratedTrack(kind="shots", label="Scenes", events=events)


def gen_spoken_topics(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    """One event per 2-min window that has both a summary and spoken content."""
    if summary is None or not getattr(summary, "windows", None):
        return GeneratedTrack(kind="spoken_topics", label="Spoken topics", events=[])
    window_size = settings.summary_window_size_sec
    # window_idx -> (min t_start, max t_end, has_transcript)
    bounds: dict[int, list] = {}
    for (t0, t1), tr in zip(artifacts.segments, artifacts.transcripts):
        w = int(float(t0) // window_size)
        b = bounds.setdefault(w, [float(t0), float(t1), False])
        b[0] = min(b[0], float(t0))
        b[1] = max(b[1], float(t1))
        if (tr or "").strip():
            b[2] = True
    events: list[TimelineEvent] = []
    for w in summary.windows:
        b = bounds.get(w.idx)
        summ = (w.summary or "").strip()
        if not b or not b[2] or not summ:
            continue
        events.append(TimelineEvent(
            t_start=b[0], t_end=b[1], label=summ[:200], source="spoken_topics",
            score=1.0, metadata={"topic": summ, "window_idx": w.idx},
        ))
    events.sort(key=lambda e: e.t_start)
    return GeneratedTrack(kind="spoken_topics", label="Spoken topics", events=events)


def gen_highlights(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    """DETR/SG-DETR saliency highlights as a track. Reuses run_highlights_v2,
    which loads the cached feature .npy and runs the trained head. Best-effort:
    on any failure the track is empty (never blocks the rest of the timeline)."""
    events: list[TimelineEvent] = []
    try:
        res = run_highlights_v2(
            str(video_id),
            artifacts.duration_s,
            modality=artifacts.modality,
            top_k=settings.timeline_highlights_top_k,
        )
        for i, m in enumerate(res.moments):
            events.append(TimelineEvent(
                t_start=float(m["t_start"]), t_end=float(m["t_end"]),
                label=f"Highlight {i + 1}", source="highlights",
                score=float(m.get("score", 0.0)), metadata={"saliency": float(m.get("score", 0.0))},
            ))
    except Exception as exc:  # noqa: BLE001
        log.warning("timeline:highlights generator failed for video=%s: %s", video_id, exc)
    return GeneratedTrack(kind="highlights", label="Highlights", events=events)


def _speaker_snippet(turn: dict, segments, transcripts, max_len: int = 120) -> str:
    """Transcript text of the 30 s segments overlapping a speaker turn — what
    makes a speaker event semantically searchable (not just "Speaker 1")."""
    parts: list[str] = []
    for (t0, t1), tr in zip(segments, transcripts):
        if float(t0) < turn["t_end"] and float(t1) > turn["t_start"] and (tr or "").strip():
            parts.append(tr.strip())
    return " ".join(parts)[:max_len]


def gen_speakers(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    """pyannote speaker turns (research F) as a timeline track. Reads the eager
    ingest-time `artifacts.speaker_turns`; empty track when disabled. Speakers
    are numbered in order of first appearance."""
    turns = sorted(
        (t for t in (getattr(artifacts, "speaker_turns", None) or [])
         if t.get("speaker") and t.get("t_start") is not None),
        key=lambda t: float(t["t_start"]),
    )
    names: dict[str, int] = {}
    events: list[TimelineEvent] = []
    for t in turns:
        spk = str(t["speaker"])
        n = names.setdefault(spk, len(names) + 1)
        snippet = _speaker_snippet(t, artifacts.segments, artifacts.transcripts)
        label = f"Speaker {n}: {snippet}" if snippet else f"Speaker {n}"
        events.append(TimelineEvent(
            t_start=float(t["t_start"]), t_end=float(t["t_end"]), label=label[:200],
            source="speakers", score=1.0, metadata={"speaker": spk},
        ))
    return GeneratedTrack(kind="speakers", label="Speakers", events=events)


def gen_vlm_actions(video_id, artifacts, summary, *, settings) -> GeneratedTrack | None:
    """VLM timestamped action captions (roadmap #3) as a timeline track. Reads
    the eager ingest-time `artifacts.shot_actions`; empty track when disabled."""
    actions = getattr(artifacts, "shot_actions", None) or []
    events = [
        TimelineEvent(
            t_start=float(a["t_start"]),
            t_end=float(a["t_end"]),
            label=str(a["action"])[:200],
            source="vlm_actions",
            score=1.0,
            metadata={"action": str(a["action"])},
        )
        for a in actions
        if a.get("action") and a.get("t_start") is not None
    ]
    events.sort(key=lambda e: e.t_start)
    return GeneratedTrack(kind="vlm_actions", label="Actions", events=events)
