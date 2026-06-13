"""Async indexing job — long-context MR/HD pipeline.

Flow (always, per upload):

  1. ``ffprobe`` modality detection — picks the right branch below.
  2. Visual branch (modality=video_audio or video_only):
       a) Shot detect → 30-second segment grid aligned to scene cuts.
       b) Per-segment: CLIP-L visual, Whisper ASR (skipped if no audio), OCR,
          PANN events (skipped if no audio), NSFW, VLM caption.
       c) Whole-file CLIP+SlowFast features via Lighthouse — cached to MinIO
          at ``features/{video_id}/lighthouse/clip_slowfast.npy``.
  3. Audio branch (modality=audio_only OR has_audio=True):
       a) 30-second time grid (no shot detect — there are no frames).
       b) Per-segment: Whisper ASR, PANN events, LLM caption-from-transcript.
       c) Whole-file CLAP features via Lighthouse — cached at
          ``features/{video_id}/lighthouse/clap.npy``.
  4. HierarchicalSummarizer: per-segment stitch (deterministic) + per-window
     LLM summaries + global LLM summary. Written into Qdrant payloads + the
     ``videos.global_summary`` DB column.
  5. Qdrant upsert: one point per segment with the extended payload schema
     (caption, transcript, audio_tags, segment_summary, window_summary,
     window_idx, modality).
  6. Per-video thumbnail strip (visual only) + metadata embedding for the
     Recommend tile (visual only).

Each encoder is wrapped in a best-effort try/except so a missing optional model
(e.g. msclap on a CPU-only setup) degrades gracefully — the video still becomes
searchable on whichever features succeeded.
"""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, NAMESPACE_OID, uuid5

import numpy as np

from main.settings import get_settings
from main.storage.minio import download_to_path, s3

log = logging.getLogger(__name__)

# Per-segment grid size (seconds). The summarizer's per-window grouping is
# layered on top of this — a 2-min window = 4 segments.
SEGMENT_LEN_SEC = 30.0


def _torch_device() -> str:
    """Pick CUDA when the worker has a visible GPU, else CPU.

    Called once per encoder fan-out. Avoids the previous mistake of pinning
    the moderation/OCR/audio-event classifiers to CPU on a GPU box — that
    cost ~25s per video in extra inference time (see migration log
    2026-05-23 problem 17).
    """
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@dataclass
class IngestArtifacts:
    """Everything the pipeline produces in-memory before persistence."""
    modality: str
    duration_s: float
    has_video: bool
    has_audio: bool
    segments: list[tuple[float, float]]
    visual_embeddings: np.ndarray | None
    caption_embeddings: np.ndarray | None
    captions: list[str]
    transcripts: list[str]
    ocr_texts: list[str]
    audio_tags_per_segment: list[list[dict]]
    nsfw_scores: list[float]
    toxic_scores: list[float]
    lighthouse_visual_path: str | None
    lighthouse_audio_path: str | None
    shot_actions: list[dict] | None = None  # VLM timestamped actions (roadmap #3); None when disabled
    audio_event_embeddings: "np.ndarray | None" = None  # CLAP per-segment (roadmap #2); None when disabled
    crop_embeddings: "list | None" = None  # (shot_idx, region, vec) image crops (roadmap #6); None when disabled
    speaker_turns: list[dict] | None = None  # pyannote turns (research F); None when disabled
    motion_embeddings: "np.ndarray | None" = None  # ViCLIP per-segment (research A); None when disabled


