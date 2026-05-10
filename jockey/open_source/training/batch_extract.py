"""
Batch Feature Extraction — run the feature extractor over many videos.

Two input modes:
  1. --videos-dir DIR     scan recursively for video files
  2. --manifest CSV       CSV with columns video_id, video_path, title, genre, synopsis, tone

Each video produces one .npz at OUT_DIR/<video_id>.npz.

Example:
    python -m jockey.open_source.training.batch_extract \\
        --videos-dir data/charades/videos/ \\
        --out-dir   features/charades/ \\
        --skip-existing
"""
import argparse
import csv
import glob
import logging
import os
import time
from typing import Dict, List

from jockey.open_source.training.feature_extractor import FeatureExtractor

log = logging.getLogger(__name__)

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def discover_videos(videos_dir: str) -> List[Dict[str, str]]:
    files = []
    for ext in VIDEO_EXTS:
        files.extend(glob.glob(os.path.join(videos_dir, f"**/*{ext}"), recursive=True))
    files = sorted(set(files))
    return [
        {
            "video_id": os.path.splitext(os.path.basename(f))[0],
            "video_path": f,
        }
        for f in files
    ]


def load_manifest(path: str) -> List[Dict[str, str]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if "video_path" not in (reader.fieldnames or []):
            raise ValueError("manifest CSV must have a 'video_path' column")
        rows = []
        for r in reader:
            r = {k: (v or "") for k, v in r.items()}
            r.setdefault(
                "video_id",
                os.path.splitext(os.path.basename(r["video_path"]))[0],
            )
            rows.append(r)
    return rows


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    p = argparse.ArgumentParser(description="Batch-extract per-shot features.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--videos-dir", help="Directory of video files (recursive scan)")
    src.add_argument("--manifest", help="CSV manifest with video_path + optional metadata")
    p.add_argument("--out-dir", required=True, help="Output directory for .npz files")
    p.add_argument("--skip-audio", action="store_true")
    p.add_argument("--skip-asr", action="store_true")
    p.add_argument("--skip-metadata", action="store_true")
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip videos whose <video_id>.npz already exists in --out-dir",
    )
    p.add_argument("--limit", type=int, default=None, help="Process at most N videos")
    args = p.parse_args()

    items = (
        load_manifest(args.manifest)
        if args.manifest
        else discover_videos(args.videos_dir)
    )
    if args.limit is not None:
        items = items[: args.limit]

    log.info(f"Found {len(items)} videos. Output → {args.out_dir}")
    os.makedirs(args.out_dir, exist_ok=True)

    extractor = FeatureExtractor(
        skip_audio=args.skip_audio,
        skip_asr=args.skip_asr,
        skip_metadata=args.skip_metadata,
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
            feats = extractor.extract(
                video_path=item["video_path"],
                video_id=vid,
                title=item.get("title", ""),
                genre=item.get("genre", ""),
                synopsis=item.get("synopsis", ""),
                tone=item.get("tone", ""),
            )
            feats.save(out_path)
            n_ok += 1
        except Exception as e:
            log.error(f"  FAILED ({vid}): {e}")
            n_fail += 1

    elapsed = time.time() - t0
    log.info(
        f"Batch done. ok={n_ok} skip={n_skip} fail={n_fail} "
        f"elapsed={elapsed:.1f}s ({elapsed/max(len(items),1):.1f}s/video)"
    )


if __name__ == "__main__":
    main()
