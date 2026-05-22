"""Tiny FastAPI server that fronts the `jockeyassistant` bucket for the /s3-test page.

Endpoints:
    GET /api/objects                → [{key, name, size, last_modified, duration_s, thumb_url}]
    GET /api/presign?key=videos/x  → {url, expires_in}

Run:
    python scripts/s3_browser.py
    # → http://localhost:8765

This is a *standalone* service intended for local testing. It does NOT touch
the production video-service or MinIO setup.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

BUCKET = os.environ.get("S3_BUCKET", "jockeyassistant")
PRESIGN_TTL = int(os.environ.get("S3_PRESIGN_TTL", "900"))  # 15 min default
PORT = int(os.environ.get("S3_BROWSER_PORT", "8765"))

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


def _client():
    return boto3.client(
        "s3",
        region_name=REGION,
        # virtual-host style works with regional buckets; safe for vanilla AWS
        config=Config(signature_version="s3v4"),
    )


app = FastAPI(title="S3 Test Browser", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _presign(s3, key: str, ttl: int = PRESIGN_TTL) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=ttl,
    )


def _duration_from_meta(head: dict[str, Any]) -> float | None:
    meta = head.get("Metadata") or {}
    val = meta.get("duration-s")
    try:
        return float(val) if val is not None else None
    except ValueError:
        return None


@app.get("/api/objects")
def list_objects() -> dict[str, Any]:
    s3 = _client()

    # build a set of thumbnail keys (so we don't head_object once per video)
    thumb_keys: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix="thumbs/"):
        for obj in page.get("Contents", []) or []:
            thumb_keys.add(obj["Key"])

    items: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix="videos/"):
        for obj in page.get("Contents", []) or []:
            key = obj["Key"]
            stem = Path(key).stem
            thumb_key = f"thumbs/{stem}.jpg"

            duration_s: float | None = None
            try:
                head = s3.head_object(Bucket=BUCKET, Key=key)
                duration_s = _duration_from_meta(head)
            except Exception:
                pass

            items.append({
                "key": key,
                "name": Path(key).name,
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
                "duration_s": duration_s,
                "thumb_url": _presign(s3, thumb_key) if thumb_key in thumb_keys else None,
            })

    items.sort(key=lambda x: x["last_modified"], reverse=True)
    return {"bucket": BUCKET, "count": len(items), "items": items}


@app.get("/api/presign")
def presign(key: str = Query(..., min_length=1)) -> dict[str, Any]:
    if key.startswith("/") or ".." in key:
        raise HTTPException(400, "invalid key")
    s3 = _client()
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
    except Exception as exc:
        raise HTTPException(404, f"not found: {key}") from exc
    return {"url": _presign(s3, key), "expires_in": PRESIGN_TTL}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "bucket": BUCKET, "region": REGION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