def run_indexing(
    video_id: UUID,
    minio_key: str,
    user_id: UUID | None = None,
    original_filename: str = "",
) -> dict[str, Any]:
    """End-to-end indexing for one upload. Returns a summary dict."""
    s = get_settings()
    log.info("ingest:start video_id=%s key=%s", video_id, minio_key)
    start = time.time()

    scratch = tempfile.mkdtemp(prefix="jockey-ingest-")
    local_path = os.path.join(scratch, "input.bin")
    download_to_path(s.minio_bucket_videos, minio_key, local_path)

    # --- 1. Modality detection ---
    from main.pipeline.modality import detect_modality
    mod = detect_modality(local_path)

    # --- 2. Visual vs audio-only branch ---
    if mod.has_video:
        artifacts = _ingest_with_video(local_path, video_id, mod, scratch)
    else:
        artifacts = _ingest_audio_only(local_path, video_id, mod, scratch)

    # --- 3. Hierarchical summarization ---
    from main.pipeline.summarize import HierarchicalSummarizer, SegmentRecord
    seg_records = [
        SegmentRecord(
            idx=i,
            t_start=float(t0),
            t_end=float(t1),
            caption=artifacts.captions[i],
            transcript=artifacts.transcripts[i],
            audio_tags=artifacts.audio_tags_per_segment[i],
        )
        for i, (t0, t1) in enumerate(artifacts.segments)
    ]
    summary = HierarchicalSummarizer().run(seg_records, video_title=original_filename)

    # --- 4. Qdrant upsert ---
    _upsert_qdrant(s, video_id, artifacts, summary, user_id, original_filename)

    # --- 4a. Standing event timeline (Plan 1) ---
    # After Qdrant upsert, before KG. Gated + best-effort: a failure here never
    # blocks searchability or the rest of ingest.
    if s.timeline_enabled:
        try:
            _run_timeline_for_video(video_id, artifacts, summary, s)
        except Exception as exc:  # noqa: BLE001
            log.warning("ingest:timeline build failed for video=%s: %s", video_id, exc)

    # --- 4b. Knowledge-graph extraction (Phase 2a) ---
    # Runs after Qdrant upsert on purpose: if the LLM step fails halfway, the
    # video is still searchable via plain text + visual retrieval. Gated on the
    # global flag AND on the video actually belonging to at least one Index —
    # standalone Assets uploads pay no KG cost.
    if s.kg_enabled and user_id is not None:
        try:
            _run_kg_for_video_indexes(
                video_id=video_id,
                user_id=user_id,
                seg_records=seg_records,
                summary=summary,
                video_title=original_filename,
                settings=s,
            )
        except Exception as exc:
            log.warning("ingest:kg_extract failed for video=%s: %s", video_id, exc)

    # --- 5. Thumbnails + per-video metadata embedding (visual only) ---
    if artifacts.has_video:
        _write_thumbnails(local_path, video_id, artifacts.segments, scratch)

    # --- 6. Persist DB-bound state (global_summary, modality flags) on the
    # videos row. The worker calls this; we return values for it to commit. ---
    elapsed = time.time() - start
    log.info(
        "ingest:done video_id=%s modality=%s segments=%d elapsed=%.1fs",
        video_id, artifacts.modality, len(artifacts.segments), elapsed,
    )
    return {
        "video_id": str(video_id),
        "duration_s": artifacts.duration_s,
        "shot_count": len(artifacts.segments),
        "modality": artifacts.modality,
        "has_video": artifacts.has_video,
        "has_audio": artifacts.has_audio,
        "global_summary": summary.global_summary,
        "elapsed_s": elapsed,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Visual branch (modality = video_audio | video_only)
# ---------------------------------------------------------------------------


def _ingest_with_video(local_path: str, video_id: UUID, mod, scratch: str) -> IngestArtifacts:
    s = get_settings()

    # 30-second grid, snapped to PySceneDetect cuts when a cut lies within
    # ±5s of a grid boundary — gives cleaner per-segment captions on
    # well-edited content while keeping a predictable grid for the summarizer.
    from main.encoders.indexer import detect_shots, _get_video_duration, extract_frames  # type: ignore
    duration = mod.duration_s or _get_video_duration(local_path)
    if s.shot_detector == "transnet":
        try:
            from main.segmenters.transnet import detect_shots_transnet
            shots = detect_shots_transnet(local_path, s.transnet_weights, device=_torch_device())
        except Exception as exc:  # noqa: BLE001
            log.warning("ingest:transnet failed (%s) — falling back to PySceneDetect", exc)
            shots = detect_shots(local_path, refine_with_speech=False)
    else:
        shots = detect_shots(local_path, refine_with_speech=False)
    segments = _align_segments_to_shots(duration, shots, segment_len=SEGMENT_LEN_SEC)
    log.info("ingest:visual segments=%d duration=%.1fs", len(segments), duration)

    # Per-segment frame batches (used by CLIP-L, captioner, NSFW, OCR).
    frame_batches = [extract_frames(local_path, s_, e_, max_frames=s.clipl_frames_per_segment) for s_, e_ in segments]

    visual_feats = _try_encode(
        "clipl",
        lambda: _encode_clipl(frame_batches),
        fallback=lambda: np.zeros((len(segments), 768), dtype=np.float32),
    )
    crop_embeddings = _try_encode(
        "image_crops",
        lambda: _encode_crop_embeddings(frame_batches, s.image_tile_grid) if s.image_tiling_enabled else None,
        fallback=lambda: None,
    )

    transcripts = ["" for _ in segments]
    audio_tags_per_segment: list[list[dict]] = [[] for _ in segments]
    if mod.has_audio:
        transcripts = _try_encode(
            "asr",
            lambda: _transcribe_segments(local_path, segments),
            fallback=lambda: ["" for _ in segments],
        )
        audio_tags_per_segment = _try_encode(
            "pann",
            lambda: _tag_audio_segments(local_path, segments),
            fallback=lambda: [[] for _ in segments],
        )
    else:
        log.info("ingest:audio skipped (modality=video_only)")

    ocr_texts = _try_encode(
        "ocr",
        lambda: _ocr_segments(local_path, segments),
        fallback=lambda: ["" for _ in segments],
    )
    nsfw_scores = _try_encode(
        "nsfw",
        lambda: _score_nsfw(local_path, segments),
        fallback=lambda: [0.0 for _ in segments],
    )
    captions = _try_encode(
        "vlm_caption",
        lambda: _caption_segments(frame_batches),
        fallback=lambda: ["" for _ in segments],
    )
    shot_actions = _try_encode(
        "vlm_actions",
        lambda: _action_caption_segments(local_path, segments, settings=s),
        fallback=lambda: [],
    )
    audio_event_embeddings = _try_encode(
        "clap_audio_events",
        lambda: _clap_audio_segments(local_path, segments, settings=s) if mod.has_audio else None,
        fallback=lambda: None,
    )
    speaker_turns = _try_encode(
        "diarize",
        lambda: _diarize_speakers(local_path, settings=s) if mod.has_audio else None,
        fallback=lambda: None,
    )
    motion_embeddings = _try_encode(
        "motion",
        lambda: _encode_motion(local_path, segments, settings=s),
        fallback=lambda: None,
    )
    caption_feats = _try_encode(
        "caption_embed",
        lambda: _embed_captions(captions, transcripts, ocr_texts),
        fallback=lambda: np.zeros((len(segments), 3072), dtype=np.float32),
    )
    toxic_scores = _try_encode(
        "toxic",
        lambda: _score_toxic(transcripts),
        fallback=lambda: [0.0 for _ in segments],
    )

    # Full-video visual features for query-time MR / highlights, cached to S3.
    # IV2 path (grounding_backend=iv2): InternVideo2 [n,512] -> SG-DETR head.
    # Legacy path: Lighthouse CLIP+SlowFast -> CG-DETR. Encoded once over the
    # whole file; query time only runs the head on slices.
    # Best-effort: if the grounding weights aren't present (e.g. a fresh pod
    # without /models), skip the feature cache rather than failing the whole
    # ingest — OCR / CLAP / caption / timeline still index; only grounding +
    # highlights for this video are unavailable until re-indexed with weights.
    lighthouse_visual_key: str | None = None
    try:
        if s.grounding_backend == "iv2":
            lighthouse_visual_key = _encode_iv2_visual(local_path, video_id, scratch)
        else:
            lighthouse_visual_key = _encode_lighthouse_visual(local_path, video_id, scratch)
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest:visual grounding-feature cache failed (weights missing?) "
                    "— grounding/highlights unavailable for video=%s: %s", video_id, exc)

    # Audio CLAP features (cached) — only when audio is present. Used by the
    # Ground/Highlights audio fallback. Skipped under grounding_backend=iv2 for
    # video+audio: IV2+SG-DETR already serves visual Highlights, so loading the
    # heavy CLIP+SlowFast/CG-DETR LighthouseService just to cache unused CLAP is
    # wasteful (audio-ONLY clips still go through the audio branch / lighthouse).
    lighthouse_audio_key: str | None = None
    if mod.has_audio and s.grounding_backend != "iv2":
        try:
            lighthouse_audio_key = _encode_lighthouse_audio(local_path, video_id, scratch)
        except Exception as exc:  # noqa: BLE001
            log.warning("ingest:audio CLAP grounding-feature cache failed for video=%s: %s", video_id, exc)

    return IngestArtifacts(
        modality=mod.label,
        duration_s=duration,
        has_video=True,
        has_audio=mod.has_audio,
        segments=segments,
        visual_embeddings=visual_feats,
        caption_embeddings=caption_feats,
        captions=captions,
        transcripts=transcripts,
        ocr_texts=ocr_texts,
        audio_tags_per_segment=audio_tags_per_segment,
        nsfw_scores=nsfw_scores,
        toxic_scores=toxic_scores,
        lighthouse_visual_path=lighthouse_visual_key,
        lighthouse_audio_path=lighthouse_audio_key,
        shot_actions=shot_actions,
        audio_event_embeddings=audio_event_embeddings,
        crop_embeddings=crop_embeddings,
        speaker_turns=speaker_turns,
        motion_embeddings=motion_embeddings,
    )


