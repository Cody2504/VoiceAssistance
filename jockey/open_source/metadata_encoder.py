"""
Metadata Encoder — generates the [GLOBAL] token from title metadata.

Encodes title-level metadata (title, genre, synopsis, tone) into a single
embedding vector used as the [GLOBAL] context token in the MediaFM Transformer.

Usage:
    encoder = MetadataEncoder(text_embedder)
    global_emb = encoder.encode(title="My Video", genre="action", synopsis="A hero...")
"""
import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class MetadataEncoder:
    """Encodes title metadata into the [GLOBAL] token for the MediaFM Transformer.

    Uses the same TextEmbedder (OpenAI text-embedding-3-large) to encode a
    formatted metadata string. This provides title-level context to every shot
    during the Transformer encoding step.
    """

    def __init__(self, text_embedder):
        """
        Args:
            text_embedder: A TextEmbedder instance (from search.py) or any object
                           with an .encode(text) -> np.ndarray method.
        """
        self.text_embedder = text_embedder

    def _format_metadata(
        self,
        title: str,
        genre: str = "",
        synopsis: str = "",
        tone: str = "",
    ) -> str:
        """Format metadata fields into a single text string for embedding."""
        parts = []
        if title:
            parts.append(f"Title: {title}")
        if genre:
            parts.append(f"Genre: {genre}")
        if tone:
            parts.append(f"Tone: {tone}")
        if synopsis:
            parts.append(f"Synopsis: {synopsis}")
        return ". ".join(parts) if parts else title

    def encode(
        self,
        title: str,
        genre: str = "",
        synopsis: str = "",
        tone: str = "",
    ) -> np.ndarray:
        """Encode title metadata into a normalized embedding vector.

        Args:
            title: Video/movie title.
            genre: Genre tags (e.g. "action, thriller").
            synopsis: Brief synopsis or description.
            tone: Tone descriptors (e.g. "dark, suspenseful").

        Returns:
            Normalized embedding vector [D] (same dim as text embedder output).
        """
        text = self._format_metadata(title, genre, synopsis, tone)
        log.debug(f"Encoding metadata: '{text[:80]}...'")
        return self.text_embedder.encode(text)
