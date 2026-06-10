"""
Text embedding client shared by ingest, analyze, grounding, KG, timeline and
the `when` fan-out (OpenRouter API, openai/text-embedding-3-large).
"""
import logging
from typing import List

import numpy as np

log = logging.getLogger(__name__)


class TextEmbedder:
    """Text embedder using OpenRouter API (OpenAI-compatible endpoint).

    Uses openai/text-embedding-3-large via OpenRouter by default.
    Falls back to random embeddings if API key is not set.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "openai/text-embedding-3-large",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.model = model
        self.base_url = base_url
        self._client = None
        self._api_key = api_key

    def _lazy_load(self):
        if self._client is not None:
            return
        if not self._api_key:
            log.warning("OPENROUTER_API_KEY not set. Text embeddings will use random fallback.")
            self._client = "unavailable"
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self.base_url,
            )
            log.info(f"OpenRouter text embedding client initialized (model={self.model})")
        except ImportError:
            log.warning("openai package not installed. pip install openai")
            self._client = "unavailable"

    def encode(self, text: str) -> np.ndarray:
        """Encode text into a normalized embedding vector.

        Args:
            text: Input text string.

        Returns:
            Normalized embedding vector [3072] for text-embedding-3-large.
        """
        return self.encode_batch([text])[0]

    def encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Encode multiple texts in a single API call.

        OpenAI / text-embedding-3-large accepts up to 2048 inputs per request.
        Batching is essential for feature extraction (16-30 windows per video × 6700 videos
        → 100k+ embeddings; serial calls take 30+ hours, batched takes ~1).

        Returns list of normalized embedding vectors, one per input text.
        """
        self._lazy_load()

        # Replace empty / whitespace-only inputs with a single space to satisfy API.
        safe_texts = [t if (t and t.strip()) else " " for t in texts]

        if self._client == "unavailable":
            return [
                np.random.randn(3072).astype(np.float32) / np.sqrt(3072)
                for _ in safe_texts
            ]

        try:
            response = self._client.embeddings.create(input=safe_texts, model=self.model)
            out: List[np.ndarray] = []
            for d in response.data:
                e = np.array(d.embedding, dtype=np.float32)
                n = np.linalg.norm(e)
                out.append(e / n if n > 0 else e)
            return out
        except Exception as e:
            log.warning(
                f"OpenRouter batch embedding call failed ({len(safe_texts)} texts): {e}. "
                f"Using random fallback for this batch."
            )
            return [
                np.random.randn(3072).astype(np.float32) / np.sqrt(3072)
                for _ in safe_texts
            ]