# ---------------------------------------------------------------------------
# Audio-only branch (modality = audio_only)
# ---------------------------------------------------------------------------


def _ingest_audio_only(local_path: str, video_id: UUID, mod, scratch: str) -> IngestArtifacts:
    """`.mp3`, `.wav`, or audio-only `.mp4`. Skips every visual encoder.

    The Ground / Highlights / Analyze tiles still work — Ground uses
    Lighthouse QD-DETR on CLAP features, Analyze uses the transcript-driven
    hierarchical summary, Highlights uses CLAP saliency.
    """
    duration = mod.duration_s or _probe_audio_duration(local_path)
    segments = _fixed_grid(duration, SEGMENT_LEN_SEC)
    log.info("ingest:audio_only segments=%d duration=%.1fs", len(segments), duration)

    transcripts = _try_encode(
        "asr",
        lambda: _transcribe_segments(local_path, segments),
        fallback=lambda: ["" for _ in segments],
    )
    audio_tags_per_segment = _try_encode(
        "pann",
        lambda: _tag_audio_segments(local_path, segments),
        fallback=lambda: [[] for _ in segments],
    )
    captions = _try_encode(
        "llm_caption_from_asr",
        lambda: _caption_from_transcript(transcripts, audio_tags_per_segment),
        fallback=lambda: list(transcripts),  # transcript is the next-best signal
    )
    caption_feats = _try_encode(
        "caption_embed",
        lambda: _embed_captions(captions, transcripts),
        fallback=lambda: np.zeros((len(segments), 3072), dtype=np.float32),
    )
    toxic_scores = _try_encode(
        "toxic",
        lambda: _score_toxic(transcripts),
        fallback=lambda: [0.0 for _ in segments],
    )

    lighthouse_audio_key = _encode_lighthouse_audio(local_path, video_id, scratch)

    speaker_turns = _try_encode(
        "diarize",
        lambda: _diarize_speakers(local_path),
        fallback=lambda: None,
    )

    # Visual fields stay None / zeros so downstream code paths don't crash on
    # missing keys. CLIP-L vector is zero — never matched in Search (intended).
    visual_feats = np.zeros((len(segments), 768), dtype=np.float32)
    return IngestArtifacts(
        modality=mod.label,
        duration_s=duration,
        has_video=False,
        has_audio=True,
        segments=segments,
        visual_embeddings=visual_feats,
        caption_embeddings=caption_feats,
        captions=captions,
        transcripts=transcripts,
        ocr_texts=["" for _ in segments],
        audio_tags_per_segment=audio_tags_per_segment,
        nsfw_scores=[0.0 for _ in segments],
        toxic_scores=toxic_scores,
        lighthouse_visual_path=None,
        lighthouse_audio_path=lighthouse_audio_key,
        speaker_turns=speaker_turns,
    )


