from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.pipeline.export_service import ExportService
from src.pipeline.file_processing_service import FileProcessingService
from src.pipeline.orchestration_service import OrchestrationService
from src.pipeline.repository_service import RepositoryService
from src.pipeline.retry_service import RetryService
from src.pipeline.scraping_service import ScrapingService


class TestExportService:
        @patch("src.pipeline.export_service.DataExporter")
        def test_export_success(self, mock_exporter_cls):
            mock_db_manager = MagicMock(spec=DBManager)
            mock_db_manager.db_path = "db.sqlite"
            from src.core.config import AppConfig
            mock_config = AppConfig()

            service = ExportService(mock_db_manager, mock_config)
            service.export("template", "output.json")

            # DataExporter is called with both db_manager and config (both are required now)
            mock_exporter_cls.assert_called()
            # Check that the call was made with both db_manager and config
            call_args = mock_exporter_cls.call_args
            assert call_args[0][0] == mock_db_manager  # First arg is db_manager
            assert call_args[0][1] is not None  # Second arg is config
            mock_exporter_cls.return_value.export_data.assert_called_with("template", "output.json")

        @patch("src.pipeline.export_service.DataExporter")
        def test_export_failure(self, mock_exporter_cls):
            mock_db_manager = MagicMock(spec=DBManager)
            mock_db_manager.db_path = "db.sqlite"
            from src.core.config import AppConfig
            mock_config = AppConfig()
            mock_exporter_cls.return_value.export_data.side_effect = Exception("Fail")

            service = ExportService(mock_db_manager, mock_config)
            service.export("template", "output.json")

            # Verify export_data was attempted
            mock_exporter_cls.return_value.export_data.assert_called()

class TestScrapingService:
    def test_scrape(self):
        mock_repo_service = MagicMock(spec=RepositoryService)
        mock_config = MagicMock(spec=AppConfig)
        mock_config.BASE_DIR = "."

        service = ScrapingService(mock_repo_service, mock_config)
        service.scrape(progress_callback=lambda: None)

        mock_repo_service.scrape_repositories.assert_called()


class TestOrchestrationService:
    def test_orchestration_methods(self):
        container = MagicMock()
        config = MagicMock()

        service = OrchestrationService(container, config)

        # Test scrape
        mock_scraping = MagicMock()
        container.get.return_value = mock_scraping
        service.scrape()
        mock_scraping.scrape.assert_called()

        # Test prepare
        mock_prep = MagicMock()
        container.get.return_value = mock_prep
        service.prepare()
        mock_prep.prepare.assert_called()

        # Test retry
        mock_retry = MagicMock()
        container.get.return_value = mock_retry
        service.retry()
        mock_retry.retry.assert_called()

        # Test export
        mock_export = MagicMock()
        container.get.return_value = mock_export
        service.export("t", "o")
        mock_export.export.assert_called_with("t", "o")

        # Test close
        mock_db = MagicMock()
        container.get.return_value = mock_db
        service.close()
        mock_db.close_db.assert_called()


class TestRetryService:
    @pytest.fixture
    def mock_db_manager(self):
        return MagicMock(spec=DBManager)

    @pytest.fixture
    def mock_file_processing(self):
        return MagicMock(spec=FileProcessingService)

    @pytest.fixture
    def retry_service(self, mock_db_manager, mock_file_processing):
        return RetryService(mock_db_manager, mock_file_processing)

    def test_retry_no_failed_files(self, retry_service):
        retry_service.db_manager.get_failed_files.return_value = []
        retry_service.retry()
        retry_service.file_processing_service.process_single_file.assert_not_called()
        retry_service.db_manager.close_db.assert_not_called()  # wait, checks source code

        # Source code says: if not failed_files: return (so close_db NOT called)
        # Verify source code:
        # if not failed_files: ... return
        # ...
        # self.db_manager.close_db() is at end
        pass

    def test_retry_success(self, retry_service):
        retry_service.db_manager.get_failed_files.return_value = [("file1.txt", "reason")]
        retry_service.file_processing_service.process_single_file.return_value = (
            True,
            5,
        )

        with patch("src.pipeline.retry_service.tqdm"):
            retry_service.retry()

        retry_service.file_processing_service.process_single_file.assert_called()
        retry_service.db_manager.remove_failed_file.assert_called_with("file1.txt")
        retry_service.db_manager.close_db.assert_called()

    def test_retry_failure(self, retry_service):
        retry_service.db_manager.get_failed_files.return_value = [("file1.txt", "reason")]
        retry_service.file_processing_service.process_single_file.return_value = (
            False,
            0,
        )

        with patch("src.pipeline.retry_service.tqdm"):
            retry_service.retry()

        retry_service.db_manager.remove_failed_file.assert_not_called()
        retry_service.db_manager.close_db.assert_called()
