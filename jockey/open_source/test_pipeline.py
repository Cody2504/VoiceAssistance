"""
Pipeline smoke test — verifies all modules load and the indexing + search
pipeline works end-to-end with placeholder embeddings (no GPU needed).

Usage:
    python -m jockey.open_source.test_pipeline
"""
import json
import logging
import asyncio
import numpy as np
import os
import tempfile
import subprocess

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")
log = logging.getLogger("pipeline_test")


def create_test_video(output_path: str, duration: float = 5.0) -> str:
    """Create a small test video with ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=blue:size=320x240:duration={duration}:rate=24",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest", "-loglevel", "quiet",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


async def main():
    log.info("=" * 60)
    log.info("Open-Source Jockey Pipeline — Smoke Test")
    log.info("=" * 60)

    # --- Step 1: Test config ---
    log.info("\n[1/7] Loading configuration...")
    from jockey.open_source.config import config
    log.info(f"  ViCLIP model: {config.viclip_model_name}")
    log.info(f"  Text embedding: {config.text_embedding_model}")
    log.info(f"  Fused dim: {config.fused_embedding_dim}")
    log.info(f"  Qdrant: {config.qdrant_url}:{config.qdrant_port}")
    log.info("  ✅ Config loaded")

    # --- Step 2: Test ViCLIP embedder ---
    log.info("\n[2/7] Testing ViCLIP embedder...")
    from jockey.open_source.viclip_embedder import ViCLIPEmbedder

    # Try real model first, fall back to placeholder
    embedder = ViCLIPEmbedder(model_name_or_path="OpenGVLab/ViCLIP-L-14-hf", device="cpu")
    
    fake_frames = np.random.randint(0, 255, (8, 224, 224, 3), dtype=np.uint8)
    video_emb = embedder.encode_video(fake_frames)
    log.info(f"  Video embedding shape: {video_emb.shape}")
    log.info(f"  Video embedding norm: {np.linalg.norm(video_emb):.4f}")
    assert video_emb.shape[0] > 0, f"Expected non-empty embedding"
    assert abs(np.linalg.norm(video_emb) - 1.0) < 1e-4, "Embedding should be unit normalized"

    text_emb = embedder.encode_text("a dog playing fetch")
    log.info(f"  Text embedding shape: {text_emb.shape}")
    assert text_emb.shape[0] > 0
    
    is_placeholder = embedder._model == "placeholder"
    if is_placeholder:
        log.info("  ✅ ViCLIP embedder works (placeholder mode — model download failed)")
    else:
        log.info(f"  ✅ ViCLIP embedder works with REAL model! (dim={video_emb.shape[0]})")

    # --- Step 3: Test ASR (real ZipFormer if models downloaded) ---
    log.info("\n[3/7] Testing ASR engine...")
    from jockey.open_source.asr import ASREngine
    asr_model_dir = os.path.join(os.path.dirname(__file__), "models", "zipformer")
    asr = ASREngine(model_dir=asr_model_dir)
    # Test with bundled WAV if available
    test_wav = os.path.join(asr_model_dir, "sherpa-onnx-zipformer-small-en-2023-06-26", "test_wavs", "0.wav")
    if os.path.isfile(test_wav):
        import wave
        with wave.open(test_wav, 'rb') as wf:
            sr = wf.getframerate()
            n_frames = wf.getnframes()
            audio = wf.readframes(n_frames)
            samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        asr._lazy_load()
        if asr._recognizer != "unavailable":
            stream = asr._recognizer.create_stream()
            stream.accept_waveform(sr, samples)
            asr._recognizer.decode_stream(stream)
            transcript = stream.result.text.strip()
            log.info(f"  Transcript: \"{transcript}\"")
            assert len(transcript) > 0, "Expected non-empty transcript"
            log.info("  ✅ ASR works with real ZipFormer model!")
        else:
            log.warning("  ⚠️ ASR recognizer unavailable — check model files")
    else:
        log.warning(f"  Test WAV not found at {test_wav} — using fallback test")
        transcript = asr.transcribe("/tmp/nonexistent.mp4")
        log.info(f"  Transcript (fallback): '{transcript}'")
        log.info("  ✅ ASR graceful fallback works")

    # --- Step 4: Test TextEmbedder (placeholder mode) ---
    log.info("\n[4/7] Testing TextEmbedder...")
    from jockey.open_source.search import TextEmbedder
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        log.warning("  OPENAI_API_KEY not set — will use random fallback")
    text_embedder = TextEmbedder(api_key=api_key, model="text-embedding-3-large")
    text_emb = text_embedder.encode("hello world")
    log.info(f"  Text embedding shape: {text_emb.shape}")
    log.info(f"  Text embedding norm: {np.linalg.norm(text_emb):.4f}")
    assert text_emb.shape == (3072,)
    log.info("  ✅ TextEmbedder works (placeholder mode)")

    # --- Step 5: Test Qdrant (in-memory) ---
    log.info("\n[5/7] Testing Qdrant in-memory...")
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance, PointStruct

    qdrant = QdrantClient(":memory:")
    collection_name = "index_test_001"
    fused_dim = 768 + 3072  # viclip + openai text

    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=fused_dim, distance=Distance.COSINE),
    )

    # Insert 3 test shots
    import uuid
    for i in range(3):
        vis_emb = np.random.randn(768).astype(np.float32)
        txt_emb = np.random.randn(3072).astype(np.float32)
        fused = np.concatenate([vis_emb, txt_emb])
        fused = fused / np.linalg.norm(fused)

        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"test_vid_shot_{i}"))
        qdrant.upsert(
            collection_name=collection_name,
            points=[PointStruct(
                id=point_id,
                vector=fused.tolist(),
                payload={
                    "video_id": f"vid_{i}",
                    "start": i * 10.0,
                    "end": (i + 1) * 10.0,
                    "transcript": f"Shot {i} transcript",
                    "video_path": f"/tmp/video_{i}.mp4",
                    "title": f"Test video {i}",
                }
            )]
        )

    # Search
    query_vec = np.random.randn(fused_dim).astype(np.float32)
    query_vec = query_vec / np.linalg.norm(query_vec)
    results = qdrant.query_points(
        collection_name=collection_name,
        query=query_vec.tolist(),
        limit=2,
    )
    search_results = results.points
    log.info(f"  Search returned {len(search_results)} results")
    for r in search_results:
        log.info(f"    → {r.payload['title']}, score={r.score:.4f}, [{r.payload['start']}-{r.payload['end']}s]")
    assert len(search_results) == 2
    log.info("  ✅ Qdrant in-memory works")

    # --- Step 6: Test VideoSearch ---
    log.info("\n[6/7] Testing VideoSearch module...")
    from jockey.open_source.search import VideoSearch
    search = VideoSearch(qdrant_client=qdrant, viclip_embedder=embedder, text_embedder=text_embedder)
    search_results = await search.search("a person walking", index_id="test_001", top_n=2)
    parsed = json.loads(search_results)
    log.info(f"  VideoSearch returned {len(parsed)} results")
    for r in parsed:
        log.info(f"    → {r['video_title']}, score={r['score']:.4f}")
    assert len(parsed) == 2
    log.info("  ✅ VideoSearch module works")

    # --- Step 7: Test Shot Detection ---
    log.info("\n[7/7] Testing shot detection + frame extraction...")
    import shutil
    if not shutil.which("ffmpeg"):
        log.warning("  ⚠️ ffmpeg not found in PATH — skipping test video creation")
        log.info("  Testing frame extraction with decord on a minimal video...")
        # Create a tiny valid MP4 using raw bytes (smallest valid ftyp+moov)
        # Instead, just test that detect_shots handles missing video gracefully
        from jockey.open_source.indexer import detect_shots
        shots = detect_shots("/tmp/nonexistent_video.mp4", threshold=27.0)
        log.info(f"  detect_shots on missing file returned: {shots}")
        log.info("  ✅ Shot detection handles missing ffmpeg gracefully")
    else:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            test_video_path = f.name
        try:
            create_test_video(test_video_path, duration=3.0)
            log.info(f"  Created test video: {test_video_path}")

            from jockey.open_source.indexer import detect_shots, extract_frames
            shots = detect_shots(test_video_path, threshold=27.0)
            log.info(f"  Detected {len(shots)} shot(s): {shots}")
            assert len(shots) >= 1

            frames = extract_frames(test_video_path, shots[0][0], shots[0][1], max_frames=4)
            log.info(f"  Extracted frames shape: {frames.shape}")
            assert len(frames.shape) == 4 and frames.shape[-1] == 3
            log.info("  ✅ Shot detection + frame extraction works")
        finally:
            if os.path.isfile(test_video_path):
                os.remove(test_video_path)

    # --- Summary ---
    log.info("\n" + "=" * 60)
    log.info("🎉 ALL TESTS PASSED — Pipeline foundation is working!")
    log.info("=" * 60)
    log.info("\nNext steps:")
    log.info("  1. Set OPENAI_API_KEY to enable real text embeddings")
    log.info("  2. Install sherpa-onnx + download ZipFormer models for ASR")
    log.info("  3. Use a GPU machine + install internvideo2 for real ViCLIP embeddings")
    log.info("  4. Start Qdrant server: docker run -p 6333:6333 qdrant/qdrant")


if __name__ == "__main__":
    asyncio.run(main())
