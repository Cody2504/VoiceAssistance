"""boto3 S3 client wired to MinIO."""
from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.client import Config

from main.settings import get_settings


@lru_cache
def s3():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.minio_endpoint,
        aws_access_key_id=s.minio_root_user,
        aws_secret_access_key=s.minio_root_password,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name=s.minio_region,
    )


@lru_cache
def _s3_public():
    """Separate boto3 client whose ``endpoint_url`` is the browser-reachable host.

    SigV4 includes the ``Host`` header in the signed string. If we generate the
    presigned URL with the internal endpoint (``minio:9000``) and the browser hits
    the host port mapping (``localhost:9000``), the signature is rejected. Signing
    via this client makes the host match what the browser will send.
    """
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.minio_public_endpoint,
        aws_access_key_id=s.minio_root_user,
        aws_secret_access_key=s.minio_root_password,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name=s.minio_region,
    )


def upload_fileobj(bucket: str, key: str, fileobj: BinaryIO, content_type: str = "application/octet-stream") -> None:
    s3().upload_fileobj(fileobj, bucket, key, ExtraArgs={"ContentType": content_type})


def download_to_path(bucket: str, key: str, dest: str) -> None:
    # boto3's high-level download_file uses a transfer manager that builds
    # its own internal client and issues a virtual-hosted-style HEAD
    # (videos.minio.voiceassistant.uk), which Cloudflare's tunnel doesn't
    # route → 403. Fall back to a plain get_object + manual write that
    # honours the path-style config we set on s3(). See MIGRATION_LOG
    # 2026-05-23 problem #10.
    resp = s3().get_object(Bucket=bucket, Key=key)
    with open(dest, "wb") as fh:
        for chunk in resp["Body"].iter_chunks(chunk_size=1024 * 1024):
            fh.write(chunk)


def presigned_get(bucket: str, key: str, expires: int = 3600, public: bool = True) -> str:
    """Generate a presigned URL.

    ``public=True`` (default) signs against ``minio_public_endpoint`` so the browser
    can fetch the URL directly from the host's port mapping.

    ``public=False`` signs against the internal ``minio_endpoint`` (``http://minio:9000``)
    for use by other containers in the docker network — e.g. when handing a URL to
    the in-container Qwen3-VL client. The browser cannot reach this URL, but other
    containers can; SigV4 must match whichever host will actually be used.
    """
    client = _s3_public() if public else s3()
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires,
    )
