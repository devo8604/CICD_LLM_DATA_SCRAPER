"""pytest configuration for LLM Data Pipeline."""

import sys
import os

# Add the src directory to the path so tests can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

# Configuration for pytest
pytest_plugins = []

# Configuration options
asyncio_mode = "auto"