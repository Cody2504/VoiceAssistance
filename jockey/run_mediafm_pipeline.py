"""
MediaFM Pipeline — End-to-End Run Script

Demonstrates the full MediaFM-inspired pipeline:
  1. Create an index
  2. Index one or more videos (tri-modal + Transformer contextualization)
  3. Search with a text query
  4. Video Q&A (text generation)

Usage:
    # Basic — index a video and search (uses placeholder models if GPU not available)
    python run_mediafm_pipeline.py --video path/to/video.mp4

    # With real models on GPU
    python run_mediafm_pipeline.py --video path/to/video.mp4 --device cuda

    # Index multiple videos
    python run_mediafm_pipeline.py --video vid1.mp4 vid2.mp4 vid3.mp4

    # Search only (skip indexing)
    python run_mediafm_pipeline.py --search-only --query "a person running" --index-id my_index

    # Disable MediaFM Transformer (use legacy flat embeddings)
    python run_mediafm_pipeline.py --video path/to/video.mp4 --no-mediafm
"""
import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import uuid

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mediafm_pipeline")

# Suppress noisy third-party loggers
for _logger_name in (
    "httpx", "httpcore", "huggingface_hub", "transformers",
    "pyscenedetect", "urllib3", "filelock", "accelerate",
    "jockey.open_source",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

# Suppress transformers load reports, progress bars, and deprecation warnings
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*unauthenticated.*")


def create_test_video(output_path: str, duration: float = 10.0, scenes: int = 3) -> str:
    """Create a test video with multiple scene changes using ffmpeg.

    Generates a video with colored segments (blue → red → green) to trigger
    shot detection, plus a sine tone audio track.
    """
    if not _has_ffmpeg():
        log.warning("ffmpeg not found — cannot create test video")
        return ""

    # Create a video with scene changes via filter_complex
    colors = ["blue", "red", "green", "yellow", "purple"]
    seg_duration = duration / scenes

    filter_parts = []
    for i in range(scenes):
        color = colors[i % len(colors)]
        filter_parts.append(
            f"color=c={color}:size=320x240:duration={seg_duration}:rate=24[v{i}]"
        )

    concat_inputs = "".join(f"[v{i}]" for i in range(scenes))
    filter_complex = ";".join(filter_parts) + f";{concat_inputs}concat=n={scenes}:v=1:a=0[outv]"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "0:a",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest", "-loglevel", "quiet",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        log.info(f"Created test video: {output_path} ({duration}s, {scenes} scenes)")
        return output_path
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to create test video: {e}")
        return ""


def _has_ffmpeg() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None


def print_banner():
    banner = """
+==============================================================+
|         MediaFM-Inspired Video Understanding Pipeline        |
|                                                              |
|   Tri-Modal:  CLIP (video) + wav2vec2 (audio) + text      |
|   Context:    Transformer Encoder (3L, 8H)                   |
|   API:        OpenRouter (embeddings + VLM)                  |
|   Video QA:   qwen/qwen3-vl-8b-instruct (via OpenRouter)    |
+==============================================================+
"""
    print(banner)


async def run_pipeline(args):
    """Run the full MediaFM pipeline."""
    print_banner()

    # --- Config ---
    from jockey.open_source.config import PipelineConfig

    config = PipelineConfig()
    config.mediafm_enabled = not args.no_mediafm
    config.viclip_device = args.device
    config.audio_encoder_device = args.device
    config.mediafm_device = args.device

    log.info("=" * 60)
    log.info("CONFIGURATION")
    log.info("=" * 60)
    log.info(f"  MediaFM Transformer: {'ENABLED' if config.mediafm_enabled else 'DISABLED (legacy mode)'}")
    log.info(f"  ViCLIP model:        {config.viclip_model_name}")
    log.info(f"  Audio encoder:       {config.audio_encoder_model}")
    log.info(f"  Text embedding:      {config.text_embedding_model}")
    log.info(f"  Fused dimension:     {config.fused_embedding_dim}")
    log.info(f"  Device:              {args.device}")
    log.info(f"  Qdrant:              {'in-memory' if args.qdrant_memory else f'{config.qdrant_url}:{config.qdrant_port}'}")

    # --- Build components manually (for in-memory Qdrant support) ---
    log.info("")
    log.info("=" * 60)
    log.info("LOADING MODELS")
    log.info("=" * 60)

    from jockey.open_source.viclip_embedder import ViCLIPEmbedder
    from jockey.open_source.search import TextEmbedder, VideoSearch
    from jockey.open_source.asr import ASREngine
    from jockey.open_source.indexer import VideoIndexer

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

    # Qdrant — in-memory or server
    if args.qdrant_memory:
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(":memory:")
        log.info("  Qdrant: in-memory mode")
    else:
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(host=config.qdrant_url, port=config.qdrant_port, api_key=config.qdrant_api_key)
        log.info(f"  Qdrant: {config.qdrant_url}:{config.qdrant_port}")

    # MediaFM components
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

    # Build indexer
    indexer = VideoIndexer(
        viclip_embedder=viclip,
        text_embedder=text_embedder,
        asr_engine=asr,
        qdrant_client=qdrant,
        config=config,
        audio_encoder=audio_encoder,
        metadata_encoder=metadata_encoder,
        mediafm_encoder=mediafm_encoder,
    )

    # Build search
    search = VideoSearch(
        qdrant_client=qdrant,
        viclip_embedder=viclip,
        text_embedder=text_embedder,
        audio_encoder=audio_encoder,
        config=config,
    )

    index_id = args.index_id or str(uuid.uuid4())[:8]

    # --- Indexing ---
    if not args.search_only:
        log.info("")
        log.info("=" * 60)
        log.info("INDEXING")
        log.info("=" * 60)

        # Resolve video paths
        video_paths = args.video or []
        if not video_paths and not args.search_only:
            # Create a test video if none provided
            log.info("No video provided — creating a test video...")
            test_path = os.path.join(tempfile.gettempdir(), "mediafm_test_video.mp4")
            test_path = create_test_video(test_path, duration=10.0, scenes=3)
            if test_path:
                video_paths = [test_path]
            else:
                log.error("Cannot create test video (ffmpeg not found). Provide --video path.")
                return

        # Create index
        indexer.create_index(index_id)
        log.info(f"  Index ID: {index_id}")

        # Index each video
        for i, video_path in enumerate(video_paths):
            if not os.path.isfile(video_path):
                log.warning(f"  Video not found: {video_path} — skipping")
                continue

            vid_id = f"vid_{i:03d}"
            title = os.path.splitext(os.path.basename(video_path))[0]

            log.info(f"\n  [{i+1}/{len(video_paths)}] Indexing: {video_path}")
            indexer.index_video(
                video_path=video_path,
                index_id=index_id,
                video_id=vid_id,
                title=title,
                genre=args.genre,
                synopsis=args.synopsis,
            )

    # --- Search ---
    log.info("")
    log.info("=" * 60)
    log.info("SEARCH")
    log.info("=" * 60)

    queries = args.query or ["a person doing something", "dramatic scene", "action sequence"]
    for query in queries:
        log.info(f"\n  Query: \"{query}\"")

        # Clip-level search
        results_json = await search.search(query, index_id=index_id, top_n=args.top_n, group_by="clip")
        results = json.loads(results_json)

        if isinstance(results, list):
            log.info(f"  Found {len(results)} results:")
            for r in results:
                ctx = " [contextualized]" if r.get("contextualized") else ""
                log.info(
                    f"    → score={r['score']:.4f} | {r['video_title']} "
                    f"[{r.get('start', 0):.1f}s - {r.get('end', 0):.1f}s]{ctx}"
                )
                if r.get("transcript"):
                    log.info(f"      transcript: \"{r['transcript'][:80]}\"")
        else:
            log.warning(f"  Search returned error: {results}")

    # --- Video Q&A (if requested) ---
    if args.qa_prompt and args.video:
        log.info("")
        log.info("=" * 60)
        log.info("VIDEO Q&A")
        log.info("=" * 60)

        from jockey.open_source.video_qa import VideoQA
        qa = VideoQA.from_config(config)

        for video_path in args.video:
            if not os.path.isfile(video_path):
                continue
            log.info(f"\n  Video: {video_path}")
            log.info(f"  Prompt: \"{args.qa_prompt}\"")
            answer = await qa.freeform(video_path=video_path, prompt=args.qa_prompt)
            parsed = json.loads(answer)
            log.info(f"  Answer: {parsed.get('text', 'N/A')}")

    # --- Summary ---
    log.info("")
    log.info("=" * 60)
    log.info("PIPELINE RUN COMPLETE")
    log.info("=" * 60)
    log.info(f"  Index ID:     {index_id}")
    log.info(f"  Mode:         {'MediaFM (tri-modal + context)' if config.mediafm_enabled else 'Legacy'}")
    log.info(f"  Embedding dim: {config.fused_embedding_dim}")
    if not args.search_only:
        log.info(f"  Videos indexed: {len(video_paths)}")
    log.info(f"  Queries run:  {len(queries)}")


def main():
    parser = argparse.ArgumentParser(
        description="MediaFM-Inspired Video Understanding Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index a video and search with test queries
  python run_mediafm_pipeline.py --video movie.mp4

  # Index with metadata for better [GLOBAL] context
  python run_mediafm_pipeline.py --video movie.mp4 --genre "action,thriller" --synopsis "A hero saves the world"

  # Use legacy mode (no Transformer contextualization)
  python run_mediafm_pipeline.py --video movie.mp4 --no-mediafm

  # Search an existing index
  python run_mediafm_pipeline.py --search-only --index-id abc123 --query "car chase"

  # Run video Q&A
  python run_mediafm_pipeline.py --video clip.mp4 --qa-prompt "What is happening in this video?"

  # Run demo with auto-generated test video (no GPU needed)
  python run_mediafm_pipeline.py --device cpu --qdrant-memory
        """,
    )

    # Input
    parser.add_argument("--video", nargs="+", help="Video file(s) to index")
    parser.add_argument("--index-id", default=None, help="Index ID (auto-generated if not set)")

    # Metadata for [GLOBAL] token
    parser.add_argument("--genre", default="", help="Genre metadata (e.g. 'action,thriller')")
    parser.add_argument("--synopsis", default="", help="Synopsis for the video")

    # Search
    parser.add_argument("--query", nargs="+", help="Search query/queries")
    parser.add_argument("--top-n", type=int, default=3, help="Number of search results")
    parser.add_argument("--search-only", action="store_true", help="Skip indexing, search existing index")

    # Video Q&A
    parser.add_argument("--qa-prompt", default=None, help="If set, run video Q&A with this prompt")

    # Pipeline mode
    parser.add_argument("--no-mediafm", action="store_true",
                        help="Disable MediaFM Transformer (use legacy flat embeddings)")

    # Hardware
    parser.add_argument("--device", default="cpu", help="Device for models (cpu/cuda)")
    parser.add_argument("--qdrant-memory", action="store_true", default=True,
                        help="Use Qdrant in-memory (no server needed)")
    parser.add_argument("--qdrant-server", dest="qdrant_memory", action="store_false",
                        help="Connect to Qdrant server")

    args = parser.parse_args()

    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
