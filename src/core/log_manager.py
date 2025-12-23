"""Log file management and rotation."""

import datetime
import logging
from pathlib import Path

from src.core.config import AppConfig


class LogManager:
    """Manages log file creation, rotation, and cleanup."""

    def __init__(self, logs_dir: str | Path, config: AppConfig):
        """
        Initialize log manager.

        Args:
            logs_dir: Directory to store log files
            config: Application configuration
        """
        self.logs_dir = Path(logs_dir)
        self.config = config
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def create_log_file(self) -> Path:
        """
        Create a new log file with timestamp.

        Returns:
            Path to the created log file
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_name = f"{self.config.model.logging.log_file_prefix}_{timestamp}.log"
        return self.logs_dir / log_file_name

    def cleanup_old_logs(self, max_files: int) -> None:
        """
        Remove old log files to maintain the maximum count.

        Args:
            max_files: Maximum number of log files to retain
        """
        log_files = sorted(
            [f for f in self.logs_dir.iterdir() if f.name.startswith(self.config.model.logging.log_file_prefix) and f.name.endswith(".log")],
            key=lambda f: f.stat().st_mtime,
        )

        if len(log_files) >= max_files:
            files_to_delete = log_files[: len(log_files) - max_files + 1]
            for old_log_file in files_to_delete:
                try:
                    old_log_file.unlink()
                    logging.info(f"Deleted old log file: {old_log_file.name}")
                except OSError as e:
                    logging.error(f"Error deleting old log file {old_log_file.name}: {e}")
