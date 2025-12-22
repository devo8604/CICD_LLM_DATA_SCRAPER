import hashlib
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.llm.llm_client import LLMClient
from src.pipeline.file_processing_service import FileProcessingService


class TestFileProcessingServiceFull:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.CHUNK_READ_SIZE = 100
        config.LLM_REQUEST_TIMEOUT = 1
        config.LLM_MAX_RETRIES = 2
        config.DEFAULT_TEMPERATURE = 0.7
        config.DEFAULT_MAX_TOKENS = 500
        config.USE_MLX = False
        return config

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=DBManager)
        db.training_data_repo = MagicMock()
        return db

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock(spec=LLMClient)
        # Ensure it doesn't look like an MLX client unless we want it to
        if hasattr(llm, 'context_window'):
            del llm.context_window
        return llm

    @pytest.fixture
    def service(self, mock_llm, mock_db, mock_config):
        return FileProcessingService(mock_llm, mock_db, mock_config)

    def test_calculate_file_hash_success(self, service):
        file_content = b"content"
        expected_hash = hashlib.sha256(file_content).hexdigest()

        with patch("builtins.open", mock_open(read_data=file_content)):
            hash_val = service.calculate_file_hash("file.txt")
            assert hash_val == expected_hash

    def test_calculate_file_hash_os_error(self, service):
        with patch("builtins.open", side_effect=OSError("Error")):
            assert service.calculate_file_hash("file.txt") is None

    def test_calculate_file_hash_unexpected_error(self, service):
        with patch("builtins.open", side_effect=Exception("Error")):
            assert service.calculate_file_hash("file.txt") is None

    def test_process_file_context_mlx_clear(self, service):
        service.config.USE_MLX = True
        service.llm_client.clear_mlx_memory = MagicMock()
        service._processed_count = 9  # Set to 9 so increment makes it 10

        with service._process_file_context("file.txt"):
            pass

        service.llm_client.clear_mlx_memory.assert_called()

    def test_read_file_content_success(self, service):
        with patch("builtins.open", mock_open(read_data="content")):
            with patch("src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync") as mock_run:
                mock_run.side_effect = lambda f, t, *args, **kwargs: f(*args, **kwargs)

                content = service._read_file_content("file.txt")
                assert content == "content"

    def test_read_file_content_timeout(self, service):
        with patch(
            "src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync",
            side_effect=TimeoutError,
        ):
            assert service._read_file_content("file.txt") is None

    def test_read_file_content_errors(self, service):
        with patch("src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync") as mock_run:
            mock_run.side_effect = lambda f, t, *args, **kwargs: f(*args, **kwargs)

            # UnicodeDecodeError
            with patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "")):
                assert service._read_file_content("file.txt") is None

            # FileNotFoundError
            with patch("builtins.open", side_effect=FileNotFoundError):
                assert service._read_file_content("file.txt") is None

    def test_process_single_file_not_isfile(self, service):
        with patch("os.path.isfile", return_value=False):
            success, count = service.process_single_file("dir", "repo")
            assert success is True
            assert count == 0

    def test_process_single_file_hash_fail(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value=None),
        ):
            success, count = service.process_single_file("file.txt", "repo")
            assert success is False

    def test_process_single_file_unchanged(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="hash"),
            patch.object(service.db_manager, "get_file_hash", return_value="hash"),
        ):
            success, count = service.process_single_file("file.txt", "repo")
            assert success is True
            assert count == 0

    def test_process_single_file_read_fail(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="new_hash"),
            patch.object(service.db_manager, "get_file_hash", return_value="old_hash"),
            patch.object(service, "_read_file_content", return_value=None),
        ):
            success, count = service.process_single_file("file.txt", "repo")
            assert success is False
            service.db_manager.add_failed_file.assert_called()

    def test_process_single_file_empty(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="new_hash"),
            patch.object(service.db_manager, "get_file_hash", return_value="old_hash"),
            patch.object(service, "_read_file_content", return_value="   "),
        ):
            success, count = service.process_single_file("file.txt", "repo")
            assert success is True
            assert count == 0

    def test_process_single_file_full_flow(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="new_hash"),
            patch.object(service.db_manager, "get_file_hash", return_value="old_hash"),
            patch.object(service, "_read_file_content", return_value="content"),
            patch("src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync") as mock_timeout,
            patch("src.ui.progress_tracker.get_progress_tracker"),
        ):
            # Ensure LLM client is NOT MLX
            if hasattr(service.llm_client, 'context_window'):
                del service.llm_client.context_window

            # timeout called for generate_questions then get_answer_single
            mock_timeout.side_effect = [
                ["Q1"],  # generate_questions
                "A1",  # get_answer_single
            ]

            service.db_manager.get_processed_question_hashes.return_value = []

            success, count = service.process_single_file("file.txt", "repo")

            assert success is True
            assert count == 1
            service.db_manager.training_data_repo.add_qa_samples_batch.assert_called_once_with(
                "file.txt", [("Q1", "A1")]
            )
            service.db_manager.save_file_hash.assert_called_with("file.txt", "new_hash")

    def test_process_single_file_generation_error(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="new_hash"),
            patch.object(service.db_manager, "get_file_hash", return_value="old_hash"),
            patch.object(service, "_read_file_content", return_value="content"),
            patch("src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync") as mock_timeout,
            patch("time.sleep"),
        ):
            # Ensure LLM client is NOT MLX
            if hasattr(service.llm_client, 'context_window'):
                del service.llm_client.context_window

            # Raise exception on all attempts
            mock_timeout.side_effect = Exception("LLM Error")

            success, count = service.process_single_file("file.txt", "repo")

            assert success is False
            service.db_manager.add_failed_file.assert_called()

    def test_process_single_file_retry_logic(self, service):
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="new_hash"),
            patch.object(service.db_manager, "get_file_hash", return_value="old_hash"),
            patch.object(service, "_read_file_content", return_value="content"),
            patch("src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync") as mock_timeout,
            patch("time.sleep"),
            patch("src.ui.progress_tracker.get_progress_tracker"),
        ):
            # Ensure LLM client is NOT MLX
            if hasattr(service.llm_client, 'context_window'):
                del service.llm_client.context_window

            # 1. Fail generate, 2. Succeed generate, 3. Succeed answer
            mock_timeout.side_effect = [Exception("Fail"), ["Q1"], "A1"]

            service.db_manager.get_processed_question_hashes.return_value = []

            success, count = service.process_single_file("file.txt", "repo")

            assert success is True
            assert count == 1
            service.db_manager.training_data_repo.add_qa_samples_batch.assert_called_once_with(
                "file.txt", [("Q1", "A1")]
            )
