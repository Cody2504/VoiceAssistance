"""EasyOCR per-frame text extractor — closes UC #17 (products on screen) and
contributes to UC #6 (text/logos as text).

Lazy-loaded. First call downloads ~200MB English-model weights to
`~/.EasyOCR/`. CPU-runnable. Returns a single joined string per frame so it
slots cleanly into Qdrant payloads as `ocr_text`.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class OCREncoder:
    """Lazy wrapper around EasyOCR. Use `extract_from_frame(frame_rgb)`."""

    def __init__(self, languages: tuple[str, ...] = ("en",), device: str = "cpu"):
        self.languages = list(languages)
        self.gpu = device.startswith("cuda")
        self._reader = None

    def _load(self):
        if self._reader is not None:
            return
        import easyocr  # type: ignore
        log.info("ocr_encoder: loading EasyOCR languages=%s gpu=%s", self.languages, self.gpu)
        self._reader = easyocr.Reader(self.languages, gpu=self.gpu, verbose=False)
        log.info("ocr_encoder: ready")

    def extract_from_frame(self, frame_rgb: np.ndarray, min_conf: float = 0.4) -> str:
        """Run OCR on a single RGB frame. Returns joined text passing min_conf.

        Empty string if no readable text or if the reader fails to load.
        """
        if frame_rgb is None or getattr(frame_rgb, "size", 0) == 0:
            return ""
        try:
            self._load()
        except Exception as exc:
            log.warning("ocr_encoder: load failed (%s) — returning empty", exc)
            return ""
        try:
            # EasyOCR accepts BGR or RGB numpy arrays; we feed RGB.
            results = self._reader.readtext(frame_rgb)
        except Exception as exc:
            log.warning("ocr_encoder: readtext failed: %s", exc)
            return ""
        toks: list[str] = []
        for r in results:
            # readtext returns list of (bbox, text, confidence)
            try:
                _, text, conf = r
            except (ValueError, TypeError):
                continue
            if conf >= min_conf and text and text.strip():
                toks.append(str(text).strip())
        return " ".join(toks)