# ---------------------------------------------------------------------------
# Encoder wrappers — kept short so the orchestration above is the readable bit
# ---------------------------------------------------------------------------


def _try_encode(stage: str, run, fallback):
    try:
        return run()
    except Exception as exc:
        log.warning("ingest:%s failed: %s — using fallback", stage, exc)
        return fallback()


def _encode_clipl(frame_batches):
    from main.encoders.clipl_embedder import CLIPLEmbedder
    return CLIPLEmbedder().encode_video_batch(frame_batches)


def _encode_crop_embeddings(frame_batches, grid):
    """Per-shot per-crop CLIP-L embeddings (roadmap #6, index side) for better
    small-object / logo recall. Returns [(shot_idx, region, vec), ...]."""
    from main.encoders.clipl_embedder import CLIPLEmbedder
    from main.pipeline.image_tiling import tile_frames
    emb = CLIPLEmbedder()
    out = []
    for shot_idx, frames in enumerate(frame_batches):
        for region, crop in tile_frames(frames, grid):
            if crop is None or len(crop) == 0:
                continue
            out.append((shot_idx, region, emb.encode_video(crop)))
    return out


def _transcribe_segments(local_path, segments):
    from main.encoders.asr_whisper import transcribe_segment  # type: ignore
    return [transcribe_segment(local_path, s_, e_) for s_, e_ in segments]


_OCR_FRAMES_PER_SEGMENT = 8  # cap; ~1 fps up to this many frames per segment


def _ocr_segments(local_path, segments):
    from main.encoders.ocr_encoder import OCREncoder
    from main.encoders.indexer import extract_frames  # type: ignore
    enc = OCREncoder(device=_torch_device())
    out = []
    for s_, e_ in segments:
        # Sample several frames across the segment and union the unique lines — a
        # single midpoint frame misses transient overlays (title cards, ingredient
        # captions, scoreboards). De-dupes text repeated across frames.
        n = max(1, min(_OCR_FRAMES_PER_SEGMENT, int(round(e_ - s_))))
        frames = extract_frames(local_path, s_, e_, max_frames=n)
        seen: list[str] = []
        for f in (frames if frames is not None else []):
            t = (enc.extract_from_frame(f) or "").strip()
            if t and t not in seen:
                seen.append(t)
        out.append(" | ".join(seen))
    return out


def _tag_audio_segments(local_path, segments):
    from main.encoders.audio_event_encoder import (
        AudioEventEncoder, _load_full_audio_32k_mono, slice_samples,
    )
    ae = AudioEventEncoder(device=_torch_device())
    full = _load_full_audio_32k_mono(local_path)
    out = []
    for s_, e_ in segments:
        seg = slice_samples(full, s_, e_, sr=32000)
        out.append(ae.tag_audio_segment(seg, top_k=5) if seg is not None and seg.size else [])
    return out


def _score_nsfw(local_path, segments):
    from main.encoders.moderation_encoder import NSFWClassifier
    from main.encoders.indexer import extract_frames  # type: ignore
    cls = NSFWClassifier(device=_torch_device())
    scores = []
    for s_, e_ in segments:
        mid = (s_ + e_) / 2
        frames = extract_frames(local_path, mid, mid + 0.5, max_frames=1)
        scores.append(cls.score_frame(frames[0]) if frames is not None and len(frames) else 0.0)
    return scores


def _caption_segments(frame_batches):
    from main.encoders.captioner import VLMCaptioner
    from main.encoders.config import config as _jockey_config
    cap = VLMCaptioner.from_config(_jockey_config)
    if not cap.is_available():
        log.info("ingest:captioner disabled — captions will be empty")
        return ["" for _ in frame_batches]
    return cap.caption_batch(frame_batches)


