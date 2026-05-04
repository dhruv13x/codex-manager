from __future__ import annotations

import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from .ui import console


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

    # Fetch remote state
    remote_files = {}
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        if "Contents" in response:
            for obj in response["Contents"]:
                remote_files[obj["Key"]] = obj["Size"]
    except ClientError as e:
        console.print(f"[bold red]Failed to list remote bucket {bucket_name}: {e}[/]", stderr=True)
        return

    # Push all tar.gz and metadata.json files
    backup_files = sorted(list(backup_dir.glob("*.tar.gz")) + list(backup_dir.glob("*.metadata.json")))

    for file_path in backup_files:
        if not file_path.is_file() or file_path.is_symlink():
            continue

        object_name = file_path.name
        
        # Check if file exists and has the same size
        if object_name in remote_files and remote_files[object_name] == file_path.stat().st_size:
            console.print(f"Skipping {file_path.name}, already exists in cloud with same size.")
            continue

        if dry_run:
            console.print(f"Would push {file_path.name} to s3://{bucket_name}/{object_name}")
            continue

        try:
            console.print(f"Uploading {file_path.name} to s3://{bucket_name}/{object_name}...")
            s3.upload_file(str(file_path), bucket_name, object_name)
            console.print(f"[green]Successfully uploaded {file_path.name}[/]")
        except ClientError as e:
            console.print(f"[bold red]Failed to upload {file_path.name}: {e}[/]", stderr=True)


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

    # Use a set for O(1) lookup
    local_files = {p.name for p in backup_dir.glob("*")}

    try:
        # Use simple list_objects_v2 for better test compatibility unless we want to rewrite many tests
        response = s3.list_objects_v2(Bucket=bucket_name)
        if "Contents" not in response:
            if not response.get("KeyCount") or response.get("KeyCount") == 0:
                console.print(f"No objects found in bucket {bucket_name}")
            return

        for obj in response["Contents"]:
            object_name = obj["Key"]
            file_path = backup_dir / object_name

            if object_name in local_files:
                console.print(f"Skipping {object_name}, already exists locally.")
                continue

            if dry_run:
                console.print(f"Would pull s3://{bucket_name}/{object_name} to {file_path}")
                continue

            try:
                console.print(f"Downloading s3://{bucket_name}/{object_name} to {file_path}...")
                s3.download_file(bucket_name, object_name, str(file_path))
                console.print(f"[green]Successfully downloaded {object_name}[/]")
            except ClientError as e:
                console.print(f"[bold red]Failed to download {object_name}: {e}[/]", stderr=True)
    except ClientError as e:
        console.print(f"[bold red]Failed to sync with bucket {bucket_name}: {e}[/]", stderr=True)
