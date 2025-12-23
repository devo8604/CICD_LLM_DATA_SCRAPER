"""
Test cases for dynamic timeout functionality based on file size.
"""

import os
import tempfile

from src.core.utils import calculate_dynamic_timeout


def test_calculate_dynamic_timeout_small_file():
    """Test dynamic timeout calculation for a small file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"Small content")
        temp_file.flush()

        try:
            timeout = calculate_dynamic_timeout(temp_file.name, base_timeout=300, min_timeout=30, max_timeout=3600)
            # Small file should get close to minimum timeout
            assert 30 <= timeout <= 300  # Should be between min and base
        finally:
            os.unlink(temp_file.name)


def test_calculate_dynamic_timeout_medium_file():
    """Test dynamic timeout calculation for a medium file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Create a ~1MB file (reference size)
        temp_file.write(b"x" * (1024 * 1024))  # 1MB
        temp_file.flush()

        try:
            timeout = calculate_dynamic_timeout(temp_file.name, base_timeout=300, min_timeout=30, max_timeout=3600)
            # Medium file (1MB) should get base timeout (300s) since scaling factor is 1, sqrt(1) = 1
            assert timeout == 300
        finally:
            os.unlink(temp_file.name)


def test_calculate_dynamic_timeout_large_file():
    """Test dynamic timeout calculation for a large file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Create a ~4MB file (4x reference size)
        temp_file.write(b"x" * (4 * 1024 * 1024))  # 4MB
        temp_file.flush()

        try:
            timeout = calculate_dynamic_timeout(temp_file.name, base_timeout=300, min_timeout=30, max_timeout=3600)
            # Large file (4MB) should get base * sqrt(4) = 300 * 2 = 600 seconds
            # But due to square root scaling: 300 * sqrt(4) = 300 * 2 = 600
            assert timeout == 600
        finally:
            os.unlink(temp_file.name)


def test_calculate_dynamic_timeout_very_large_file():
    """Test dynamic timeout calculation for a very large file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Create a ~100MB file
        temp_file.write(b"x" * (100 * 1024 * 1024))  # 100MB
        temp_file.flush()

        try:
            timeout = calculate_dynamic_timeout(temp_file.name, base_timeout=300, min_timeout=30, max_timeout=3600)
            # Very large file (100MB) should get base * sqrt(100) = 300 * 10 = 3000 seconds
            # But capped at max_timeout of 3600
            expected = min(300 * (100**0.5), 3600)  # 3000 seconds
            assert timeout == expected
        finally:
            os.unlink(temp_file.name)


def test_calculate_dynamic_timeout_file_not_found():
    """Test dynamic timeout calculation when file doesn't exist."""
    timeout = calculate_dynamic_timeout("/nonexistent/file.txt", base_timeout=300)
    # Should return base timeout when file doesn't exist
    assert timeout == 300


def test_calculate_dynamic_timeout_edge_cases():
    """Test edge cases for dynamic timeout calculation."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Empty file
        temp_file.flush()

        try:
            timeout = calculate_dynamic_timeout(temp_file.name, base_timeout=300, min_timeout=30, max_timeout=3600)
            # Empty file should get minimum timeout
            assert timeout == 30
        finally:
            os.unlink(temp_file.name)


if __name__ == "__main__":
    # Run tests manually if executed as script
    test_calculate_dynamic_timeout_small_file()
    test_calculate_dynamic_timeout_medium_file()
    test_calculate_dynamic_timeout_large_file()
    test_calculate_dynamic_timeout_very_large_file()
    test_calculate_dynamic_timeout_file_not_found()
    test_calculate_dynamic_timeout_edge_cases()
    print("All dynamic timeout tests passed!")
