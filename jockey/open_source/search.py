"""
Qdrant-based video search module.
Replaces TwelveLabs Search API with local vector similarity search.

Text embeddings use OpenRouter API (openai/text-embedding-3-large).

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
        self._lazy_load()

        if self._client == "unavailable":
            emb = np.random.randn(3072).astype(np.float32)
            return emb / np.linalg.norm(emb)

        try:
            response = self._client.embeddings.create(input=text, model=self.model)
            emb = np.array(response.data[0].embedding, dtype=np.float32)
            return emb / np.linalg.norm(emb)
        except Exception as e:
            log.warning(f"OpenRouter embedding call failed: {e}. Using random fallback.")
            emb = np.random.randn(3072).astype(np.float32)
            return emb / np.linalg.norm(emb)


class VideoSearch:
    """Video search using ViCLIP visual embeddings + OpenRouter text embeddings + Qdrant.

    When mediafm_enabled, the search query is also expanded to match the tri-modal
    fused embedding dimension (ViCLIP + wav2vec2 + text = 4608).
    """

    def __init__(
        self,
        qdrant_client,
        viclip_embedder,
        text_embedder: TextEmbedder,
        audio_encoder=None,
        config=None,
    ):
        self.qdrant = qdrant_client
        self.viclip = viclip_embedder
        self.text_embedder = text_embedder
        self.audio_encoder = audio_encoder
        self.config = config

    @property
    def _mediafm_enabled(self) -> bool:
        return self.config is not None and self.config.mediafm_enabled and self.audio_encoder is not None

    def _get_collection_name(self, index_id: str) -> str:
        return f"index_{index_id}"

    def _build_query_vector(self, query: str) -> np.ndarray:
        """Build a query vector matching the indexed embedding dimension.

        For MediaFM (tri-modal) mode:
            [viclip_text_emb (768)] + [zeros (768, audio placeholder)] + [openrouter_text_emb (3072)]
            = 4608 dims

        For legacy mode:
            [viclip_text_emb (768)] + [openrouter_text_emb (3072)]
            = 3840 dims
        """
        viclip_text_emb = self.viclip.encode_text(query)
        openrouter_text_emb = self.text_embedder.encode(query)

        if self._mediafm_enabled:
            # For text queries, we don't have audio — use zeros for the audio slot
            audio_placeholder = np.zeros(self.config.audio_embedding_dim, dtype=np.float32)
            query_vector = np.concatenate([viclip_text_emb, audio_placeholder, openrouter_text_emb])
        else:
            query_vector = np.concatenate([viclip_text_emb, openrouter_text_emb])

        return query_vector / np.linalg.norm(query_vector)

    async def search(
        self,
        query: str,
        index_id: str,
        top_n: int = 3,
        group_by: str = "clip",
        video_filter: Optional[List[str]] = None,
    ) -> str:
        """Search indexed videos using text query.

        Args:
            query: Natural language search query.
            index_id: Index (collection) to search in.
            top_n: Number of results to return.
            group_by: "clip" for segments, "video" for whole videos.
            video_filter: Optional list of video IDs to restrict search to.

        Returns:
            JSON string with search results.
        """
        query_vector = self._build_query_vector(query)

        # Build Qdrant filter — exclude CLS embeddings from shot-level search
        from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

        filter_conditions = []

        # Exclude CLS embeddings (shot_index == -1) for clip-level search
        if group_by == "clip":
            filter_conditions.append(
                FieldCondition(key="is_cls_embedding", match=MatchValue(value=False))
            )

        if video_filter:
            filter_conditions.append(
                FieldCondition(key="video_id", match=MatchAny(any=video_filter))
            )

        search_filter = Filter(must=filter_conditions) if filter_conditions else None

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
                "contextualized": r.payload.get("mediafm_contextualized", False),
            } for r in results[:top_n]]

        return json.dumps(top_results)

    async def search_similar_videos(
        self,
        video_id: str,
        index_id: str,
        top_n: int = 3,
    ) -> str:
        """Find videos similar to a given video using [CLS] embeddings.

        Only works when MediaFM mode was used during indexing.
        """
        collection_name = self._get_collection_name(index_id)

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results, _ = self.qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=[
                    FieldCondition(key="video_id", match=MatchValue(value=video_id)),
                    FieldCondition(key="is_cls_embedding", match=MatchValue(value=True)),
                ]),
                limit=1,
                with_vectors=True,
            )
            if not results:
                return json.dumps({"error": f"No CLS embedding found for video {video_id}."})

            cls_vector = results[0].vector
        except Exception as e:
            return json.dumps({"error": f"Failed to retrieve CLS embedding: {e}"})

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            response = self.qdrant.query_points(
                collection_name=collection_name,
                query=cls_vector,
                limit=top_n + 1,
                query_filter=Filter(must=[
                    FieldCondition(key="is_cls_embedding", match=MatchValue(value=True)),
                ]),
            )
            similar = [{
                "video_id": r.payload.get("video_id", ""),
                "score": r.score,
                "video_url": r.payload.get("video_path", ""),
                "video_title": r.payload.get("title", ""),
            } for r in response.points if r.payload.get("video_id") != video_id][:top_n]

            return json.dumps(similar)
        except Exception as e:
            return json.dumps({"error": f"Video similarity search failed: {e}"})

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
