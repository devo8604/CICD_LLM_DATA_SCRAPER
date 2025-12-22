"""pytest configuration for LLM Data Pipeline."""

import os
import sys
from unittest.mock import MagicMock

import pytest
from tqdm import tqdm

# Add the src directory to the path so tests can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

# Configuration for pytest
pytest_plugins = []

# Configuration options
asyncio_mode = "auto"


@pytest.fixture(autouse=True)
def disable_tqdm_monitor():
    """Disable tqdm monitor thread to prevent hanging tests."""
    tqdm.monitor_interval = 0
    yield
    tqdm.monitor_interval = 10  # Reset to default? Or just leave it.


@pytest.fixture
def mock_db_manager():
    """Fixture for mocking DBManager."""
    from src.data.db_manager import DBManager
    mock = MagicMock(spec=DBManager)
    mock.db_path = "test.db"
    return mock


@pytest.fixture
def mock_llm_client():
    """Fixture for mocking LLMClient."""
    return MagicMock()
