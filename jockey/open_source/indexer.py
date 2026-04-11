"""
Video Indexer — ingests videos into the search pipeline.

Replaces TwelveLabs' managed indexing infrastructure.
Pipeline: Video → Shot Detection → Frame Extraction → Tri-Modal Embeddings → MediaFM Context → Qdrant.

Supports two modes:
  - Legacy mode (mediafm_enabled=False): ViCLIP + text concat, per-shot independent
  - MediaFM mode (mediafm_enabled=True): ViCLIP + audio + text, contextualized via Transformer

Usage:
    indexer = VideoIndexer.from_config(config)
    indexer.create_index("my_index_id")
    indexer.index_video("movie.mp4", index_id="my_index_id", video_id="vid_001")
"""
import logging
import os
import uuid
from typing import Dict, List, Optional, Tuple

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
            duration = _get_video_duration(video_path)
            shots = [(0.0, duration)]
        return shots
    except ImportError:
        log.warning("scenedetect not installed. Treating entire video as one shot. pip install scenedetect[opencv]")
        duration = _get_video_duration(video_path)
        return [(0.0, duration)]


def _get_video_duration(video_path: str) -> float:
    """Get video duration using available libraries (decord or cv2)."""
    try:
        import decord
        vr = decord.VideoReader(video_path, num_threads=1, ctx=decord.cpu(0))
        return len(vr) / vr.get_avg_fps()
    except Exception:
        pass
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            return frame_count / fps
    except Exception:
        pass
    log.warning("Cannot determine video duration, defaulting to 300s")
    return 300.0


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

    Pipeline per video (MediaFM mode):
    1. Shot boundary detection (PySceneDetect)
    2. Per-shot: extract frames → ViCLIP visual embedding [768]
    3. Per-shot: extract audio → wav2vec2 audio embedding [768]
    4. Per-shot: ASR transcript → OpenAI text embedding [3072]
    5. Per-shot: fuse embeddings (concat → [4608])
    6. Whole-video: generate [GLOBAL] token from metadata
    7. Whole-video: contextualize via MediaFM Transformer
    8. Store contextualized embeddings + [CLS] in Qdrant

    Legacy mode (mediafm_enabled=False):
    1-4 same, skip steps 5-7, store raw concat in Qdrant.
    """

    def __init__(
        self,
        viclip_embedder,
        text_embedder,
        asr_engine,
        qdrant_client,
        config,
        audio_encoder=None,
        metadata_encoder=None,
        mediafm_encoder=None,
    ):
        self.viclip = viclip_embedder
        self.text_embedder = text_embedder
        self.asr = asr_engine
        self.qdrant = qdrant_client
        self.config = config
        self.audio_encoder = audio_encoder
        self.metadata_encoder = metadata_encoder
        self.mediafm = mediafm_encoder

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
            api_key=config.openrouter_api_key,
            model=config.text_embedding_model,
            base_url=config.openrouter_base_url,
        )
        asr = ASREngine(model_dir=config.zipformer_model_dir)
        qdrant = QdrantClient(host=config.qdrant_url, port=config.qdrant_port, api_key=config.qdrant_api_key)

        audio_encoder = None
        metadata_encoder = None
        mediafm_encoder = None

        if config.mediafm_enabled:
            from jockey.open_source.audio_encoder import AudioEncoder
            from jockey.open_source.metadata_encoder import MetadataEncoder
            from jockey.open_source.mediafm_encoder import MediaFMEncoderWrapper

            audio_encoder = AudioEncoder(
                model_name=config.audio_encoder_model,
                device=config.audio_encoder_device,
            )
            metadata_encoder = MetadataEncoder(text_embedder=text_embedder)
            mediafm_encoder = MediaFMEncoderWrapper(
                fused_dim=config.fused_embedding_dim,
                hidden_dim=config.mediafm_hidden_dim,
                num_layers=config.mediafm_num_layers,
                num_heads=config.mediafm_num_heads,
                device=config.mediafm_device,
                checkpoint_path=config.mediafm_checkpoint,
            )

        return cls(
            viclip, text_embedder, asr, qdrant, config,
            audio_encoder=audio_encoder,
            metadata_encoder=metadata_encoder,
            mediafm_encoder=mediafm_encoder,
        )

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

    def _fuse_shot_legacy(self, visual_emb, text_emb):
        """Legacy fusion: concat ViCLIP + text, L2 normalize."""
        fused = np.concatenate([visual_emb, text_emb])
        return fused / np.linalg.norm(fused)

    def _fuse_shot_trimodal(self, visual_emb, audio_emb, text_emb):
        """Tri-modal fusion: concat ViCLIP + wav2vec2 + text, L2 normalize."""
        fused = np.concatenate([visual_emb, audio_emb, text_emb])
        return fused / np.linalg.norm(fused)

    def index_video(
        self,
        video_path: str,
        index_id: str,
        video_id: Optional[str] = None,
        title: Optional[str] = None,
        genre: str = "",
        synopsis: str = "",
        tone: str = "",
    ):
        """Index a single video: detect shots → embed each shot → contextualize → store in Qdrant.

        Args:
            video_path: Path to the video file.
            index_id: Index (collection) to add the video to.
            video_id: Optional video ID. Generated if not provided.
            title: Video title for [GLOBAL] token. Defaults to filename.
            genre: Genre metadata for [GLOBAL] token.
            synopsis: Synopsis for [GLOBAL] token.
            tone: Tone metadata for [GLOBAL] token.
        """
        if video_id is None:
            video_id = str(uuid.uuid4())

        if title is None:
            title = os.path.basename(video_path)

        use_mediafm = self.config.mediafm_enabled and self.mediafm is not None

        log.info(f"Indexing video: {video_path} → index={index_id}, video_id={video_id}")
        log.info(f"  Mode: {'MediaFM (tri-modal + context)' if use_mediafm else 'Legacy (ViCLIP + text)'}")

        # 1. Detect shots
        shots = detect_shots(video_path, threshold=self.config.shot_detection_threshold)
        log.info(f"  Detected {len(shots)} shots")

        # 2. Encode each shot
        raw_embeddings = []
        shot_metadata = []

        for i, (start, end) in enumerate(shots):
            # Visual embedding
            frames = extract_frames(video_path, start, end, max_frames=self.config.max_frames_per_shot)
            visual_emb = self.viclip.encode_video(frames)  # [768]

            # ASR transcript
            transcript = self.asr.transcribe(video_path, start_sec=start, end_sec=end)

            # Text embedding
            text_to_embed = transcript if transcript else os.path.basename(video_path)
            text_emb = self.text_embedder.encode(text_to_embed)  # [3072]

            if use_mediafm:
                # Audio embedding
                audio_emb = self.audio_encoder.encode_audio(video_path, start_sec=start, end_sec=end)  # [768]
                fused = self._fuse_shot_trimodal(visual_emb, audio_emb, text_emb)
            else:
                fused = self._fuse_shot_legacy(visual_emb, text_emb)

            raw_embeddings.append(fused)
            shot_metadata.append({
                "shot_index": i,
                "start": start,
                "end": end,
                "transcript": transcript,
            })

            log.info(
                f"  Shot {i}: [{start:.1f}s - {end:.1f}s] transcript='{transcript[:50]}...' "
                if transcript else f"  Shot {i}: [{start:.1f}s - {end:.1f}s] (no transcript)"
            )

        # 3. Contextualize with MediaFM (if enabled)
        cls_embedding = None
        if use_mediafm and len(raw_embeddings) > 0:
            log.info(f"  Running MediaFM context encoder on {len(raw_embeddings)} shots...")

            # Generate [GLOBAL] token from title metadata
            global_emb = None
            if self.metadata_encoder is not None:
                global_emb = self.metadata_encoder.encode(
                    title=title, genre=genre, synopsis=synopsis, tone=tone,
                )
                # Pad global_emb to fused_dim if it's only text_embedding_dim
                if len(global_emb) < self.config.fused_embedding_dim:
                    padding = np.zeros(self.config.fused_embedding_dim - len(global_emb), dtype=np.float32)
                    global_emb = np.concatenate([padding, global_emb])
                    global_emb = global_emb / np.linalg.norm(global_emb)

            # Contextualize all shots together
            final_embeddings, cls_embedding = self.mediafm.contextualize(
                shot_embeddings=raw_embeddings,
                global_embedding=global_emb,
            )
        else:
            final_embeddings = raw_embeddings

        # 4. Store in Qdrant
        collection_name = f"index_{index_id}"
        from qdrant_client.models import PointStruct

        points = []
        for i, (emb, meta) in enumerate(zip(final_embeddings, shot_metadata)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{video_id}_shot_{i}"))
            payload = {
                "video_id": video_id,
                "index_id": index_id,
                "shot_index": meta["shot_index"],
                "start": meta["start"],
                "end": meta["end"],
                "transcript": meta["transcript"],
                "video_path": video_path,
                "title": title,
                "mediafm_contextualized": use_mediafm,
            }
            points.append(PointStruct(
                id=point_id,
                vector=emb.tolist(),
                payload=payload,
            ))

        # Store video-level [CLS] embedding if available
        if cls_embedding is not None:
            cls_point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{video_id}_cls"))
            points.append(PointStruct(
                id=cls_point_id,
                vector=cls_embedding.tolist(),
                payload={
                    "video_id": video_id,
                    "index_id": index_id,
                    "shot_index": -1,  # sentinel for CLS
                    "start": shots[0][0] if shots else 0.0,
                    "end": shots[-1][1] if shots else 0.0,
                    "transcript": "",
                    "video_path": video_path,
                    "title": title,
                    "is_cls_embedding": True,
                    "mediafm_contextualized": True,
                },
            ))

        # Batch upsert
        if points:
            self.qdrant.upsert(collection_name=collection_name, points=points)
            log.info(f"  Indexed {len(points)} points into '{collection_name}'")

    def delete_index(self, index_id: str):
        """Delete a video index (Qdrant collection)."""
        collection_name = f"index_{index_id}"
        self.qdrant.delete_collection(collection_name=collection_name)
        log.info(f"Deleted Qdrant collection '{collection_name}'")