def _action_caption_segments(local_path, segments, *, settings=None) -> list[dict]:
    """Eager VLM action re-caption (roadmap #3). For each segment: sample ~fps
    frames (capped) and ask the VLM for timestamped actions, mapped to absolute
    video time. Gated on vlm_actions_enabled; returns [] when off/unavailable."""
    s = settings or get_settings()
    if not s.vlm_actions_enabled:
        return []
    from main.encoders.indexer import extract_frames  # type: ignore
    from main.encoders.action_captioner import ActionCaptioner
    from main.encoders.config import config as _jockey_config

    cap = ActionCaptioner.from_config(_jockey_config)
    if not cap.is_available():
        log.info("ingest:action captioner disabled — no action events")
        return []
    events: list[dict] = []
    for (t0, t1) in segments:
        dur = float(t1) - float(t0)
        n = max(1, min(s.vlm_actions_max_frames, int(round(dur * s.vlm_actions_fps))))
        frames = extract_frames(local_path, float(t0), float(t1), max_frames=n)
        if frames is None or len(frames) == 0:
            continue
        events.extend(cap.caption_actions(
            frames, clip_start=float(t0), clip_dur=dur, span_sec=s.vlm_actions_event_span_sec,
        ))
    return events


def _clap_audio_segments(local_path, segments, *, settings=None):
    """Per-segment CLAP audio embeddings (roadmap #2) for the audio-event vector
    index. Gated on audio_events_enabled; returns None when off/unavailable."""
    s = settings or get_settings()
    if not s.audio_events_enabled:
        return None
    from main.encoders.clap_encoder import CLAPEncoder
    enc = CLAPEncoder(use_cuda=(_torch_device() == "cuda"))
    if not enc.is_available():
        log.info("ingest:CLAP audio encoder disabled — no audio-event vectors")
        return None
    return enc.encode_audio_segments(local_path, segments)


def _diarize_speakers(local_path, *, settings=None) -> list[dict] | None:
    """Full-file pyannote speaker diarization (research F). Gated on
    diarization_enabled; returns None when off/unavailable."""
    s = settings or get_settings()
    if not s.diarization_enabled:
        return None
    from main.encoders.config import config as _jockey_config
    from main.encoders.diarizer import SpeakerDiarizer
    d = SpeakerDiarizer.from_config(_jockey_config, s)
    if not d.is_available():
        log.info("ingest:diarizer disabled — no speaker turns")
        return None
    return d.diarize(local_path)


def _encode_motion(local_path, segments, *, settings=None):
    """Per-segment ViCLIP motion embeddings (research A) for the `jockey_motion`
    index. Gated on motion_enabled; returns None when off/unavailable."""
    s = settings or get_settings()
    if not s.motion_enabled:
        return None
    from main.encoders.indexer import extract_frames  # type: ignore
    from main.encoders.motion_encoder import MotionEncoder
    enc = MotionEncoder.from_settings(s)
    if not enc.is_available():
        log.info("ingest:motion encoder disabled — no motion vectors")
        return None
    vecs = []
    for (t0, t1) in segments:
        frames = extract_frames(local_path, float(t0), float(t1), max_frames=s.motion_frames_per_segment)
        if frames is None or len(frames) == 0:
            vecs.append(np.zeros(s.motion_embedding_dim, dtype=np.float32))
            continue
        v = enc.encode_video(frames)
        vecs.append(v if v is not None else np.zeros(s.motion_embedding_dim, dtype=np.float32))
    return np.stack(vecs) if vecs else None


def _caption_from_transcript(transcripts: list[str], audio_tags: list[list[dict]]) -> list[str]:
    """For audio-only inputs there are no frames. We synthesize a per-segment
    "caption-equivalent" from the transcript + top audio tags so the dense
    retrieval index has something to match against beyond raw ASR."""
    from openai import OpenAI
    s = get_settings()
    if not s.openrouter_api_key:
        return list(transcripts)
    client = OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)
    out: list[str] = []
    for t, tags in zip(transcripts, audio_tags):
        if not t.strip():
            out.append("")
            continue
        tag_str = ", ".join(x.get("label", "") for x in tags[:3] if x.get("label"))
        prompt = (
            f"You are describing a 30-second audio segment. Spoken transcript:\n"
            f"{t.strip()}\nDetected audio: {tag_str or '(none)'}\n\n"
            "Write one short sentence (≤ 25 words) capturing what is being "
            "discussed or what is happening in the audio. Be concrete."
        )
        try:
            resp = client.chat.completions.create(
                model=s.summary_llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.2,
            )
            out.append((resp.choices[0].message.content or "").strip())
        except Exception as exc:
            log.warning("ingest:caption-from-transcript failed: %s", exc)
            out.append(t.strip())
    return out


def _embed_captions(captions: list[str], transcripts: list[str],
                    ocr_texts: list[str] | None = None) -> np.ndarray:
    from main.encoders.search import TextEmbedder
    from main.encoders.config import config
    if not config.openrouter_api_key:
        raise RuntimeError("no openrouter_api_key configured")
    embedder = TextEmbedder(
        api_key=config.openrouter_api_key,
        model=config.text_embedding_model,
        base_url=config.openrouter_base_url,
    )
    # roadmap #1 (semantic OCR): fold on-screen text into the embedded signal so
    # segments are retrievable by their signage/slide text, not just speech+caption.
    ocr = ocr_texts if ocr_texts is not None else ["" for _ in captions]

    def _combine(t: str, c: str, o: str) -> str:
        parts = [p for p in (t, c, o) if p]
        return " | ".join(parts) if parts else " "

    return np.stack([
        embedder.encode(_combine(transcripts[i], captions[i], ocr[i]))
        for i in range(len(captions))
    ])


