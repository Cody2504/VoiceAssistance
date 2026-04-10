"""
Video Indexer — ingests videos into the search pipeline.

Replaces TwelveLabs' managed indexing infrastructure.
Pipeline: Video → Shot Detection → Frame Extraction → Embeddings → Qdrant.

Usage:
    indexer = VideoIndexer.from_config(config)
    indexer.create_index("my_index_id")
    indexer.index_video("movie.mp4", index_id="my_index_id", video_id="vid_001")
"""
import logging
import os
import uuid
from typing import List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


def detect_shots(video_path: str, threshold: float = 27.0) -> List[Tuple[float, float]]:
    """Detect shot boundaries in a video using PySceneDetect.

    Args:
        video_path: Path to video file.
        threshold: Content detection threshold (lower = more sensitive).

    Returns:
        List of (start_sec, end_sec) tuples for each shot.
    """
    try:
        from scenedetect import detect, ContentDetector
        scene_list = detect(video_path, ContentDetector(threshold=threshold))
        shots = [(s.get_seconds(), e.get_seconds()) for s, e in scene_list]
        if not shots:
            # Single-shot video (no scene changes detected)
            import subprocess
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", video_path],
                capture_output=True, text=True,
            )
            duration = float(result.stdout.strip())
            shots = [(0.0, duration)]
        return shots
    except ImportError:
        log.warning("scenedetect not installed. Treating entire video as one shot. pip install scenedetect[opencv]")
        return [(0.0, 300.0)]  # fallback: assume 5-min video


def extract_frames(video_path: str, start_sec: float, end_sec: float, max_frames: int = 8) -> np.ndarray:
    """Extract uniformly sampled frames from a video segment.

    Args:
        video_path: Path to video file.
        start_sec: Start time in seconds.
        end_sec: End time in seconds.
        max_frames: Maximum number of frames to extract.

    Returns:
        Frames as numpy array [N, H, W, 3] (uint8, RGB).
    """
    try:
        import decord
        from decord import VideoReader, cpu

        vr = VideoReader(video_path, num_threads=1, ctx=cpu(0))
        fps = vr.get_avg_fps()

        start_frame = int(start_sec * fps)
        end_frame = min(int(end_sec * fps), len(vr))
        total_frames = end_frame - start_frame

        if total_frames <= 0:
            total_frames = len(vr)
            start_frame = 0
            end_frame = total_frames

        n_frames = min(max_frames, total_frames)
        indices = np.linspace(start_frame, end_frame - 1, n_frames, dtype=int)
        frames = vr.get_batch(indices).asnumpy()  # [N, H, W, 3]
        return frames

    except ImportError:
        log.warning("decord not installed. Returning placeholder frames. pip install decord")
        return np.zeros((max_frames, 224, 224, 3), dtype=np.uint8)


class VideoIndexer:
    """Indexes videos into Qdrant for the open-source Jockey pipeline.

    Pipeline per video:
    1. Shot boundary detection (PySceneDetect)
    2. Per-shot: extract frames → ViCLIP visual embedding
    3. Per-shot: extract audio → ZipFormer ASR → OpenAI text embedding
    4. Fuse embeddings (concat + L2 normalize)
    5. Store in Qdrant with metadata
    """

    def __init__(self, viclip_embedder, text_embedder, asr_engine, qdrant_client, config):
        self.viclip = viclip_embedder
        self.text_embedder = text_embedder
        self.asr = asr_engine
        self.qdrant = qdrant_client
        self.config = config

    @classmethod
    def from_config(cls, config):
        """Create a VideoIndexer from a PipelineConfig."""
        from jockey.open_source.viclip_embedder import ViCLIPEmbedder
        from jockey.open_source.search import TextEmbedder
        from jockey.open_source.asr import ASREngine
        from qdrant_client import QdrantClient

        viclip = ViCLIPEmbedder(
            model_name_or_path=config.viclip_model_name,
            device=config.viclip_device,
        )
        text_embedder = TextEmbedder(
            api_key=config.openai_api_key,
            model=config.text_embedding_model,
        )
        asr = ASREngine(model_dir=config.zipformer_model_dir)
        qdrant = QdrantClient(host=config.qdrant_url, port=config.qdrant_port, api_key=config.qdrant_api_key)

        return cls(viclip, text_embedder, asr, qdrant, config)

    def create_index(self, index_id: str):
        """Create a new Qdrant collection for a video index."""
        from qdrant_client.models import VectorParams, Distance

        collection_name = f"index_{index_id}"
        self.qdrant.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self.config.fused_embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        log.info(f"Created Qdrant collection '{collection_name}' (dim={self.config.fused_embedding_dim})")

    def index_video(self, video_path: str, index_id: str, video_id: Optional[str] = None):
        """Index a single video: detect shots → embed each shot → store in Qdrant.

        Args:
            video_path: Path to the video file.
            index_id: Index (collection) to add the video to.
            video_id: Optional video ID. Generated if not provided.
        """
        if video_id is None:
            video_id = str(uuid.uuid4())

        log.info(f"Indexing video: {video_path} → index={index_id}, video_id={video_id}")

        # 1. Detect shots
        shots = detect_shots(video_path, threshold=self.config.shot_detection_threshold)
        log.info(f"  Detected {len(shots)} shots")

        collection_name = f"index_{index_id}"
        from qdrant_client.models import PointStruct

        points = []
        for i, (start, end) in enumerate(shots):
            # 2. Extract frames for visual embedding
            frames = extract_frames(video_path, start, end, max_frames=self.config.max_frames_per_shot)
            visual_emb = self.viclip.encode_video(frames)  # [768]

            # 3. ASR for transcript
            transcript = self.asr.transcribe(video_path, start_sec=start, end_sec=end)

            # 4. Text embedding of transcript
            text_to_embed = transcript if transcript else os.path.basename(video_path)
            text_emb = self.text_embedder.encode(text_to_embed)  # [3072]

            # 5. Fuse: concat + L2 normalize
            fused = np.concatenate([visual_emb, text_emb])
            fused = fused / np.linalg.norm(fused)

            # 6. Create point
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{video_id}_shot_{i}"))
            points.append(PointStruct(
                id=point_id,
                vector=fused.tolist(),
                payload={
                    "video_id": video_id,
                    "index_id": index_id,
                    "shot_index": i,
                    "start": start,
                    "end": end,
                    "transcript": transcript,
                    "video_path": video_path,
                    "title": os.path.basename(video_path),
                },
            ))

            log.info(f"  Shot {i}: [{start:.1f}s - {end:.1f}s] transcript='{transcript[:50]}...' " if transcript else f"  Shot {i}: [{start:.1f}s - {end:.1f}s] (no transcript)")

        # Batch upsert
        if points:
            self.qdrant.upsert(collection_name=collection_name, points=points)
            log.info(f"  Indexed {len(points)} shots into '{collection_name}'")

    def delete_index(self, index_id: str):
        """Delete a video index (Qdrant collection)."""
        collection_name = f"index_{index_id}"
        self.qdrant.delete_collection(collection_name=collection_name)
        log.info(f"Deleted Qdrant collection '{collection_name}'")
