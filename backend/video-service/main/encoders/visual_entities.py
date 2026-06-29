"""32B VLM that describes a shot's frames into a searchable `visual_entities` text
for image search. Mirrors the OpenRouter client + safe-default pattern of
`image_verify.py`, but uses its OWN model (`visual_entities_model`) so the shared
8B caption is untouched. Safe-by-default: unavailable/error -> '' (non-blocking)."""
import base64
import logging
import os
from io import BytesIO
from typing import List, Optional

import numpy as np

log = logging.getLogger(__name__)
_UNAVAILABLE = "unavailable"

VISUAL_ENTITY_PROMPT = (
    "You are describing frames from one moment of a video so it can later be found "
    "by an image search. List everything clearly visible that identifies WHAT is "
    "shown: (1) any brand, product, or logo you recognize, by name; (2) any visible "
    "text, signage, or packaging words, transcribed verbatim; (3) distinctive "
    "objects; (4) a short scene description. If you cannot name something, describe "
    "it (shape, colour, type). Be concise (<= 60 words). End with a line "
    "'NAMES: <comma-separated brand/product/wordmark names you are confident about, "
    "or none>'."
)


def _frames_to_jpegs(frames: np.ndarray, k: int) -> List[bytes]:
    """Pick up to k evenly-spaced frames and JPEG-encode them."""
    from PIL import Image
    if frames is None or len(frames) == 0:
        return []
    idxs = np.linspace(0, len(frames) - 1, num=min(k, len(frames))).round().astype(int)
    out = []
    for i in sorted(set(idxs.tolist())):
        buf = BytesIO()
        Image.fromarray(np.asarray(frames[i], dtype=np.uint8)).save(buf, format="JPEG", quality=90)
        out.append(buf.getvalue())
    return out


class VisualEntityCaptioner:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 base_url: str = "https://openrouter.ai/api/v1", frames_per_shot: int = 4,
                 max_new_tokens: int = 160, enabled: Optional[bool] = None):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or os.environ.get("VISUAL_ENTITIES_MODEL", "qwen/qwen3-vl-32b-instruct")
        self.base_url = base_url
        self.frames_per_shot = frames_per_shot
        self.max_new_tokens = max_new_tokens
        self.enabled = bool(self.api_key) if enabled is None else enabled
        self._client = None

    def _lazy_load(self) -> None:
        if self._client is not None:
            return
        if not self.enabled or not self.api_key:
            self._client = _UNAVAILABLE
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            self._client = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._client not in (None, _UNAVAILABLE)

    def caption_shot(self, frames: np.ndarray) -> str:
        if not self.is_available():
            return ""
        jpegs = _frames_to_jpegs(frames, self.frames_per_shot)
        if not jpegs:
            return ""
        content: list = [{"type": "text", "text": VISUAL_ENTITY_PROMPT}]
        for j in jpegs:
            b64 = base64.b64encode(j).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        try:
            resp = self._client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": content}],
                max_tokens=self.max_new_tokens, temperature=0)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001 — never break ingest
            log.warning("visual_entities caption failed (%s)", e)
            return ""

    def caption_batch(self, frame_batches: List[np.ndarray]) -> List[str]:
        return [self.caption_shot(fb) for fb in frame_batches]


_singleton: Optional[VisualEntityCaptioner] = None


def get_visual_entity_captioner() -> VisualEntityCaptioner:
    global _singleton
    if _singleton is None:
        try:
            from main.settings import get_settings
            s = get_settings()
            _singleton = VisualEntityCaptioner(
                model=s.visual_entities_model, frames_per_shot=s.visual_entities_frames_per_shot)
        except Exception:
            _singleton = VisualEntityCaptioner()
    return _singleton
