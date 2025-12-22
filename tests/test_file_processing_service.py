"""Unit tests for the FileProcessingService."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.pipeline.file_processing_service import FileProcessingService


class TestFileProcessingService:
    """Test cases for FileProcessingService."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.config = AppConfig()
        self.db_manager = MagicMock(spec=DBManager)
        self.service = FileProcessingService(llm_client=MagicMock(), db_manager=self.db_manager, config=self.config)

    def test_calculate_file_hash_success(self):
        """Test successful file hash calculation."""
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file_path = f.name

        try:
            # Calculate hash
            result = self.service.calculate_file_hash(temp_file_path)

            # Verify the hash is correct
            import hashlib

            expected_hash = hashlib.sha256(b"test content").hexdigest()
            assert result == expected_hash
        finally:
            # Clean up
            os.unlink(temp_file_path)

    def test_calculate_file_hash_nonexistent_file(self):
        """Test hash calculation for non-existent file."""
        result = self.service.calculate_file_hash("/nonexistent/file.txt")
        assert result is None

    def test_process_single_file_unchanged(self):
        """Test processing a file that hasn't changed (should skip)."""
        # Mock the database to return a matching hash
        self.db_manager.get_file_hash.return_value = "same_hash"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file_path = f.name

        try:
            # Mock the hash calculation to return the same hash
            with patch.object(self.service, "calculate_file_hash", return_value="same_hash"):
                result = self.service.process_single_file(temp_file_path, "test_repo")
                success, qa_count = result

                # Verify the file was skipped (success=True, qa_count=0)
                assert success is True
                assert qa_count == 0
        finally:
            os.unlink(temp_file_path)

    def test_process_single_file_empty_content(self):
        """Test processing an empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            # Create empty file
            temp_file_path = f.name

        try:
            # Mock the hash calculation
            with patch.object(self.service, "calculate_file_hash", return_value="hash123"):
                self.db_manager.get_file_hash.return_value = None  # File is new

                result = self.service.process_single_file(temp_file_path, "test_repo")
                success, qa_count = result

                # Empty files should be processed successfully but generate no Q&A pairs
                assert success is True
                assert qa_count == 0
        finally:
            os.unlink(temp_file_path)

    def test_process_single_file_timeout(self):
        """Test file processing with timeout."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file_path = f.name

        try:
            # Mock reading to simulate timeout
            with patch.object(self.service, "calculate_file_hash", return_value="hash123"):
                self.db_manager.get_file_hash.return_value = None  # File is new

                # Simulate timeout by patching the TimeoutManager
                with patch(
                    "src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync",
                    side_effect=TimeoutError(),
                ):
                    result = self.service.process_single_file(temp_file_path, "test_repo")
                    success, qa_count = result

                    # File should fail due to timeout
                    assert success is False
                    assert qa_count == 0

                    # Verify the failed file was logged
                    self.db_manager.add_failed_file.assert_called_once()
        finally:
            os.unlink(temp_file_path)
