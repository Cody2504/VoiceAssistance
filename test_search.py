"""
Test indexing + search on football.mp4 using the pretrained pipeline.

Runs CLIP-B/32 locally on CPU (~150 MB download on first run) and uses
in-memory Qdrant — no Docker, no GPU. ASR is stubbed (Whisper on CPU is
slow and football audio transcribes poorly anyway).

Expect ~30-60s total on a typical laptop:
  - CLIP load:  ~10s
  - Indexing :  ~15-30s for a 30s video
  - Each query: ~1-2s

Run:
    export OPENROUTER_API_KEY=sk-or-...
    python test_search.py
"""
import asyncio
import json
import os
import sys
import time

VIDEO_PATH = "/home/hai/MyProj/tl-jockey/football.mp4"

# Force CPU
os.environ["CUDA_VISIBLE_DEVICES"] = ""

if not os.environ.get("OPENROUTER_API_KEY"):
    sys.exit("set OPENROUTER_API_KEY first  (used for query text-embeddings)")
if not os.path.isfile(VIDEO_PATH):
    sys.exit(f"video not found: {VIDEO_PATH}")

# Smaller CLIP for laptop speed (default config picks CLIP-L/14, 4× larger)
LIGHT_CLIP = "openai/clip-vit-base-patch32"

from jockey.open_source.config import config
config.viclip_model_name = LIGHT_CLIP
config.viclip_device = "cpu"
config.mediafm_enabled = False    # skip the Transformer contextualizer

from jockey.open_source.indexer import VideoIndexer
from jockey.open_source.search import VideoSearch, TextEmbedder
from jockey.open_source.viclip_embedder import ViCLIPEmbedder
from qdrant_client import QdrantClient


class StubASR:
    """Skip ASR — Whisper on CPU is slow and not needed for this test."""
    def transcribe(self, *args, **kwargs):
        return ""


# --- 1. Build pipeline components ---
print(f"loading {LIGHT_CLIP} on CPU...")
t0 = time.time()
viclip = ViCLIPEmbedder(model_name_or_path=LIGHT_CLIP, device="cpu")
viclip._lazy_load()
print(f"  model ready in {time.time()-t0:.1f}s\n")

text_embedder = TextEmbedder(
    api_key=os.environ["OPENROUTER_API_KEY"],
    model=config.text_embedding_model,
    base_url=config.openrouter_base_url,
)
qdrant = QdrantClient(":memory:")

indexer = VideoIndexer(
    viclip_embedder=viclip,
    text_embedder=text_embedder,
    asr_engine=StubASR(),
    qdrant_client=qdrant,
    config=config,
)
indexer.create_index("football_test")

# --- 2. Index the video (shot detect → ViCLIP per shot → store in Qdrant) ---
print(f"indexing {VIDEO_PATH} ...")
t0 = time.time()
indexer.index_video(VIDEO_PATH, index_id="football_test", title="football clip")
print(f"  indexed in {time.time()-t0:.1f}s\n")

# --- 3. Search the index with several queries ---
search = VideoSearch(
    qdrant_client=qdrant,
    viclip_embedder=viclip,
    text_embedder=text_embedder,
    config=config,
)

queries = [
    "a player kicking the ball",
    "the crowd in the stadium",
    "a goal being scored",
    "players running on the field",
]
for q in queries:
    t0 = time.time()
    hits = json.loads(asyncio.run(search.search(q, "football_test", top_n=3, group_by="clip")))
    print(f"query: {q!r}   ({time.time()-t0:.2f}s)")
    for h in hits:
        print(f"  score={h['score']:.3f}  t=[{h['start']:5.1f}, {h['end']:5.1f}]s")
    print()
