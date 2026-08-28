"""Object storage. One thin wrapper over boto3 — identical for MinIO (local) and
real S3; only ``S3_ENDPOINT_URL`` differs.

boto3 is synchronous, so callers wrap these in ``run_in_threadpool``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

_NOT_FOUND = {"404", "NoSuchKey", "NotFound"}


def _client() -> S3Client:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


def download_bytes(key: str) -> bytes:
    response = _client().get_object(Bucket=settings.s3_bucket, Key=key)
    body: bytes = response["Body"].read()
    return body


def object_exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in _NOT_FOUND:
            return False
        raise
    return True
