"""Unit tests for the BatchProcessingService."""

from unittest.mock import MagicMock

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.pipeline.batch_processing_service import BatchProcessingService
from src.pipeline.file_processing_service import FileProcessingService


class TestBatchProcessingService:
    """Test cases for BatchProcessingService."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.config = AppConfig()
        self.file_processing_service = MagicMock(spec=FileProcessingService)
        self.db_manager = MagicMock(spec=DBManager)
        self.service = BatchProcessingService(
            file_processing_service=self.file_processing_service,
            db_manager=self.db_manager,
            config=self.config,
        )

    def test_process_files_batch_single_file(self):
        """Test processing a batch with a single file."""
        files = ["/path/to/file1.py"]
        repo_name = "test_repo"

        # Mock the file processing result
        self.file_processing_service.process_single_file = MagicMock(return_value=(True, 2))

        results = self.service.process_files_batch(
            files=files,
            repo_name=repo_name,
            batch_num=1,
            total_batches=1,
        )

        # Verify the result
        assert len(results) == 1
        file_path, success, qa_count = results[0]
        assert file_path == "/path/to/file1.py"
        assert success is True
        assert qa_count == 2

        # Verify the file processing service was called correctly
        self.file_processing_service.process_single_file.assert_called_once()

    def test_process_files_batch_multiple_files(self):
        """Test processing a batch with multiple files."""
        files = ["/path/to/file1.py", "/path/to/file2.py", "/path/to/file3.py"]
        repo_name = "test_repo"

        # Mock the file processing results
        def mock_process_single_file(file_path, repo_name, pbar=None, cancellation_event=None):
            if "file1" in file_path:
                return (True, 1)
            elif "file2" in file_path:
                return (False, 0)  # Failed
            else:  # file3
                return (True, 3)

        self.file_processing_service.process_single_file = MagicMock(side_effect=mock_process_single_file)

        results = self.service.process_files_batch(
            files=files,
            repo_name=repo_name,
            batch_num=1,
            total_batches=1,
        )

        # Verify all results
        assert len(results) == 3

        # Check each result
        file_path1, success1, qa_count1 = results[0]
        file_path2, success2, qa_count2 = results[1]
        file_path3, success3, qa_count3 = results[2]

        assert file_path1 == "/path/to/file1.py" and success1 is True and qa_count1 == 1
        assert file_path2 == "/path/to/file2.py" and success2 is False and qa_count2 == 0
        assert file_path3 == "/path/to/file3.py" and success3 is True and qa_count3 == 3

    def test_process_files_batch_empty_list(self):
        """Test processing an empty batch."""
        results = self.service.process_files_batch(
            files=[],
            repo_name="test_repo",
            batch_num=1,
            total_batches=1,
        )

        # Should return empty list
        assert len(results) == 0

    def test_process_files_batch_exception_handling(self):
        """Test that exceptions in individual tasks are handled properly."""
        files = ["/path/to/file1.py"]
        repo_name = "test_repo"

        # Mock to raise an exception during file processing
        self.file_processing_service.process_single_file = MagicMock(side_effect=Exception("Processing error"))

        # Should handle the exception without crashing and return failure record
        results = self.service.process_files_batch(
            files=files,
            repo_name=repo_name,
            batch_num=1,
            total_batches=1,
        )

        # Should return a failure result for the problematic file, not crash
        assert len(results) == 1
        file_path, success, qa_count = results[0]
        assert file_path == "/path/to/file1.py"
        assert success is False  # File processing failed
        assert qa_count == 0  # No Q&A pairs generated
