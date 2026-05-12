"""
Smoke-test the TRACE moment localizer on football.mp4.

Loads Yongxin-Guo/trace-uni (4-bit on T4), runs 3-5 sample queries, prints
predicted spans + confidences. Validates that:
  - TRACE repo + dependencies are correctly installed
  - 4-bit load fits the available GPU
  - Output parser produces sensible (start, end) bounded by [0, duration]

INFERENCE ONLY — no training, no Charades eval.

Run on Colab T4:
    !pip install bitsandbytes accelerate
    !git clone https://github.com/gyxxyg/TRACE.git
    !cd TRACE && pip install -r requirements.txt && pip install -e .
    !cd /content/tl-jockey && python test_trace_localizer.py

Approximate wall-clock on T4 4-bit:
    one-time load: ~3-5 min
    per query:     ~10-30 s
"""
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

VIDEO_PATH = "/home/hai/MyProj/tl-jockey/football.mp4"
if len(sys.argv) > 1:
    VIDEO_PATH = sys.argv[1]

QUERIES = [
    "a player kicking the ball",
    "the crowd cheering in the stadium",
    "a goal being scored",
]

if not os.path.isfile(VIDEO_PATH):
    sys.exit(f"video not found: {VIDEO_PATH}")

from jockey.open_source.config import config
from jockey.open_source.trace_localizer import TraceLocalizer

loc = TraceLocalizer(
    model_path=config.trace_model_name,
    device="cuda",
    load_in_4bit=config.trace_load_in_4bit,
    num_frames=config.trace_frames_per_clip,
)

print(f"\nRunning TRACE on {VIDEO_PATH}")
print(f"  model       : {config.trace_model_name}")
print(f"  4-bit       : {config.trace_load_in_4bit}")
print(f"  frames/clip : {config.trace_frames_per_clip}\n")

for q in QUERIES:
    t0 = time.time()
    pred = loc.localize(q, VIDEO_PATH)
    elapsed = time.time() - t0

    # Sanity checks
    sane = (
        pred.start_sec >= 0
        and pred.end_sec <= pred.duration + 1.0   # +1s tolerance for rounding
        and pred.end_sec > pred.start_sec
    )
    status = "OK " if sane else "BAD"

    print(f"  [{status}] {elapsed:5.1f}s  span=[{pred.start_sec:6.2f}, {pred.end_sec:6.2f}]s "
          f"of duration={pred.duration:.1f}s  score={pred.confidence:.3f}")
    print(f"         query: {q!r}")
    if not sane:
        print(f"         FAILED sanity check (out-of-bounds or inverted span)")
    print()
