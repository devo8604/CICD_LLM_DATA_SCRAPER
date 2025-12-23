from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.data.file_manager import FileManager
from src.pipeline.batch_processing_service import BatchProcessingService
from src.pipeline.file_processing_service import FileProcessingService
from src.pipeline.preparation_service import PreparationService
from src.pipeline.state_management_service import StateManagementService


class TestPreparationService:
    @pytest.fixture
    def mock_db_manager(self):
        return MagicMock(spec=DBManager)

    @pytest.fixture
    def mock_file_manager(self):
        return MagicMock(spec=FileManager)

    @pytest.fixture
    def mock_file_processing(self):
        mock = MagicMock(spec=FileProcessingService)
        # Mock the llm_client attribute
        mock.llm_client = MagicMock()
        return mock

    @pytest.fixture
    def mock_batch_processing(self):
        return MagicMock(spec=BatchProcessingService)

    @pytest.fixture
    def mock_state_service(self):
        service = MagicMock(spec=StateManagementService)
        service.state = {
            "current_repo_name": None,
            "processed_repos_count": 0,
            "current_file_path_in_repo": None,
            "processed_files_count_in_repo": 0,
        }
        return service

    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.BASE_DIR = "."
        config.MAX_CONCURRENT_FILES = 1
        config.FILE_BATCH_SIZE = 10
        config.BATTERY_LOW_THRESHOLD = 15
        config.BATTERY_HIGH_THRESHOLD = 90
        config.BATTERY_CHECK_INTERVAL = 60

        # Mock model properties
        config.model.pipeline.base_dir = "."
        config.model.processing.max_concurrent_files = 1
        config.model.processing.file_batch_size = 10

        return config

    @pytest.fixture
    def service(
        self,
        mock_db_manager,
        mock_file_manager,
        mock_file_processing,
        mock_batch_processing,
        mock_state_service,
        mock_config,
    ):
        return PreparationService(
            mock_db_manager,
            mock_file_manager,
            mock_file_processing,
            mock_batch_processing,
            mock_state_service,
            mock_config,
        )

    def test_cleanup_tracked_files(self, service):
        service.db_manager.get_all_tracked_files.return_value = [
            "exist.txt",
            "gone.txt",
        ]

        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: p == "exist.txt"

            service._cleanup_tracked_files()

            service.db_manager.delete_samples_for_file.assert_called_with("gone.txt")
            service.db_manager.delete_file_hash.assert_called_with("gone.txt")
            assert service.db_manager.delete_samples_for_file.call_count == 1

    def test_discover_repositories_and_files(self, service):
        service.repos_dir = "/repos"

        with patch("os.walk") as mock_walk:
            # Structure: /repos/repo1/.git, /repos/repo2/.git
            mock_walk.return_value = [
                ("/repos", ["repo1", "repo2"], []),
                ("/repos/repo1", [".git"], []),
                ("/repos/repo2", [".git"], []),
            ]

            # Since the code checks for ".git" in dirs during os.walk of repos_dir?
            # Code:
            # for root, dirs, files in os.walk(self.repos_dir):
            #   if ".git" in dirs: all_repos.append(root); dirs[:] = []

            # So if /repos/repo1 contains .git, it is added.

            # Re-mocking correctly for the logic:
            mock_walk.return_value = [
                ("/repos", ["repo1", "repo2"], []),
                ("/repos/repo1", [".git"], ["f1.txt"]),
                ("/repos/repo2", [".git"], ["f2.txt"]),
            ]

            service.file_manager.get_all_files_in_repo.side_effect = lambda r: [r + "/f.txt"]

            repos, total_files, files_map = service._discover_repositories_and_files()

            assert len(repos) == 2
            assert "/repos/repo1" in repos
            assert "/repos/repo2" in repos
            assert total_files == 2

    def test_get_repo_start_index(self, service):
        all_repos = ["r1", "r2", "r3"]
        service.state_service.state["current_repo_name"] = "r2"

        index = service._get_repo_start_index(all_repos)
        assert index == 1

        service.state_service.state["current_repo_name"] = "unknown"
        index = service._get_repo_start_index(all_repos)
        assert index == 0
        assert service.state_service.state["current_repo_name"] is None

    def test_process_files_sequentially(self, service):
        files = ["f1.txt", "f2.txt"]
        repo_name = "repo1"
        pbar = MagicMock()

        service.file_processing_service.process_single_file.return_value = (True, 10)

        with patch("src.pipeline.preparation_service.tqdm"):
            service._process_files_sequentially(files, repo_name, pbar)

        assert service.file_processing_service.process_single_file.call_count == 2
        pbar.update.assert_called()

    def test_process_files_concurrently(self, service):
        service.config.MAX_CONCURRENT_FILES = 2
        files = ["f1.txt", "f2.txt", "f3.txt"]
        repo_name = "repo1"
        pbar = MagicMock()

        service._process_files_concurrently(files, repo_name, pbar)

        service.batch_processing_service.process_files_batch.assert_called()
        # Should be called once since batch size is 10 and we have 3 files
        assert service.batch_processing_service.process_files_batch.call_count == 1

    def test_prepare_flow(self, service):
        # Mock everything to test the main flow
        with (
            patch.object(service, "_cleanup_tracked_files") as mock_cleanup,
            patch.object(service, "_discover_repositories_and_files") as mock_discover,
            patch.object(service, "_process_repositories") as mock_process,
        ):
            mock_discover.return_value = (["r1"], 1, {"r1": ["f1"]})

            service.prepare()

            mock_cleanup.assert_called()
            mock_discover.assert_called()
            mock_process.assert_called()
            service.state_service.reset_state.assert_called()
            service.db_manager.close_db.assert_called()

    def test_process_repositories_cancellation(self, service):
        cancellation_event = MagicMock()
        cancellation_event.is_set.return_value = True

        with patch("src.pipeline.preparation_service.tqdm"):
            service._process_repositories(["r1"], {}, 0, cancellation_event)

        # Should break immediately
        # We can verify by mocking _process_single_repository
        with patch.object(service, "_process_single_repository") as mock_single:
            with patch("src.pipeline.preparation_service.tqdm"):
                service._process_repositories(["r1"], {}, 0, cancellation_event)
                mock_single.assert_not_called()

    def test_get_file_start_index(self, service):
        files = ["dir/f1", "dir/f2", "dir/f3"]
        service.state_service.state["current_file_path_in_repo"] = "dir/f2"

        index = service._get_file_start_index(files)
        assert index == 1
