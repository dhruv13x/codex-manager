from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from codex_manager.sync import _get_s3_client, pull_backup, push_backup


def test_get_s3_client(mocker) -> None:
    mock_boto3 = mocker.patch("codex_manager.sync.boto3")

    mocker.patch.dict(os.environ, {
        "AWS_ENDPOINT_URL": "env_endpoint",
        "AWS_ACCESS_KEY_ID": "env_access",
        "AWS_SECRET_ACCESS_KEY": "env_secret",
    })

    _get_s3_client(None, None, None)
    mock_boto3.client.assert_called_with(
        "s3",
        endpoint_url="env_endpoint",
        aws_access_key_id="env_access",
        aws_secret_access_key="env_secret",
    )

    _get_s3_client("arg_endpoint", "arg_access", "arg_secret")
    mock_boto3.client.assert_called_with(
        "s3",
        endpoint_url="arg_endpoint",
        aws_access_key_id="arg_access",
        aws_secret_access_key="arg_secret",
    )


def test_push_backup(mocker, tmp_path: Path) -> None:
    mock_client = MagicMock()
    mocker.patch("codex_manager.sync._get_s3_client", return_value=mock_client)

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "test.tar.gz").write_text("data", encoding="utf-8")

    push_backup(backup_dir, "my-bucket", dry_run=False)

    mock_client.upload_file.assert_called_once_with(
        str(backup_dir / "test.tar.gz"), "my-bucket", "test.tar.gz"
    )

    mock_client.reset_mock()
    push_backup(backup_dir, "my-bucket", dry_run=True)
    mock_client.upload_file.assert_not_called()


def test_pull_backup(mocker, tmp_path: Path) -> None:
    mock_client = MagicMock()
    mocker.patch("codex_manager.sync._get_s3_client", return_value=mock_client)

    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "test.tar.gz"},
            {"Key": "existing.tar.gz"},
        ]
    }

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "existing.tar.gz").write_text("data", encoding="utf-8")

    pull_backup(backup_dir, "my-bucket", dry_run=False)

    mock_client.download_file.assert_called_once_with(
        "my-bucket", "test.tar.gz", str(backup_dir / "test.tar.gz")
    )

    mock_client.reset_mock()
    pull_backup(backup_dir, "my-bucket", dry_run=True)
    mock_client.download_file.assert_not_called()


def test_pull_backup_empty_bucket(mocker, tmp_path: Path) -> None:
    mock_client = MagicMock()
    mocker.patch("codex_manager.sync._get_s3_client", return_value=mock_client)

    mock_client.list_objects_v2.return_value = {}

    backup_dir = tmp_path / "backups"
    pull_backup(backup_dir, "my-bucket", dry_run=False)
    mock_client.download_file.assert_not_called()
