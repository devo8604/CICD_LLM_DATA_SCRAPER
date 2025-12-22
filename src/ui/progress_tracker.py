"""Progress tracking for the LLM data pipeline."""

import logging
import time
from pathlib import Path

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class ProgressTracker:
    """Tracks hierarchical progress of the pipeline."""

    def __init__(self):
        self.total_repos = 0
        self.current_repo_index = 0
        self.current_repo_name = ""
        self.current_repo_files_total = 0
        self.current_repo_files_processed = 0
        self.total_files = 0
        self.files_processed = 0
        self.current_file_path = ""
        self.current_file_size = 0  # Size of current file in bytes
        self.current_file_progress = 0.0  # Percentage within current file (Q&A generation)
        self.start_time = None
        self.model_name = "Unknown"
        self.backend = "Unknown"

    def start(self) -> None:
        """Start the timer for progress tracking."""
        self.start_time = time.time()

    def set_model_name(self, name: str) -> None:
        """Set the name of the model being used."""
        self.model_name = name

    def set_backend(self, backend: str) -> None:
        """Set the LLM backend being used."""
        self.backend = backend

    def update_total_repos(self, count: int) -> None:
        self.total_repos = count

    def update_current_repo(self, index: int, name: str, total_files: int) -> None:
        self.current_repo_index = index
        self.current_repo_name = name
        self.current_repo_files_total = total_files
        self.current_repo_files_processed = 0

    def update_current_file(self, file_path: str) -> None:
        """Update the current file path being processed."""
        self.current_file_path = file_path

    def update_current_file_with_size(self, file_path: str, file_size: int) -> None:
        """Update the current file path and size being processed."""
        self.current_file_path = file_path
        self.current_file_size = file_size

    def increment_repo_files_processed(self) -> None:
        self.current_repo_files_processed += 1
        self.files_processed += 1

    def update_total_files(self, count: int) -> None:
        self.total_files = count

    def update_file_progress(self, percentage: float) -> None:
        """Update progress within the current file (0.0 to 100.0)."""
        self.current_file_progress = percentage

    @property
    def overall_progress(self) -> float:
        if self.total_files > 0:
            return (self.files_processed / self.total_files) * 100
        return 0.0

    def get_progress_summary(self) -> dict:
        elapsed = 0
        if self.start_time:
            elapsed = time.time() - self.start_time

        return {
            "overall_progress": self.overall_progress,
            "total_progress": self.overall_progress,  # Legacy key for backward compatibility
            "total_repos": self.total_repos,
            "current_repo_index": self.current_repo_index,
            "current_repo_name": self.current_repo_name,
            "current_repo_files_total": self.current_repo_files_total,
            "current_repo_files_processed": self.current_repo_files_processed,
            "current_file_path": self.current_file_path,
            "current_file_size": self.current_file_size,
            "current_file_progress": self.current_file_progress,
            "total_files": self.total_files,
            "files_processed": self.files_processed,
            "elapsed_time": elapsed,
            "model_name": self.model_name,
            "backend": self.backend,
        }

    def format_progress_string(self) -> str:
        """Format a detailed progress string for logging/display."""
        return self.get_detailed_progress_string()

    def get_detailed_progress_string(self) -> str:
        """Get detailed progress string (used by tests)."""
        if self.total_repos == 0:
            return "No repositories to process"

        # Overall progress
        overall_part = f"Overall: {self.overall_progress:.1f}% ({self.files_processed}/{self.total_files} files)"

        # Current repository
        repo_part = (
            f"Repo: {self.current_repo_index + 1}/{self.total_repos} - {self.current_repo_name or 'Processing...'}"
        )

        # Current repository progress
        if self.current_repo_files_total > 0:
            repo_progress = min(
                100.0,
                (self.current_repo_files_processed / self.current_repo_files_total) * 100,
            )
            repo_detail = (
                f"Files: {self.current_repo_files_processed}/{self.current_repo_files_total} "
                f"files ({repo_progress:.1f}%)"
            )
        else:
            repo_detail = "Repo: 0/0 files"

        # Current file
        if self.current_file_path:
            basename = Path(self.current_file_path).name
            current_file_part = f"File: {basename[:50]}{'...' if len(basename) > 50 else ''}"
        else:
            current_file_part = "File: Starting next..."

        result = f"{overall_part} | {repo_part} | {repo_detail} | {current_file_part}"
        return result


# Global progress tracker instance
_global_tracker: ProgressTracker | None = None


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker singleton."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ProgressTracker()
    return _global_tracker
