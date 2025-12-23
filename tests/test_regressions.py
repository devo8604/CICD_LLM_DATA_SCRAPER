"""Regression tests to ensure previously fixed bugs do not reappear."""

import os
from unittest.mock import MagicMock, patch

from src.core.error_handling import TimeoutManager
from src.llm.llm_client import LLMClient
from src.pipeline.file_processing_service import FileProcessingService


class TestRegressions:
    """Test cases for preventing previously fixed bugs."""

    def test_timeout_manager_run_with_timeout_sync_signature(self):
        """
        REGRESSION TEST: Ensure TimeoutManager.run_with_timeout_sync has the correct signature.
        We once had a bug where the arguments (func, timeout) were swapped in calls.
        The correct signature is (func, timeout, *args, **kwargs).
        """

        def mock_func(arg1, arg2):
            return f"{arg1}-{arg2}"

        # If arguments were swapped (timeout, func), this would raise a TypeError
        # because it would try to call 'int' (timeout) as a function.
        result = TimeoutManager.run_with_timeout_sync(mock_func, 5.0, "val1", "val2")
        assert result == "val1-val2"

    def test_file_processing_service_calls_timeout_manager_correctly(self):
        """
        REGRESSION TEST: Ensure FileProcessingService calls run_with_timeout_sync with correct arg order.
        We once had a bug where it was called as run_with_timeout_sync(timeout, func, ...).
        """
        mock_llm = MagicMock(spec=LLMClient)
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.model.llm.max_retries = 1
        mock_config.model.generation.default_temperature = 0.7
        mock_config.model.generation.default_max_tokens = 100
        mock_config.model.processing.chunk_read_size = 4096

        service = FileProcessingService(mock_llm, mock_db, mock_config)

        # Mock dependencies to reach the run_with_timeout_sync call
        with (
            patch("os.path.isfile", return_value=True),
            patch.object(service, "calculate_file_hash", return_value="hash"),
            patch.object(mock_db, "get_file_hash", return_value=None),
            patch.object(service, "_read_file_content", return_value="content"),
            patch("src.pipeline.file_processing_service.calculate_dynamic_timeout", return_value=30),
            patch("src.pipeline.file_processing_service.TimeoutManager.run_with_timeout_sync") as mock_timeout_run,
        ):
            # We don't care about the return value, just the call signature
            mock_timeout_run.return_value = ["Q1?"]

            # Trigger the implementation
            service._process_single_file_impl("test.txt", "repo")

            # Verify the first argument is a callable, not an integer
            args, _ = mock_timeout_run.call_args
            assert callable(args[0]), f"First argument to run_with_timeout_sync should be callable, got {type(args[0])}"
            assert isinstance(args[1], int | float), f"Second argument to run_with_timeout_sync should be timeout (number), got {type(args[1])}"

    def test_calculate_dynamic_timeout_received_path_not_content(self):
        """
        REGRESSION TEST: Ensure calculate_dynamic_timeout receives a file path, not content.
        We once had a bug where 'content' string was passed, which caused issues if content
        happened to be a valid short path or caused os.path.getsize to fail.
        """
        # We'll use a real file to be sure
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"some content")
            tmp_path = tmp.name

        try:
            with patch("os.path.getsize") as mock_getsize:
                mock_getsize.return_value = 100
                from src.core.utils import calculate_dynamic_timeout

                # Correct usage: path string
                calculate_dynamic_timeout(tmp_path)
                mock_getsize.assert_called_once_with(tmp_path)

                # If it were passed content, it would look like this:
                # calculate_dynamic_timeout("some content")
                # and mock_getsize would be called with "some content"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_llm_client_lazy_initialization_regression(self):
        """
        REGRESSION TEST: Ensure LLMClient doesn't perform network operations in __init__.
        """
        mock_config = MagicMock()
        mock_config.model.pipeline.prompt_theme = "devops"
        mock_config.model.llm.model_cache_ttl = 300

        with patch("httpx.Client") as mock_client:
            # Instantiation should NOT trigger any httpx calls
            _ = LLMClient(
                base_url="http://localhost:8000",
                model_name="test-model",
                max_retries=3,
                retry_delay=5,
                config=mock_config,
            )
            mock_client.assert_not_called()
