import os
import shutil
import tempfile
from pathlib import Path

# Create temporary directories for testing
# We do this at the module level to ensure they are set before any tests (and imports) run
_tmp_home = tempfile.mkdtemp(prefix="codex-manager-test-home-")
_tmp_codex = tempfile.mkdtemp(prefix="codex-manager-test-codex-")

os.environ["CODEX_MANAGER_HOME"] = _tmp_home
os.environ["CODEX_HOME"] = _tmp_codex

# Also set them as Path objects for convenience in cleanup if needed
TEST_HOME = Path(_tmp_home)
TEST_CODEX = Path(_tmp_codex)

def pytest_configure(config):
    """Ensure the temporary directories exist."""
    TEST_HOME.mkdir(parents=True, exist_ok=True)
    TEST_CODEX.mkdir(parents=True, exist_ok=True)

def pytest_unconfigure(config):
    """Clean up the temporary directories after all tests have finished."""
    if TEST_HOME.exists():
        shutil.rmtree(TEST_HOME, ignore_errors=True)
    if TEST_CODEX.exists():
        shutil.rmtree(TEST_CODEX, ignore_errors=True)
