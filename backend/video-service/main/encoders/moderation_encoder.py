"""Content-moderation classifiers — closes UC #14 properly.

Two specialised models replace the prompt-only VLM moderation path:

  - Visual NSFW: `Falconsai/nsfw_image_detection` (ViT image classifier, ~340MB)
                  Returns P(nsfw) ∈ [0, 1] per shot's middle frame.
  - Textual toxicity: `unitary/toxic-bert` (BERT classifier, ~440MB)
                  Returns P(toxic) ∈ [0, 1] per ASR transcript.

Both lazy-loaded, CPU-runnable. Outputs stored as `nsfw_score` and `toxic_score`
on each shot's Qdrant payload, plus per-video aggregates on the Video row.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class NSFWClassifier:
    """Per-frame NSFW classifier (Falconsai/nsfw_image_detection ViT)."""

    def __init__(self, device: str = "cpu", model_name: str = "Falconsai/nsfw_image_detection"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None
        self._nsfw_idx: Optional[int] = None

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        log.info("nsfw_classifier: loading %s (device=%s)", self.model_name, self.device)
        self._processor = AutoImageProcessor.from_pretrained(self.model_name)
        self._model = AutoModelForImageClassification.from_pretrained(self.model_name).to(self.device).eval()
        # Discover which label maps to "nsfw"
        id2label = getattr(self._model.config, "id2label", {})
        for i, lab in id2label.items():
            if isinstance(lab, str) and "nsfw" in lab.lower():
                self._nsfw_idx = int(i)
                break
        if self._nsfw_idx is None:
            # Fallback heuristic: assume index 1 is positive class
            self._nsfw_idx = 1
        log.info("nsfw_classifier: ready (nsfw_idx=%d)", self._nsfw_idx)

    def score_frame(self, frame_rgb: np.ndarray) -> float:
        """Return P(NSFW) ∈ [0,1] for a single RGB frame. 0.0 on failure."""
        if frame_rgb is None or getattr(frame_rgb, "size", 0) == 0:
            return 0.0
        try:
            self._load()
        except Exception as exc:
            log.warning("nsfw_classifier: load failed (%s)", exc)
            return 0.0
        try:
            import torch
            from PIL import Image
            img = Image.fromarray(frame_rgb)
            inputs = self._processor(images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                logits = self._model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()
            return float(probs[self._nsfw_idx])
        except Exception as exc:
            log.warning("nsfw_classifier: inference failed: %s", exc)
            return 0.0


class ToxicTextClassifier:
    """Per-text toxicity classifier (unitary/toxic-bert)."""

    def __init__(self, device: str = "cpu", model_name: str = "unitary/toxic-bert"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._tokenizer = None
        self._toxic_idx: Optional[int] = None

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        log.info("toxic_classifier: loading %s (device=%s)", self.model_name, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name).to(self.device).eval()
        id2label = getattr(self._model.config, "id2label", {})
        for i, lab in id2label.items():
            if isinstance(lab, str) and "toxic" in lab.lower() and "non" not in lab.lower():
                self._toxic_idx = int(i)
                break
        if self._toxic_idx is None:
            self._toxic_idx = 0  # unitary/toxic-bert: label 0 = toxic
        log.info("toxic_classifier: ready (toxic_idx=%d)", self._toxic_idx)

    def score_text(self, text: str) -> float:
        """Return P(toxic) ∈ [0,1] for a single text. 0.0 on empty/failure."""
        if not text or not text.strip():
            return 0.0
        try:
            self._load()
        except Exception as exc:
            log.warning("toxic_classifier: load failed (%s)", exc)
            return 0.0
        try:
            import torch
            inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=256).to(self.device)
            with torch.no_grad():
                logits = self._model(**inputs).logits
            # toxic-bert uses sigmoid (multi-label), not softmax
            probs = torch.sigmoid(logits)[0].cpu().numpy()
            return float(probs[self._toxic_idx])
        except Exception as exc:
            log.warning("toxic_classifier: inference failed: %s", exc)
            return 0.0
