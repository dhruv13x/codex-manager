from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from codex_manager.sync import _get_s3_client, pull_backup, push_backup


@patch("codex_manager.sync._get_s3_client")
def test_push_backup(mock_s3, tmp_path):
    s3 = MagicMock()
    mock_s3.return_value = s3

    bdir = tmp_path / "backups"
    bdir.mkdir()
    f1 = bdir / "foo.tar.gz"
    f1.write_text("x")
    m1 = bdir / "foo.metadata.json"
    m1.write_text("x")

    paginator = MagicMock()
    s3.get_paginator.return_value = paginator
    paginator.paginate.return_value = [{"Contents": [{"Key": "foo.metadata.json"}]}]

    push_backup(bdir, "bucket", "ep", "key", "sec", dry_run=False)
    s3.upload_file.assert_any_call(str(f1), "bucket", "foo.tar.gz")

@patch("codex_manager.sync._get_s3_client")
def test_push_backup_client_error(mock_s3, tmp_path):
    s3 = MagicMock()
    mock_s3.return_value = s3

    bdir = tmp_path / "backups"
    bdir.mkdir()
    f1 = bdir / "foo.tar.gz"
    f1.write_text("x")

    paginator = MagicMock()
    s3.get_paginator.return_value = paginator
    paginator.paginate.return_value = []

    s3.upload_file.side_effect = ClientError({"Error": {}}, "op")

    push_backup(bdir, "bucket", "ep", "key", "sec", dry_run=False)

@patch("codex_manager.sync._get_s3_client")
def test_pull_backup(mock_s3, tmp_path):
    s3 = MagicMock()
    mock_s3.return_value = s3

    bdir = tmp_path / "backups"
    bdir.mkdir()
    f1 = bdir / "foo.tar.gz"
    f1.write_text("x")

    s3.list_objects_v2.return_value = {"Contents": [{"Key": "foo.tar.gz"}, {"Key": "bar.tar.gz"}]}

    pull_backup(bdir, "bucket", "ep", "key", "sec", dry_run=False)
    s3.download_file.assert_any_call("bucket", "bar.tar.gz", str(bdir / "bar.tar.gz"))

@patch("codex_manager.sync._get_s3_client")
def test_pull_backup_client_error(mock_s3, tmp_path):
    s3 = MagicMock()
    mock_s3.return_value = s3

    bdir = tmp_path / "backups"
    bdir.mkdir()

    s3.list_objects_v2.side_effect = ClientError({"Error": {}}, "op")
    pull_backup(bdir, "bucket", "ep", "key", "sec", dry_run=False)

@patch("codex_manager.sync.boto3")
def test_get_s3_client(mock_boto, monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    res = _get_s3_client(None, None, None)
    assert res is not None
