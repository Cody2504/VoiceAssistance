"""Cut 2 / Task 11.10 — OCR.

Two paths:

Cached (default everywhere)
    The indexing pipeline already wrote per-shot `ocr_text` to Qdrant.
    Emit a segment for every shot that has on-screen text. Zero compute.

Fresh OCR (vast.ai GPU only)
    If PaddleOCR is importable in this image, re-run OCR on the start
    frame of each shot for higher-quality text or a different language.
    Used by setting `OCR_FRESH=true` on the segment definition fields:
    a `lang` field overrides the OCR language.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from functools import lru_cache
from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition
from main.models.video import Video
from main.settings import get_settings
from main.storage.minio import download_to_path

from .qdrant_io import read_shots
from .video_io import fetch_video

log = logging.getLogger(__name__)


def _format_from_cached(shots: list[dict[str, Any]], definition: SegmentDefinition) -> list[dict[str, Any]]:
    field_names = {f.name for f in definition.fields}
    out: list[dict[str, Any]] = []
    for sh in shots:
        text = (sh.get("ocr_text") or "").strip()
        if not text:
            continue
        meta: dict[str, Any] = {}
        if "ocr_text" in field_names:
            meta["ocr_text"] = text
        if "shot_idx" in field_names:
            meta["shot_idx"] = sh["idx"]
        out.append({"t_start": sh["t_start"], "t_end": sh["t_end"], "metadata": meta})
    return out


@lru_cache(maxsize=4)
def _paddle(lang: str):
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    log.info("ocr: loading PaddleOCR lang=%s", lang)
    return PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)


def _extract_frame(video_path: str, t: float) -> str | None:
    fd, png = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video_path,
             "-frames:v", "1", "-loglevel", "quiet", png],
            check=True,
        )
        return png
    except subprocess.CalledProcessError:
        try: os.remove(png)
        except OSError: pass
        return None


def _format_from_fresh(
    video: Video, shots: list[dict[str, Any]], definition: SegmentDefinition, lang: str
) -> list[dict[str, Any]] | None:
    engine = _paddle(lang)
    if engine is None:
        return None

    fd, video_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        download_to_path(get_settings().minio_bucket_videos, video.minio_key, video_path)
        field_names = {f.name for f in definition.fields}
        out: list[dict[str, Any]] = []
        for sh in shots:
            png = _extract_frame(video_path, sh["t_start"])
            if png is None:
                continue
            try:
                texts: list[str] = []
                for page in engine.ocr(png, cls=True) or []:
                    if not page:
                        continue
                    for line in page:
                        try:
                            text = line[1][0]
                        except (IndexError, TypeError):
                            continue
                        if text:
                            texts.append(text)
                if not texts:
                    continue
                meta: dict[str, Any] = {}
                if "ocr_text" in field_names:
                    meta["ocr_text"] = " | ".join(texts)
                if "shot_idx" in field_names:
                    meta["shot_idx"] = sh["idx"]
                out.append({"t_start": sh["t_start"], "t_end": sh["t_end"], "metadata": meta})
            finally:
                try: os.remove(png)
                except OSError: pass
        return out
    finally:
        try: os.remove(video_path)
        except OSError: pass


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    if not shots:
        return []

    # "Fresh OCR" mode is opt-in via env to keep the default path cheap.
    if os.environ.get("OCR_FRESH", "").lower() in {"1", "true", "yes"}:
        video = fetch_video(video_id)
        if video is not None:
            lang_field = next((f for f in definition.fields if f.name == "lang"), None)
            lang = (lang_field.description if lang_field and lang_field.description else "en")[:8]
            fresh = _format_from_fresh(video, shots, definition, lang)
            if fresh is not None:
                return fresh
            log.info("ocr:PaddleOCR not available — falling back to cached payload")

    return _format_from_cached(shots, definition)