def _score_toxic(transcripts):
    from main.encoders.moderation_encoder import ToxicTextClassifier
    cls = ToxicTextClassifier(device=_torch_device())
    return [cls.score_text(t or "") for t in transcripts]


# ---------------------------------------------------------------------------
# Lighthouse feature pre-compute & S3 cache
# ---------------------------------------------------------------------------


def _encode_iv2_visual(local_path: str, video_id: UUID, scratch: str) -> str:
    """Encode the whole video with InternVideo2 (`[n_clips, 512]`, no TEF) and
    cache to S3 for query-time SG-DETR Ground/Highlights. TEF is appended at
    query time inside the grounding service."""
    from main.services.iv2_grounding_service import get_iv2_grounding
    s = get_settings()
    feats = get_iv2_grounding().encode_video_to_features(local_path)
    key = f"features/{video_id}/iv2/visual.npy"
    _put_npy_to_s3(feats, s.minio_bucket_videos, key, scratch)
    log.info("ingest:iv2_visual cached clips=%d key=%s", feats.shape[0], key)
    return key


def _encode_lighthouse_visual(local_path: str, video_id: UUID, scratch: str) -> str:
    """Run CLIP+SlowFast over the full video, cache `[n_clips, 2818]` to S3.
    Returns the S3 key for later retrieval at query time."""
    from main.services.lighthouse_service import get_lighthouse
    s = get_settings()
    feats = get_lighthouse().encode_video_to_features(local_path)
    key = f"features/{video_id}/lighthouse/clip_slowfast.npy"
    _put_npy_to_s3(feats, s.minio_bucket_videos, key, scratch)
    log.info("ingest:lighthouse_visual cached clips=%d key=%s", feats.shape[0], key)
    return key


def _encode_lighthouse_audio(local_path: str, video_id: UUID, scratch: str) -> str:
    from main.services.lighthouse_service import get_lighthouse
    s = get_settings()
    feats = get_lighthouse().encode_audio_to_features(local_path)
    key = f"features/{video_id}/lighthouse/clap.npy"
    _put_npy_to_s3(feats, s.minio_bucket_videos, key, scratch)
    log.info("ingest:lighthouse_audio cached clips=%d key=%s", feats.shape[0], key)
    return key


def _put_npy_to_s3(arr: np.ndarray, bucket: str, key: str, scratch: str) -> None:
    path = os.path.join(scratch, key.replace("/", "_"))
    np.save(path, arr)
    with open(path, "rb") as f:
        s3().upload_fileobj(f, bucket, key, ExtraArgs={"ContentType": "application/octet-stream"})


# ---------------------------------------------------------------------------
# Knowledge-graph extraction dispatch
# ---------------------------------------------------------------------------


def _qdrant_point_id_for(video_id: UUID) -> "callable":
    """Return a function mapping a segment index → the deterministic Qdrant
    point UUID used elsewhere in this module. Kept in one place so KG mention
    rows reference the exact same point id the segment was upserted under."""
    def _impl(segment_idx: int) -> str:
        return str(uuid5(NAMESPACE_OID, f"{video_id}:{segment_idx}"))
    return _impl


