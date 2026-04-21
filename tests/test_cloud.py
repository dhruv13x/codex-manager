from unittest.mock import MagicMock, patch

import pytest

from codex_manager.cloud import B2Provider, CloudFile, get_cloud_provider


def test_cloud_file():
    cf = CloudFile("a", 10, 10.0)
    assert cf.name == "a"
    assert cf.size == 10
    assert cf.last_modified == 10.0

@patch("codex_manager.cloud.resolve_b2_credentials")
def test_get_cloud_provider(mock_resolve):
    mock_resolve.return_value = (None, None, None)
    assert get_cloud_provider() is None

@patch("codex_manager.cloud.B2Api")
@patch("codex_manager.cloud.InMemoryAccountInfo")
def test_b2_provider(mock_info, mock_b2):
    b2_api_instance = MagicMock()
    mock_b2.return_value = b2_api_instance
    bucket_mock = MagicMock()
    b2_api_instance.get_bucket_by_name.return_value = bucket_mock

    provider = B2Provider("id", "key", "bucket")

    provider.upload_file("local", "remote")
    bucket_mock.upload_local_file.assert_called_with(local_file="local", file_name="remote")

    down_dest = MagicMock()
    bucket_mock.download_file_by_name.return_value = down_dest
    provider.download_file("remote", "local")
    down_dest.save_to.assert_called_with("local")

    # list_files
    fv1 = MagicMock()
    fv1.file_name = "test.txt"
    fv1.size = 100
    fv1.upload_timestamp = 1000.0

    fv2 = MagicMock()
    fv2.file_name = "other.txt"

    bucket_mock.ls.return_value = [(fv1, None), (fv2, None)]

    files = provider.list_files("test")
    assert len(files) == 1
    assert files[0].name == "test.txt"

    # list_files exception
    bucket_mock.ls.side_effect = Exception("err")
    files = provider.list_files("test")
    assert len(files) == 0

    # delete_file
    fv_info = MagicMock()
    fv_info.id_ = "id"
    bucket_mock.get_file_info_by_name.return_value = fv_info
    provider.delete_file("remote")
    bucket_mock.delete_file_version.assert_called_with("id", "remote")

@patch("codex_manager.cloud.B2Api", None)
def test_b2_provider_no_sdk():
    with pytest.raises(ImportError):
        B2Provider("id", "key", "bucket")

@patch("codex_manager.cloud.B2Api")
@patch("codex_manager.cloud.InMemoryAccountInfo")
@patch("codex_manager.cloud.resolve_b2_credentials")
def test_get_cloud_provider_success(mock_resolve, mock_info, mock_b2):
    mock_resolve.return_value = ("id", "key", "bucket")
    mock_b2.return_value = MagicMock()
    assert get_cloud_provider() is not None
