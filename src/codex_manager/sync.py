from __future__ import annotations

import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def _get_s3_client(endpoint_url: str | None, access_key: str | None, secret_key: str | None) -> boto3.client:
    # use env vars if not passed
    endpoint_url = endpoint_url or os.environ.get("AWS_ENDPOINT_URL")
    access_key = access_key or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY")

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def push_backup(
    backup_dir: Path,
    bucket_name: str,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    dry_run: bool = False,
) -> None:
    s3 = _get_s3_client(endpoint_url, access_key, secret_key)

    for file_path in backup_dir.glob("*"):
        if not file_path.is_file():
            continue

        object_name = file_path.name

        # Don't upload symlinks
        if file_path.is_symlink():
            continue

        if dry_run:
            print(f"Would push {file_path.name} to s3://{bucket_name}/{object_name}")
            continue

        try:
            print(f"Uploading {file_path.name} to s3://{bucket_name}/{object_name}...")
            s3.upload_file(str(file_path), bucket_name, object_name)
            print(f"Successfully uploaded {file_path.name}")
        except ClientError as e:
            print(f"Failed to upload {file_path.name}: {e}")


def pull_backup(
    backup_dir: Path,
    bucket_name: str,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    dry_run: bool = False,
) -> None:
    s3 = _get_s3_client(endpoint_url, access_key, secret_key)

    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
    except ClientError as e:
        print(f"Failed to list objects in bucket {bucket_name}: {e}")
        return

    if "Contents" not in response:
        print(f"No objects found in bucket {bucket_name}")
        return

    for obj in response["Contents"]:
        object_name = obj["Key"]
        file_path = backup_dir / object_name

        if file_path.exists():
            print(f"Skipping {object_name}, already exists locally.")
            continue

        if dry_run:
            print(f"Would pull s3://{bucket_name}/{object_name} to {file_path}")
            continue

        try:
            print(f"Downloading s3://{bucket_name}/{object_name} to {file_path}...")
            s3.download_file(bucket_name, object_name, str(file_path))
            print(f"Successfully downloaded {object_name}")
        except ClientError as e:
            print(f"Failed to download {object_name}: {e}")
