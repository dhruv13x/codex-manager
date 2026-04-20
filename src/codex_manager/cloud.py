from __future__ import annotations

import os
import sys
from typing import Any
from pathlib import Path

try:
    from b2sdk.v2 import InMemoryAccountInfo, B2Api
except ImportError:
    B2Api = None

from .credentials import resolve_b2_credentials

class CloudFile:
    def __init__(self, name: str, size: int, last_modified: float):
        self.name = name
        self.size = size
        self.last_modified = last_modified

class B2Provider:
    def __init__(self, key_id: str, app_key: str, bucket_name: str):
        if not B2Api:
            raise ImportError("'b2sdk' is not installed. Please run: pip install b2sdk")
        
        self.info = InMemoryAccountInfo()
        self.b2_api = B2Api(self.info)
        self.bucket_name = bucket_name
        
        # Native B2 authorize handles endpoint discovery automatically
        self.b2_api.authorize_account("production", key_id, app_key)
        self.bucket = self.b2_api.get_bucket_by_name(bucket_name)

    def upload_file(self, local_path: str | Path, remote_path: str) -> None:
        self.bucket.upload_local_file(
            local_file=str(local_path),
            file_name=remote_path
        )

    def download_file(self, remote_path: str, local_path: str | Path) -> None:
        download_dest = self.bucket.download_file_by_name(remote_path)
        download_dest.save_to(str(local_path))

    def list_files(self, prefix: str = "") -> list[CloudFile]:
        files = []
        # b2sdk Bucket.ls call matching geminiai_cli pattern
        try:
            for file_version, _ in self.bucket.ls(recursive=True):
                if file_version.file_name.startswith(prefix):
                    files.append(CloudFile(
                        name=file_version.file_name,
                        size=file_version.size,
                        last_modified=file_version.upload_timestamp / 1000.0  # ms to seconds
                    ))
        except Exception as e:
            print(f"Cloud list failed: {e}", file=sys.stderr)
        return files

    def delete_file(self, remote_path: str) -> None:
        file_version = self.bucket.get_file_info_by_name(remote_path)
        self.bucket.delete_file_version(file_version.id_, remote_path)

def get_cloud_provider(args: Any = None) -> B2Provider | None:
    key_id, app_key, bucket = resolve_b2_credentials(args)
    if key_id and app_key and bucket:
        return B2Provider(key_id, app_key, bucket)
    return None
