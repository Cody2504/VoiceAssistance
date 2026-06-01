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

        Marengo mode (default):
            CLIP-text encode(query) → 768-d, L2-normalized.
            Same encoder produced the visual side, so dot product is meaningful.

        Legacy modes:
            MediaFM tri-modal: [viclip(768) | zeros(768) | text_emb(3072)] = 4608d
            Legacy concat   : [viclip(768) | text_emb(3072)] = 3840d
        """
        marengo_mode = getattr(self.config, "marengo_mode", True) if self.config is not None else True

        viclip_text_emb = self.viclip.encode_text(query)

        if marengo_mode:
            # Single encoder space — CLIP-text output is already L2-normalized.
            return viclip_text_emb

        # --- legacy concat paths ---
        openrouter_text_emb = self.text_embedder.encode(query)
        if self._mediafm_enabled:
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
            from qdrant_client.models import Range
            filter_conditions.append(
                FieldCondition(key="shot_index", range=Range(gte=0))
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

    async def find_in_transcript(
        self,
        query: str,
        index_id: str,
        video_id: Optional[str] = None,
        top_n: int = 3,
    ) -> str:
        """Find shots whose transcripts mention `query`.

        Hybrid match:
          1. Exact case-insensitive substring → score 1.0 if hit.
          2. Otherwise CLIP-text cosine similarity between query and transcript.

        Args:
            query: Natural language phrase to search for in transcripts.
            index_id: Qdrant collection name.
            video_id: Restrict to a single video. If None, search the whole index.
            top_n: Return the top-N matching shots.

        Returns:
            JSON string with a list of {video_id, start, end, transcript, score}.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        collection_name = self._get_collection_name(index_id)

        filter_conds = [FieldCondition(key="shot_index", range=Range(gte=0))]
        if video_id:
            filter_conds.append(FieldCondition(key="video_id", match=MatchValue(value=video_id)))

        try:
            points, _ = self.qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=filter_conds),
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as e:
            return json.dumps({"error": f"transcript search failed: {e}"})

        shots = []
        for p in points:
            payload = p.payload or {}
            transcript = (payload.get("transcript") or "").strip()
            if not transcript:
                continue
            shots.append({
                "video_id": payload.get("video_id", ""),
                "start": float(payload.get("start", 0.0)),
                "end": float(payload.get("end", 0.0)),
                "transcript": transcript,
                "video_url": payload.get("video_path", ""),
                "video_title": payload.get("title", ""),
            })

        if not shots:
            return json.dumps({
                "message": (
                    "No transcripts found. Either the index has no transcripts "
                    "(set STORE_TRANSCRIPT=true / config.store_transcript=True at "
                    "index time) or the video has no speech."
                ),
                "results": [],
            })

        q_lower = query.lower().strip()

        # --- pass 1: exact substring match (case-insensitive) ---
        substring_hits = []
        for s in shots:
            if q_lower and q_lower in s["transcript"].lower():
                substring_hits.append({**s, "score": 1.0, "match_type": "substring"})

        # --- pass 2: semantic fallback via CLIP-text cosine ---
        semantic_hits = []
        if len(substring_hits) < top_n:
            try:
                q_emb = self.viclip.encode_text(query)               # [D]
                transcript_embs = self.viclip.encode_text_batch(
                    [s["transcript"][:300] for s in shots]            # cap to 300 chars per CLIP-77-token limit
                )                                                     # [N, D]
                scores = transcript_embs @ q_emb                      # cosine since both L2-normalized
                already_idx = {(h["video_id"], h["start"]) for h in substring_hits}
                for s, sc in zip(shots, scores):
                    if (s["video_id"], s["start"]) in already_idx:
                        continue
                    semantic_hits.append({**s, "score": float(sc), "match_type": "semantic"})
            except Exception as e:
                log.warning(f"semantic fallback failed: {e}")

        semantic_hits.sort(key=lambda x: x["score"], reverse=True)
        results = substring_hits + semantic_hits[: max(0, top_n - len(substring_hits))]
        return json.dumps(results[:top_n])

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
