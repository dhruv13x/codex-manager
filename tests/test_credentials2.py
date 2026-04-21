from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from codex_manager.credentials import (
    fetch_doppler_secrets,
    get_doppler_token,
    load_env_file,
    resolve_b2_credentials,
)


def test_load_env_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text("A=1\nB='2'\n#C=3\n")
    env = load_env_file(f)
    assert env["A"] == "1"
    assert env["B"] == "2"
    assert "C" not in env

    assert load_env_file(tmp_path / "missing") == {}

def test_get_doppler_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DOPPLER_TOKEN", "env_tok")
    assert get_doppler_token() == "env_tok"

    monkeypatch.delenv("DOPPLER_TOKEN", raising=False)
    with patch("codex_manager.credentials.os.path.exists", return_value=True):
        with patch("codex_manager.credentials.open", MagicMock()) as mock_file:
            mock_file.return_value.__enter__.return_value = ["DOPPLER_TOKEN=file_tok"]
            assert get_doppler_token() == "file_tok"

    with patch("codex_manager.credentials.os.path.exists", return_value=False):
        assert get_doppler_token() is None

@patch("codex_manager.credentials.requests.get")
def test_fetch_doppler_secrets(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"A": "1"}
    mock_get.return_value = mock_resp
    assert fetch_doppler_secrets("tok") == {"A": "1"}

    mock_resp.status_code = 404
    assert fetch_doppler_secrets("tok") is None

    mock_get.side_effect = Exception("err")
    assert fetch_doppler_secrets("tok") is None

@patch("codex_manager.credentials.get_doppler_token")
@patch("codex_manager.credentials.fetch_doppler_secrets")
def test_resolve_b2_credentials(mock_fetch, mock_tok, monkeypatch):
    # args
    args = SimpleNamespace(b2_id="id1", b2_key="key1", bucket="b1")
    assert resolve_b2_credentials(args) == ("id1", "key1", "b1")

    # doppler
    args = SimpleNamespace(b2_id=None, b2_key=None, bucket=None)
    mock_tok.return_value = "tok"
    mock_fetch.return_value = {"CODEX_B2_KEY_ID": "id2", "CODEX_B2_APP_KEY": "key2", "CODEX_B2_BUCKET": "b2"}
    assert resolve_b2_credentials(args) == ("id2", "key2", "b2")

    # env
    mock_tok.return_value = None
    monkeypatch.setenv("CODEX_B2_KEY_ID", "id3")
    monkeypatch.setenv("CODEX_B2_APP_KEY", "key3")
    monkeypatch.setenv("CODEX_B2_BUCKET", "b3")
    assert resolve_b2_credentials(args) == ("id3", "key3", "b3")

    # env file
    monkeypatch.delenv("CODEX_B2_KEY_ID", raising=False)
    monkeypatch.delenv("CODEX_B2_APP_KEY", raising=False)
    monkeypatch.delenv("CODEX_B2_BUCKET", raising=False)
    with patch("codex_manager.credentials.load_env_file") as mock_load:
        mock_load.return_value = {"CODEX_B2_KEY_ID": "id4", "CODEX_B2_APP_KEY": "key4", "CODEX_B2_BUCKET": "b4"}
        assert resolve_b2_credentials(args) == ("id4", "key4", "b4")
