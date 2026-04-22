from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from codex_manager.registry import merge_registries, get_registry_entry

def test_merge_registries_both_present():
    local = {
        "a@a.com": {"updated_at": "2026-01-01"},
        "b@b.com": {"updated_at": "2026-01-03"}
    }
    remote = {
        "a@a.com": {"updated_at": "2026-01-02"},
        "b@b.com": {"updated_at": "2026-01-01"}
    }
    merged = merge_registries(local, remote)
    assert merged["a@a.com"]["updated_at"] == "2026-01-02"
    assert merged["b@b.com"]["updated_at"] == "2026-01-03"

def test_get_registry_entry(mocker):
    mocker.patch("codex_manager.registry.load_registry", return_value={"test@example.com": {"val": 1}})
    entry = get_registry_entry("test@example.com")
    assert entry["val"] == 1
    assert get_registry_entry("none@none.com") is None
