"""Open-vocabulary object detector (research item B) — GroundingDINO via HF
transformers, used ONLY at query time to verify/re-rank `when` candidates by
whether the query's object phrase is actually detectable in the candidate
window (coarse-to-fine: the coarse streams find the neighborhood, the detector
pins which neighborhood really shows the object).

No ingest/index cost. Lazy `_UNAVAILABLE` pattern like the other encoders.
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

_UNAVAILABLE = "unavailable"


class ObjectDetector:
    def __init__(self, model_name: str, box_threshold: float = 0.25):
        self.model_name = model_name
        self.box_threshold = box_threshold
        self._model = None
        self._processor = None

    @classmethod
    def from_settings(cls, settings) -> "ObjectDetector":
        return cls(
            model_name=settings.object_verify_model,
            box_threshold=settings.object_verify_box_threshold,
        )

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
            self._processor = AutoProcessor.from_pretrained(self.model_name)
            model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model_name)
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = model.to(self._device).eval()
            log.info("ObjectDetector ready (model=%s, device=%s)", self.model_name, self._device)
        except Exception as exc:  # noqa: BLE001
            log.warning("ObjectDetector unavailable: %s", exc)
            self._model = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._model not in (None, _UNAVAILABLE)

    def max_confidence(self, frames: np.ndarray, phrase: str) -> float | None:
        """Max detection confidence for `phrase` across `frames` [N, H, W, 3]
        uint8 RGB. 0.0 = looked and found nothing (a real demote signal);
        None = could not look (caller should leave the score untouched)."""
        self._lazy_load()
        if self._model in (None, _UNAVAILABLE) or not phrase:
            return None
        if frames is None or len(frames) == 0:
            return None
        try:
            import torch
            from PIL import Image
            images = [Image.fromarray(np.asarray(f, dtype=np.uint8)) for f in frames]
            inputs = self._processor(
                images=images, text=[phrase] * len(images), return_tensors="pt"
            ).to(self._device)
            with torch.no_grad():
                outputs = self._model(**inputs)
            sizes = [img.size[::-1] for img in images]
            try:
                # transformers >= 4.51 renamed box_threshold -> threshold
                results = self._processor.post_process_grounded_object_detection(
                    outputs, inputs.input_ids,
                    threshold=self.box_threshold, text_threshold=0.25, target_sizes=sizes,
                )
            except TypeError:
                results = self._processor.post_process_grounded_object_detection(
                    outputs, inputs.input_ids,
                    box_threshold=self.box_threshold, text_threshold=0.25, target_sizes=sizes,
                )
            best = 0.0
            for r in results:
                scores = r.get("scores")
                if scores is not None and len(scores):
                    best = max(best, float(scores.max()))
            return best
        except Exception as exc:  # noqa: BLE001
            log.warning("ObjectDetector: detection failed: %s", exc)
            return None
