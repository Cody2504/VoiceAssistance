"""Upload one or more local videos to `jockeyassistant`, with thumbnails.

Layout on S3:
    videos/<basename>.mp4   ← the video itself, ContentType=video/mp4
    thumbs/<basename>.jpg   ← single frame extracted at ~1.0s via ffmpeg

Duration is detected with ffprobe and stored as S3 user metadata
(`x-amz-meta-duration-s`) so the frontend can show it without re-probing.

Usage:
    python scripts/s3_ingest.py "SAT table.mp4" tennis.mp4 football.mp4
    python scripts/s3_ingest.py samples/*.mp4
    python scripts/s3_ingest.py --all                 # uploads everything matching *.mp4 in project root + samples/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import boto3
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
BUCKET = os.environ.get("S3_BUCKET", "jockeyassistant")


def slug(stem: str) -> str:
    """Conservative S3 key: keep alnum, dash, underscore, dot."""
    s = re.sub(r"\s+", "_", stem.strip())
    return re.sub(r"[^A-Za-z0-9._-]", "", s) or "video"


def probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            stderr=subprocess.STDOUT,
        )
        return float(json.loads(out)["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, ValueError):
        return None


def make_thumb(src: Path, dest: Path, at: float = 1.0) -> bool:
    """Extract a single JPEG frame at `at` seconds (clamped). Returns success."""
    dur = probe_duration(src) or 0.0
    ts = max(0.0, min(at, max(0.0, dur - 0.05)))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{ts:.3f}", "-i", str(src),
        "-frames:v", "1", "-q:v", "3",
        "-vf", "scale='min(640,iw)':-2",
        str(dest),
    ]
    try:
        subprocess.check_call(cmd)
        return dest.is_file()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def upload_one(s3, src: Path) -> None:
    if not src.is_file():
        print(f"  skip (not a file): {src}")
        return

    name = slug(src.stem) + src.suffix.lower()
    video_key = f"videos/{name}"
    thumb_key = f"thumbs/{Path(name).stem}.jpg"

    dur = probe_duration(src)
    meta = {}
    if dur is not None:
        meta["duration-s"] = f"{dur:.3f}"

    print(f"  upload  {src.name}  →  s3://{BUCKET}/{video_key}"
          f"   ({src.stat().st_size:,} bytes" + (f", {dur:.1f}s)" if dur else ")"))
    s3.upload_file(
        str(src), BUCKET, video_key,
        ExtraArgs={
            "ContentType": "video/mp4",
            "Metadata": meta,
        },
    )

    with tempfile.TemporaryDirectory() as td:
        thumb_path = Path(td) / "thumb.jpg"
        if make_thumb(src, thumb_path):
            print(f"  thumb   {thumb_path.name}  →  s3://{BUCKET}/{thumb_key}")
            s3.upload_file(
                str(thumb_path), BUCKET, thumb_key,
                ExtraArgs={"ContentType": "image/jpeg"},
            )
        else:
            print(f"  thumb   skipped (ffmpeg failed or unavailable)")


def iter_default_targets() -> Iterable[Path]:
    for p in sorted(PROJECT_ROOT.glob("*.mp4")):
        yield p
    samples = PROJECT_ROOT / "samples"
    if samples.is_dir():
        for p in sorted(samples.glob("*.mp4")):
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="video files to upload")
    ap.add_argument("--all", action="store_true", help="upload every *.mp4 in project root and ./samples/")
    args = ap.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("warning: ffmpeg/ffprobe not on PATH; thumbnails/duration will be skipped", file=sys.stderr)

    targets: list[Path] = []
    if args.all:
        targets.extend(iter_default_targets())
    for raw in args.paths:
        targets.append(Path(raw).expanduser().resolve())
    if not targets:
        ap.error("pass at least one path, or --all")

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
        print("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set (check .env)", file=sys.stderr)
        return 2

    s3 = boto3.client("s3", region_name=region)
    print(f"bucket: s3://{BUCKET}  ({len(targets)} file(s))")
    for p in targets:
        upload_one(s3, p)
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
