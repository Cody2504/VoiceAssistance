"""End-to-end smoke test for the `jockeyassistant` S3 bucket.

What it does:
  1. uploads `SAT table.mp4` to s3://jockeyassistant/videos/SAT_table.mp4
  2. lists the bucket
  3. downloads the same object back to /tmp/s3_smoke_out.mp4
  4. generates a presigned GET URL (15 min) and prints it
  5. verifies the downloaded file matches the source by size

Reads creds from environment (.env is auto-loaded). Required:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
Optional:
    S3_BUCKET (default: jockeyassistant)

Run from project root with the venv active:
    python scripts/s3_smoke_test.py
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

BUCKET = os.environ.get("S3_BUCKET", "jockeyassistant")
SOURCE = PROJECT_ROOT / "SAT table.mp4"
KEY = "videos/SAT_table.mp4"
DEST = Path("/tmp/s3_smoke_out.mp4")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not SOURCE.is_file():
        print(f"source missing: {SOURCE}", file=sys.stderr)
        return 1

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
        print("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set (check .env)", file=sys.stderr)
        return 2

    s3 = boto3.client("s3", region_name=region)

    print(f"[1/5] upload  {SOURCE.name}  →  s3://{BUCKET}/{KEY}")
    src_size = SOURCE.stat().st_size
    src_sha = sha256(SOURCE)
    s3.upload_file(
        str(SOURCE), BUCKET, KEY,
        ExtraArgs={"ContentType": "video/mp4"},
    )
    print(f"        ok ({src_size:,} bytes, sha256={src_sha[:12]}…)")

    print(f"[2/5] list    s3://{BUCKET}/  (top 10)")
    try:
        resp = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=10)
    except ClientError as e:
        print(f"        list failed: {e}", file=sys.stderr)
        return 3
    for obj in resp.get("Contents", []):
        print(f"          {obj['Key']:50s}  {obj['Size']:>12,}  {obj['LastModified']:%Y-%m-%d %H:%M}")

    print(f"[3/5] head    s3://{BUCKET}/{KEY}")
    head = s3.head_object(Bucket=BUCKET, Key=KEY)
    print(f"        content-type={head['ContentType']}  size={head['ContentLength']:,}  etag={head['ETag']}")

    print(f"[4/5] download s3://{BUCKET}/{KEY}  →  {DEST}")
    s3.download_file(BUCKET, KEY, str(DEST))
    dest_sha = sha256(DEST)
    match = "MATCH" if dest_sha == src_sha else "MISMATCH"
    print(f"        ok ({DEST.stat().st_size:,} bytes, sha256={dest_sha[:12]}…)  [{match}]")
    if dest_sha != src_sha:
        return 4

    print(f"[5/5] presign GET  s3://{BUCKET}/{KEY}  (15 min)")
    url = s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": KEY}, ExpiresIn=900)
    print(f"        {url}")

    print("\nall steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
