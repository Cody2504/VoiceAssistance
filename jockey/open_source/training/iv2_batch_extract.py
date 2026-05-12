"""
Batch InternVideo2 feature extraction over a directory or manifest of videos.

Mirrors `batch_extract.py` but uses `IV2FeatureExtractor`. Single model load,
many videos.

Examples:
    # Whole directory
    python -m jockey.open_source.training.iv2_batch_extract \\
        --videos-dir data/charades/videos/ \\
        --out-dir   features/iv2_charades/ \\
        --window-sec 2.0 --skip-existing

    # CSV manifest
    python -m jockey.open_source.training.iv2_batch_extract \\
        --manifest data/charades_manifest.csv \\
        --out-dir  features/iv2_charades/
"""
from __future__ import annotations

import argparse
import logging
import os
import time

from jockey.open_source.training.batch_extract import discover_videos, load_manifest
from jockey.open_source.training.iv2_feature_extractor import IV2FeatureExtractor

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    p = argparse.ArgumentParser(description="Batch-extract InternVideo2 features.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--videos-dir", help="Directory of video files (recursive)")
    src.add_argument("--manifest", help="CSV manifest with video_path column")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--limit", type=int, default=None)

    # IV2 settings
    p.add_argument("--window-sec", type=float, default=2.0)
    p.add_argument("--frames-per-clip", type=int, default=4)
    p.add_argument(
        "--model", default="OpenGVLab/InternVideo2-Stage2_1B-224p-f4",
    )
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="fp16", choices=["fp16", "bf16", "fp32"])
    p.add_argument("--encode-batch-size", type=int, default=16)
    args = p.parse_args()

    items = load_manifest(args.manifest) if args.manifest else discover_videos(args.videos_dir)
    if args.limit is not None:
        items = items[: args.limit]
    log.info(f"Found {len(items)} videos. Output → {args.out_dir}")
    os.makedirs(args.out_dir, exist_ok=True)

    extractor = IV2FeatureExtractor(
        model_name=args.model,
        device=args.device,
        window_sec=args.window_sec,
        frames_per_clip=args.frames_per_clip,
        dtype=args.dtype,
        encode_batch_size=args.encode_batch_size,
    )

    n_ok = n_skip = n_fail = 0
    t0 = time.time()
    for i, item in enumerate(items, 1):
        vid = item["video_id"]
        out_path = os.path.join(args.out_dir, f"{vid}.npz")
        if args.skip_existing and os.path.isfile(out_path):
            log.info(f"[{i}/{len(items)}] SKIP (exists): {vid}")
            n_skip += 1
            continue
        try:
            log.info(f"[{i}/{len(items)}] {vid}")
            feats = extractor.extract(video_path=item["video_path"], video_id=vid)
            feats.save(out_path)
            n_ok += 1
        except Exception as e:
            log.error(f"  FAILED ({vid}): {e}")
            n_fail += 1

    elapsed = time.time() - t0
    log.info(
        f"Batch done. ok={n_ok} skip={n_skip} fail={n_fail} "
        f"elapsed={elapsed:.1f}s ({elapsed / max(len(items), 1):.1f}s/video)"
    )


if __name__ == "__main__":
    main()
