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
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_fileobj(bucket: str, key: str, fileobj: BinaryIO, content_type: str = "application/octet-stream") -> None:
    s3().upload_fileobj(fileobj, bucket, key, ExtraArgs={"ContentType": content_type})


def download_to_path(bucket: str, key: str, dest: str) -> None:
    s3().download_file(bucket, key, dest)


def presigned_get(bucket: str, key: str, expires: int = 3600) -> str:
    return s3().generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)
