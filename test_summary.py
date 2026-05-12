"""
Test video text generation — summary of football.mp4.

Uses the pretrained Qwen3-VL VLM via OpenRouter (cloud). No local model load,
no GPU needed. Cost: ~$0.001-0.005 per call (pennies).

Run:
    export OPENROUTER_API_KEY=sk-or-...
    python test_summary.py
"""
import asyncio
import json
import os
import sys
import time

VIDEO_PATH = "/home/hai/MyProj/tl-jockey/football.mp4"

if not os.environ.get("OPENROUTER_API_KEY"):
    sys.exit("set OPENROUTER_API_KEY first  (https://openrouter.ai/keys)")
if not os.path.isfile(VIDEO_PATH):
    sys.exit(f"video not found: {VIDEO_PATH}")

from jockey.open_source.config import config
from jockey.open_source.video_qa import VideoQA

qa = VideoQA.from_config(config)

t0 = time.time()
result = json.loads(asyncio.run(qa.summarize(VIDEO_PATH, mode="summary")))
print(f"\n--- Summary ({time.time()-t0:.1f}s) ---")
print(result["text"])

t0 = time.time()
gist = json.loads(asyncio.run(qa.gist(VIDEO_PATH, options=["title", "topic", "hashtag"])))
print(f"\n--- Gist ({time.time()-t0:.1f}s) ---")
print(f"title  : {gist.get('title')}")
print(f"topic  : {gist.get('topic')}")
print(f"hashtag: {gist.get('hashtag')}")