def _run_timeline_for_video(video_id: UUID, artifacts, summary, settings) -> None:
    """Build + persist the standing event timeline for one video. Builds its own
    sync DB session (mirrors _run_kg_for_video_indexes)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from cm_shared.settings import get_base_settings
    from main.pipeline.timeline.build import build_timeline

    engine = create_engine(get_base_settings().sync_database_url, pool_pre_ping=True, future=True)
    Session = sessionmaker(engine, expire_on_commit=False)
    session = Session()
    try:
        build_timeline(video_id, artifacts, summary, settings=settings, db_session=session)
    finally:
        session.close()


def _run_kg_for_video_indexes(
    *,
    video_id: UUID,
    user_id: UUID,
    seg_records: list,
    summary,
    video_title: str,
    settings,
) -> None:
    """Find every Index this video belongs to and run KG extraction for each.

    A video can technically be in multiple indexes (it's a many-to-many). In
    practice this is rare, and KG extraction is identical per index because
    entities are scoped by `index_id`. We pay the LLM cost once per index the
    video joins — bounded and easy to reason about.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from cm_shared.settings import get_base_settings
    from main.models.index import IndexVideo
    from main.pipeline.kg_extract import run_kg_extract

    engine = create_engine(get_base_settings().sync_database_url, pool_pre_ping=True, future=True)
    Session = sessionmaker(engine, expire_on_commit=False)
    session = Session()
    try:
        index_ids = (
            session.execute(
                select(IndexVideo.index_id).where(IndexVideo.video_id == video_id)
            )
            .scalars()
            .all()
        )
        if not index_ids:
            log.info("ingest:kg_extract skipped — video not in any Index (video=%s)", video_id)
            return

        point_id_for = _qdrant_point_id_for(video_id)
        for index_id in index_ids:
            run_kg_extract(
                video_id=video_id,
                index_id=index_id,
                user_id=user_id,
                video_title=video_title,
                segments=seg_records,
                windows=summary.windows,
                qdrant_point_id_for=point_id_for,
                db_session=session,
                settings=settings,
            )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Qdrant upsert
# ---------------------------------------------------------------------------


# Qdrant tuning for the Cloudflare-tunnelled deployment. Default client timeout
# is 5 s — too short for the round-trip through a CF tunnel on a ~hundreds-of-
# points upsert (migration log 2026-05-23 problem 22). 300 s is generous on
# purpose since the worker is the only caller and a single ingest hits Qdrant
# 2–3 times at most.
_QDRANT_TIMEOUT_SEC = 300


def _upsert_qdrant(s, video_id: UUID, a: IngestArtifacts, summary, user_id, original_filename) -> None:
    from qdrant_client.http import models as qm

    from main.qdrant_util import batched_upsert, ensure_collection, get_qdrant_client, to_vector_list

    client = get_qdrant_client(timeout=_QDRANT_TIMEOUT_SEC)
    existing = {c.name for c in client.get_collections().collections}

    if a.visual_embeddings is None or a.visual_embeddings.size == 0:
        log.warning("ingest:qdrant skipped — no visual embeddings (degenerate input)")
        return
    vec_dim = a.visual_embeddings.shape[1]
    ensure_collection(client, s.qdrant_collection, vec_dim, existing=existing)

    # Per-segment text collection — used by the Analyze tile for dense
    # retrieval against caption+transcript. Visual CLIP-L vectors live in
    # `qdrant_collection` (for visual Search); they are too far from text
    # space to give good caption-similarity scores at query time.
    text_collection = "jockey_segments_text"
    have_text_vecs = a.caption_embeddings is not None and a.caption_embeddings.size > 0
    if have_text_vecs:
        text_dim = a.caption_embeddings.shape[1]
        ensure_collection(client, text_collection, text_dim, existing=existing)

    window_size = s.summary_window_size_sec
    window_summary_by_idx = {w.idx: w.summary for w in summary.windows}

    visual_points = []
    text_points = []
    for idx, (t0, t1) in enumerate(a.segments):
        window_idx = int(t0 // window_size)
        point_id = str(uuid5(NAMESPACE_OID, f"{video_id}:{idx}"))
        payload = {
            "video_id": str(video_id),
            "shot_idx": idx,
            "segment_idx": idx,
            "t_start": float(t0),
            "t_end": float(t1),
            "asr_text": a.transcripts[idx],
            "transcript": a.transcripts[idx],
            "ocr_text": a.ocr_texts[idx],
            "chunk_caption": a.captions[idx],
            "caption": a.captions[idx],
            "segment_summary": summary.segment_summaries.get(idx, ""),
            "window_idx": window_idx,
            "window_summary": window_summary_by_idx.get(window_idx, ""),
            "audio_tags": a.audio_tags_per_segment[idx],
            "nsfw_score": float(a.nsfw_scores[idx]),
            "toxic_score": float(a.toxic_scores[idx]),
            "modality": a.modality,
            "has_video": a.has_video,
            "has_audio": a.has_audio,
        }
        visual_points.append(
            qm.PointStruct(
                id=point_id,
                vector=a.visual_embeddings[idx].tolist(),
                payload=payload,
            )
        )
        if have_text_vecs:
            text_points.append(
                qm.PointStruct(
                    id=point_id,
                    vector=a.caption_embeddings[idx].tolist(),
                    payload=payload,
                )
            )
    batched_upsert(client, s.qdrant_collection, visual_points)
    if text_points:
        batched_upsert(client, text_collection, text_points)

    # audio-event CLAP vectors (roadmap #2) -> jockey_audio_events (text-queryable)
    if a.audio_event_embeddings is not None and a.audio_event_embeddings.size:
        ae_coll = s.audio_events_collection
        ae_dim = a.audio_event_embeddings.shape[1]
        ensure_collection(client, ae_coll, ae_dim, existing=existing)
        ae_points = [
            qm.PointStruct(
                id=str(uuid5(NAMESPACE_OID, f"{video_id}:{idx}")),
                vector=a.audio_event_embeddings[idx].tolist(),
                payload={"video_id": str(video_id), "t_start": float(t0), "t_end": float(t1),
                         "audio_tags": a.audio_tags_per_segment[idx]},
            )
            for idx, (t0, t1) in enumerate(a.segments)
        ]
        batched_upsert(client, ae_coll, ae_points)

    # ViCLIP motion vectors (research A) -> jockey_motion (temporal motion retrieval)
    if a.motion_embeddings is not None and a.motion_embeddings.size:
        m_coll = s.motion_collection
        m_dim = a.motion_embeddings.shape[1]
        ensure_collection(client, m_coll, m_dim, existing=existing)
        m_points = [
            qm.PointStruct(
                id=str(uuid5(NAMESPACE_OID, f"{video_id}:{idx}:motion")),
                vector=a.motion_embeddings[idx].tolist(),
                payload={"video_id": str(video_id), "segment_idx": idx,
                         "t_start": float(t0), "t_end": float(t1),
                         "caption": a.captions[idx]},
            )
            for idx, (t0, t1) in enumerate(a.segments)
        ]
        batched_upsert(client, m_coll, m_points)

    # image crop vectors (roadmap #6) -> jockey_shots (small-object / logo recall)
    if a.crop_embeddings:
        crop_points = []
        for shot_idx, region, vec in a.crop_embeddings:
            t0, t1 = a.segments[shot_idx]
            crop_points.append(qm.PointStruct(
                id=str(uuid5(NAMESPACE_OID, f"{video_id}:{shot_idx}:crop:{region}")),
                vector=to_vector_list(vec),
                payload={"video_id": str(video_id), "shot_idx": shot_idx,
                         "t_start": float(t0), "t_end": float(t1), "crop": region},
            ))
        if crop_points:
            batched_upsert(client, s.qdrant_collection, crop_points)

    # Per-video mean-pooled caption embedding for the Recommend tile.
    if a.caption_embeddings is not None and a.caption_embeddings.size > 0:
        try:
            metadata_vec = a.caption_embeddings.mean(axis=0).astype(np.float32)
            meta = "jockey_videos"
            ensure_collection(client, meta, int(metadata_vec.shape[0]))
            client.upsert(
                collection_name=meta,
                points=[
                    qm.PointStruct(
                        id=str(uuid5(NAMESPACE_OID, f"video:{video_id}")),
                        vector=metadata_vec.tolist(),
                        payload={
                            "video_id": str(video_id),
                            "user_id": str(user_id) if user_id else None,
                            "original_filename": original_filename or "",
                            "modality": a.modality,
                            "global_summary": summary.global_summary,
                        },
                    )
                ],
            )
        except Exception as exc:
            log.warning("ingest:metadata_emb failed: %s", exc)


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------


def _write_thumbnails(local_path: str, video_id: UUID, segments, scratch) -> None:
    s = get_settings()
    for idx, (s_, e_) in enumerate(segments):
        thumb_path = os.path.join(scratch, f"shot_{idx}.jpg")
        # Thumbnails are cosmetic — a single frame-extraction miss (e.g. a shot
        # midpoint landing near a chunk's reset-timestamp boundary) must NOT fail
        # the whole ingest.
        try:
            if _save_thumbnail(local_path, (s_ + e_) / 2, thumb_path) and os.path.exists(thumb_path):
                with open(thumb_path, "rb") as f:
                    s3().upload_fileobj(
                        f, s.minio_bucket_thumbs, f"{video_id}/{idx}.jpg",
                        ExtraArgs={"ContentType": "image/jpeg"},
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("ingest:thumbnail shot=%s skipped: %s", idx, exc)


def _save_thumbnail(video_path: str, t_mid: float, dest_path: str) -> bool:
    try:
        subprocess.run(
            # 480w: library cards render ~420px wide, so 160w thumbs were ~3x
            # upscaled and visibly blurry. ~30-60KB/jpg at 480w is still cheap.
            ["ffmpeg", "-y", "-ss", f"{t_mid:.2f}", "-i", video_path,
             "-frames:v", "1", "-vf", "scale=480:-1", "-loglevel", "quiet", dest_path],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError:
        return False
    # ffmpeg can exit 0 yet write nothing when the seek lands at/just past the
    # stream's end (happens on chunked videos). Treat "no file / empty" as a miss.
    return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0


# ---------------------------------------------------------------------------
# Time-grid helpers
# ---------------------------------------------------------------------------


def _fixed_grid(duration: float, segment_len: float) -> list[tuple[float, float]]:
    """Plain fixed-size grid — used for audio-only inputs."""
    if duration <= 0:
        return []
    n = int(np.ceil(duration / segment_len))
    return [
        (i * segment_len, min((i + 1) * segment_len, duration))
        for i in range(n)
    ]


def _align_segments_to_shots(
    duration: float,
    shots: list[tuple[float, float]],
    segment_len: float,
    snap_tolerance: float = 5.0,
) -> list[tuple[float, float]]:
    """30-second grid that snaps each segment boundary to the nearest PySceneDetect
    cut when one lies within ±`snap_tolerance` seconds. This keeps the segment
    grid predictable (the summarizer expects a fixed window cadence) while still
    avoiding mid-cut frame batches on cleanly edited content."""
    if duration <= 0:
        return []
    cuts = sorted({float(s) for s, _ in shots} | {float(e) for _, e in shots} | {duration})
    grid = [i * segment_len for i in range(int(np.ceil(duration / segment_len)) + 1)]
    snapped: list[float] = []
    for g in grid:
        candidate = min(cuts, key=lambda c: abs(c - g))
        snapped.append(candidate if abs(candidate - g) <= snap_tolerance else g)
    # Ensure monotonic, deduped, end-clipped.
    cleaned: list[float] = []
    for b in snapped:
        if not cleaned or b > cleaned[-1] + 1.0:
            cleaned.append(min(b, duration))
    if cleaned[0] > 0:
        cleaned.insert(0, 0.0)
    if cleaned[-1] < duration:
        cleaned.append(duration)
    return [(cleaned[i], cleaned[i + 1]) for i in range(len(cleaned) - 1)]


def _probe_audio_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0
