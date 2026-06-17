import os
import io
from unittest.mock import patch

from codex_manager.banner import print_logo


def test_print_logo_procedural_palette():
    """Test that the logo is printed with a procedurally generated palette."""
    with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with patch.dict(os.environ, {}, clear=True):
            print_logo()
        assert "CLI interface for managing OpenAI Codex account snapshots" in mock_stdout.getvalue()


def test_print_logo_fixed_palette():
    """Test that the logo is printed with a fixed palette."""
    with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with patch.dict(os.environ, {'CREATE_DUMP_PALETTE': '1'}, clear=True):
            print_logo()
        assert "CLI interface for managing OpenAI Codex account snapshots" in mock_stdout.getvalue()


def test_print_logo_fixed_palette_invalid_index():
    """Test that the logo falls back to a procedural palette with an invalid index."""
    with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with patch.dict(os.environ, {'CREATE_DUMP_PALETTE': '999'}, clear=True):
            print_logo()
        assert "CLI interface for managing OpenAI Codex account snapshots" in mock_stdout.getvalue()


def test_print_logo_fixed_palette_invalid_value():
    """Test that the logo falls back to a procedural palette with an invalid value."""
    with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with patch.dict(os.environ, {'CREATE_DUMP_PALETTE': 'invalid'}, clear=True):
            print_logo()
        assert "CLI interface for managing OpenAI Codex account snapshots" in mock_stdout.getvalue()
