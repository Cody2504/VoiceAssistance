"""
Qdrant-based video search module.
Replaces TwelveLabs Search API with local vector similarity search.

Usage:
    search = VideoSearch(qdrant_client, viclip_embedder, text_embedder)
    results = await search.search("a dog playing fetch", index_id="abc123", top_n=5)
"""
import json
import logging
import os
from typing import Dict, List, Optional, Union

import numpy as np

log = logging.getLogger(__name__)


class TextEmbedder:
    """OpenAI text-embedding-3-large wrapper."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-large"):
        self.model = model
        self._client = None
        self._api_key = api_key

    def _lazy_load(self):
        if self._client is not None:
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
            log.info(f"OpenAI text embedding client initialized (model={self.model})")
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
        self._lazy_load()

        if self._client == "unavailable":
            emb = np.random.randn(3072).astype(np.float32)
            return emb / np.linalg.norm(emb)

        try:
            response = self._client.embeddings.create(input=text, model=self.model)
            emb = np.array(response.data[0].embedding, dtype=np.float32)
            return emb / np.linalg.norm(emb)
        except Exception as e:
            log.warning(f"OpenAI embedding call failed: {e}. Using random fallback.")
            emb = np.random.randn(3072).astype(np.float32)
            return emb / np.linalg.norm(emb)


class VideoSearch:
    """Video search using ViCLIP visual embeddings + OpenAI text embeddings + Qdrant."""

    def __init__(self, qdrant_client, viclip_embedder, text_embedder: TextEmbedder):
        self.qdrant = qdrant_client
        self.viclip = viclip_embedder
        self.text_embedder = text_embedder

    def _get_collection_name(self, index_id: str) -> str:
        return f"index_{index_id}"

    async def search(
        self,
        query: str,
        index_id: str,
        top_n: int = 3,
        group_by: str = "clip",
        video_filter: Optional[List[str]] = None,
    ) -> str:
        """Search indexed videos using text query.

        Uses ViCLIP text encoder for visual-semantic matching
        plus OpenAI text embeddings for transcript matching.

        Args:
            query: Natural language search query.
            index_id: Index (collection) to search in.
            top_n: Number of results to return.
            group_by: "clip" for segments, "video" for whole videos.
            video_filter: Optional list of video IDs to restrict search to.

        Returns:
            JSON string with search results.
        """
        # Encode query with both encoders and fuse
        viclip_text_emb = self.viclip.encode_text(query)
        openai_text_emb = self.text_embedder.encode(query)
        query_vector = np.concatenate([viclip_text_emb, openai_text_emb])
        query_vector = query_vector / np.linalg.norm(query_vector)

        # Build Qdrant filter
        search_filter = None
        if video_filter:
            from qdrant_client.models import Filter, FieldCondition, MatchAny
            search_filter = Filter(must=[
                FieldCondition(key="video_id", match=MatchAny(any=video_filter))
            ])

        # Search
        collection_name = self._get_collection_name(index_id)
        try:
            response = self.qdrant.query_points(
                collection_name=collection_name,
                query=query_vector.tolist(),
                limit=top_n * 3 if group_by == "video" else top_n,
                query_filter=search_filter,
            )
            results = response.points
        except Exception as e:
            return json.dumps({
                "message": f"Search error: {str(e)}",
                "error": str(e),
            })

        # Format results
        if group_by == "video":
            # Deduplicate by video_id, keep best score per video
            seen_videos = {}
            for r in results:
                vid = r.payload.get("video_id", "")
                if vid not in seen_videos or r.score > seen_videos[vid]["score"]:
                    seen_videos[vid] = {
                        "video_id": vid,
                        "score": r.score,
                        "video_url": r.payload.get("video_path", ""),
                        "video_title": r.payload.get("title", ""),
                    }
            top_results = sorted(seen_videos.values(), key=lambda x: x["score"], reverse=True)[:top_n]
        else:
            top_results = [{
                "video_id": r.payload.get("video_id", ""),
                "start": r.payload.get("start", 0),
                "end": r.payload.get("end", 0),
                "score": r.score,
                "video_url": r.payload.get("video_path", ""),
                "video_title": r.payload.get("title", ""),
                "transcript": r.payload.get("transcript", ""),
            } for r in results[:top_n]]

        return json.dumps(top_results)

    def get_video_metadata(self, index_id: str, video_id: str) -> dict:
        """Get metadata for a specific video from Qdrant."""
        collection_name = self._get_collection_name(index_id)
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results, _ = self.qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=[
                    FieldCondition(key="video_id", match=MatchValue(value=video_id))
                ]),
                limit=1,
            )
            if results:
                return results[0].payload
        except Exception as e:
            log.warning(f"Failed to get video metadata: {e}")

        return {"message": f"Video {video_id} not found in index {index_id}"}
