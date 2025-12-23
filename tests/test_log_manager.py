"""Unit tests for the LogManager class."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.config import AppConfig
from src.core.log_manager import LogManager


class TestLogManager:
    """Test cases for LogManager."""

    def test_initialization(self):
        """Test LogManager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            config = MagicMock(spec=AppConfig)

            manager = LogManager(logs_dir, config)

            assert manager.logs_dir == logs_dir
            assert logs_dir.exists()

    def test_create_log_file(self):
        """Test log file name generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            config = MagicMock(spec=AppConfig)
            config.LOG_FILE_PREFIX = "test_log"
            config.model.logging.log_file_prefix = "test_log"

            manager = LogManager(logs_dir, config)
            log_file = manager.create_log_file()

            assert log_file.parent == logs_dir
            assert log_file.name.startswith("test_log_")
            assert log_file.name.endswith(".log")

    def test_cleanup_old_logs(self):
        """Test cleanup of old log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            config = MagicMock(spec=AppConfig)
            config.LOG_FILE_PREFIX = "test_log"
            config.model.logging.log_file_prefix = "test_log"

            manager = LogManager(logs_dir, config)

            # Create dummy log files
            for i in range(5):
                log_file = logs_dir / f"test_log_{i}.log"
                log_file.write_text(f"content {i}")
                # Set access/mod times to ensure deterministic sorting
                # (Lower index = older)
                mtime = 1000 + i
                import os

                os.utime(log_file, (mtime, mtime))

            # Initial count
            assert len(list(logs_dir.glob("test_log_*.log"))) == 5

            # Cleanup to keep 3
            # Logic: if len >= max_files (5 >= 3), delete (5 - 3 + 1) = 3 files.
            # wait, LogManager code:
            # if len(log_files) >= max_files:
            #     files_to_delete = log_files[: len(log_files) - max_files + 1]

            manager.cleanup_old_logs(3)

            # Should have 2 left (5 - 3 = 2)
            remaining_files = sorted(list(logs_dir.glob("test_log_*.log")))
            assert len(remaining_files) == 2
            # The 3 oldest should be gone: 0, 1, 2. Files 3 and 4 remain.
            assert remaining_files[0].name == "test_log_3.log"
            assert remaining_files[1].name == "test_log_4.log"

    def test_cleanup_old_logs_below_limit(self):
        """Test cleanup when below limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            config = MagicMock(spec=AppConfig)
            config.LOG_FILE_PREFIX = "test_log"
            config.model.logging.log_file_prefix = "test_log"

            manager = LogManager(logs_dir, config)

            # Create 2 files
            (logs_dir / "test_log_1.log").write_text("1")
            (logs_dir / "test_log_2.log").write_text("2")

            manager.cleanup_old_logs(5)

            assert len(list(logs_dir.glob("test_log_*.log"))) == 2

    def test_cleanup_old_logs_error_handling(self):
        """Test error handling during log deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            config = MagicMock(spec=AppConfig)
            config.LOG_FILE_PREFIX = "test_log"
            config.model.logging.log_file_prefix = "test_log"

            manager = LogManager(logs_dir, config)

            log_file = logs_dir / "test_log_1.log"
            log_file.write_text("content")

            with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
                # Should not raise exception
                manager.cleanup_old_logs(1)
