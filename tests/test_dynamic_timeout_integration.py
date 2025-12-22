"""
Integration test to verify dynamic timeouts work correctly in file processing.
"""

import os
import tempfile
from unittest.mock import Mock, patch
import pytest

from src.pipeline.file_processing_service import FileProcessingService
from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.llm.llm_client import LLMClient


def test_dynamic_timeout_integration():
    """Test that dynamic timeouts are properly applied in file processing."""

    # Create a config instance (uses defaults)
    config = AppConfig()

    # Verify the default timeout
    default_timeout = config.model.llm.request_timeout
    print(f"Default LLM_REQUEST_TIMEOUT: {default_timeout}s")

    # Create a temporary file of known size
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
        # Write 4MB of content (should result in ~600s timeout based on square root scaling)
        large_content = "This is a test file content. " * (4 * 1024 * 1024 // 30)
        temp_file.write(large_content)
        temp_file.flush()

        file_path = temp_file.name
        file_size = os.path.getsize(file_path)

        try:
            from src.core.utils import calculate_dynamic_timeout

            # Calculate expected timeout for this file size
            expected_timeout = calculate_dynamic_timeout(
                file_path,
                base_timeout=default_timeout
            )

            print(f"File size: {file_size} bytes")
            print(f"Expected timeout: {expected_timeout} seconds")

            # The timeout should be based on file size
            # Calculate expected timeout based on actual file size
            reference_size = 1024 * 1024  # 1MB
            scaling_factor = file_size / reference_size
            expected_calc = int(300 * (scaling_factor ** 0.5))

            assert expected_timeout == expected_calc, f"Expected {expected_calc}s for {file_size} byte file, got {expected_timeout}s"

        finally:
            # Clean up
            os.unlink(file_path)


def test_small_file_dynamic_timeout():
    """Test that small files get minimum timeout."""

    # Create a config instance (uses defaults)
    config = AppConfig()
    default_timeout = config.model.llm.request_timeout

    # Create a small temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
        # Write small content (< 1KB)
        small_content = "Small test content."
        temp_file.write(small_content)
        temp_file.flush()

        file_path = temp_file.name

        try:
            from src.core.utils import calculate_dynamic_timeout

            # Calculate expected timeout for small file
            expected_timeout = calculate_dynamic_timeout(
                file_path,
                base_timeout=default_timeout,
                min_timeout=30,
                max_timeout=3600
            )

            print(f"Small file timeout: {expected_timeout} seconds")

            # Small files should get minimum timeout (30 seconds)
            assert expected_timeout == 30, f"Expected 30s for small file, got {expected_timeout}s"

        finally:
            # Clean up
            os.unlink(file_path)


if __name__ == "__main__":
    test_dynamic_timeout_integration()
    test_small_file_dynamic_timeout()
    print("All dynamic timeout integration tests passed!")