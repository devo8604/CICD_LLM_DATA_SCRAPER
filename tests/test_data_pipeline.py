"""Unit tests for the refactored DataPipeline."""

from unittest.mock import MagicMock, AsyncMock, patch, create_autospec
import pytest
import tempfile
import os

from src.data_pipeline import DataPipeline
from src.config import AppConfig
from src.llm_client import LLMClient
from src.db_manager import DBManager
from src.file_manager import FileManager


class TestDataPipeline:
    """Test cases for the refactored DataPipeline."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.config = AppConfig()
        self.llm_client = MagicMock(spec=LLMClient)
        self.db_manager = MagicMock(spec=DBManager)
        self.file_manager = MagicMock(spec=FileManager)
        
        # Set up file_manager to have the correct method
        self.file_manager.get_all_files_in_repo = MagicMock(return_value=[])
        
        self.pipeline = DataPipeline(
            llm_client=self.llm_client,
            db_manager=self.db_manager,
            file_manager=self.file_manager,
            config=self.config
        )

    def test_initialization(self):
        """Test that DataPipeline initializes correctly with services."""
        # Verify that services were created
        assert self.pipeline.file_processing_service is not None
        assert self.pipeline.repository_service is not None
        assert self.pipeline.state_service is not None
        assert self.pipeline.batch_processing_service is not None
        
        # Verify that config was set correctly
        assert self.pipeline.config == self.config

    @pytest.mark.asyncio
    async def test_scrape_calls_repository_service(self):
        """Test that scrape method calls the repository service."""
        # Mock the repository service to return an awaitable
        mock_repo_service = AsyncMock()
        mock_repo_service.scrape_repositories = AsyncMock()
        self.pipeline.repository_service = mock_repo_service

        with tempfile.TemporaryDirectory() as temp_dir:
            self.pipeline.repos_dir = temp_dir
            await self.pipeline.scrape()

        # Verify the repository service's scrape method was called
        mock_repo_service.scrape_repositories.assert_called_once_with(self.pipeline.repos_dir)

    @pytest.mark.asyncio
    async def test_prepare_calls_cleanup(self):
        """Test that prepare method performs cleanup of non-existent files."""
        # Mock the database to return some tracked files
        tracked_files = ["/path/to/file1.py", "/path/to/file2.py"]
        self.db_manager.get_all_tracked_files.return_value = tracked_files
        
        # Mock file existence - first file exists, second doesn't
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda x: x == "/path/to/file1.py"
            
            with patch('src.data_pipeline.tqdm') as mock_tqdm:
                mock_tqdm.return_value.__enter__ = MagicMock()
                mock_tqdm.return_value.__exit__ = MagicMock()
                
                with patch('os.walk', return_value=[]):  # No repos to process
                    await self.pipeline.prepare()
        
        # Verify that files that don't exist get cleaned up from the database
        self.db_manager.delete_samples_for_file.assert_called_once_with("/path/to/file2.py")
        self.db_manager.delete_file_hash.assert_called_once_with("/path/to/file2.py")

    @pytest.mark.asyncio
    async def test_retry_failed_files(self):
        """Test retrying failed files."""
        # Mock failed files in the database
        failed_files = [("/path/to/failed1.py", "timeout"), ("/path/to/failed2.py", "error")]
        self.db_manager.get_failed_files.return_value = failed_files
        
        # Mock the file processing service to return success
        mock_file_service = MagicMock()
        mock_file_service.process_single_file = AsyncMock(return_value=(True, 1))
        self.pipeline.file_processing_service = mock_file_service
        
        with patch('src.data_pipeline.tqdm'):
            await self.pipeline.retry_failed_files()
        
        # Verify that process_single_file was called for each failed file
        assert mock_file_service.process_single_file.call_count == 2
        
        # Verify that successful files are removed from failed list
        self.db_manager.remove_failed_file.assert_any_call("/path/to/failed1.py")
        self.db_manager.remove_failed_file.assert_any_call("/path/to/failed2.py")

    @pytest.mark.asyncio
    async def test_retry_failed_files_none_to_retry(self):
        """Test retrying when there are no failed files."""
        self.db_manager.get_failed_files.return_value = []

        with patch('src.data_pipeline.tqdm') as mock_tqdm:
            await self.pipeline.retry_failed_files()

        # When there are no failed files, the method returns early without creating any progress bars
        mock_tqdm.assert_not_called()
        # Verify no processing calls were made
        self.db_manager.remove_failed_file.assert_not_called()

    def test_export_data(self):
        """Test data export functionality."""
        # Set up the mock db_manager with a db_path attribute
        self.db_manager.db_path = "/mock/path/pipeline.db"

        # Since the import happens inside the method, we need to patch the exporters module
        with patch('src.exporters.DataExporter') as mock_exporter_class:
            mock_exporter_instance = MagicMock()
            mock_exporter_class.return_value = mock_exporter_instance

            self.pipeline.export_data("alpaca-jsonl", "output.jsonl")

            # Verify the exporter was created and called appropriately
            mock_exporter_class.assert_called_once_with(self.db_manager.db_path)
            mock_exporter_instance.export_data.assert_called_once_with("alpaca-jsonl", "output.jsonl")
            mock_exporter_instance.close.assert_called_once()

    def test_close_calls_db_manager_close(self):
        """Test that close method calls the database manager's close method."""
        self.pipeline.close()
        
        # Verify that the database manager's close method was called
        self.db_manager.close_db.assert_called_once()