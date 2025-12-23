"""Disk space management utilities for automatic cleanup of temporary files."""

import logging
import shutil
import time
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


class DiskCleanupManager:
    """Manages automatic cleanup of temporary files and disk space management."""

    def __init__(self, config):
        self.config = config
        # Handle cases where config attributes might not be available (e.g. in tests)
        try:
            self.data_dir = Path(config.DATA_DIR)
        except AttributeError:
            # For testing, default to current directory
            self.data_dir = Path("data")

        try:
            self.repos_dir = Path(config.REPOS_DIR)
        except AttributeError:
            # For testing, default to repos directory
            self.repos_dir = Path("repos")

        try:
            self.logs_dir = Path(config.LOGS_DIR)
        except AttributeError:
            # For testing, default to logs directory
            self.logs_dir = Path("logs")

    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Remove log files older than specified days.

        Args:
            days_to_keep: Number of days to keep log files

        Returns:
            Number of files removed
        """
        if not self.logs_dir.exists():
            return 0

        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        removed_count = 0

        for log_file in self.logs_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    removed_count += 1
                    logger.info(f"Removed old log file: {log_file}")
                except Exception as e:
                    logger.error(f"Failed to remove log file {log_file}: {e}")

        return removed_count

    def cleanup_empty_directories(self, base_path: Path) -> int:
        """Recursively remove empty directories.

        Args:
            base_path: Base directory to clean up

        Returns:
            Number of directories removed
        """
        if not base_path.exists():
            return 0

        removed_count = 0

        # Walk bottom-up to remove leaf directories first
        for root, dirs, files in list(Path.walk(base_path, topdown=False)):
            for d in dirs:
                dir_path = Path(root) / d
                try:
                    # Only remove if it's a directory and empty
                    if dir_path.is_dir() and not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        removed_count += 1
                        logger.debug(f"Removed empty directory: {dir_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove directory {dir_path}: {e}")

        return removed_count

    def cleanup_temp_files(self) -> int:
        """Remove temporary files that may have been left by processing.

        Returns:
            Number of files removed
        """
        removed_count = 0

        # Remove any temporary files with common temp extensions
        temp_patterns = ["*.tmp", "*.temp", "*.tmp_*", "*_tmp", "*.bak", "*.backup"]

        # Search in data and repos directories
        for search_dir in [self.data_dir, self.repos_dir]:
            if not search_dir.exists():
                continue

            for pattern in temp_patterns:
                for temp_file in search_dir.rglob(pattern):
                    try:
                        if temp_file.is_file():
                            temp_file.unlink()
                            removed_count += 1
                            logger.debug(f"Removed temp file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temp file {temp_file}: {e}")

        return removed_count

    def cleanup_old_repos(self, days_to_keep: int = 180) -> int:
        """Remove repository clones older than specified days if they're not in use.

        Args:
            days_to_keep: Number of days to keep repository clones

        Returns:
            Number of directories removed
        """
        if not self.repos_dir.exists():
            return 0

        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        removed_count = 0

        for org_dir in self.repos_dir.iterdir():
            if org_dir.is_dir() and not org_dir.name.startswith("."):
                for repo_dir in org_dir.iterdir():
                    if repo_dir.is_dir() and not repo_dir.name.startswith("."):
                        # Check if this repo is in the current repos.txt
                        repos_file = Path("repos.txt")
                        should_keep = False

                        if repos_file.exists():
                            try:
                                with open(repos_file) as f:
                                    repos_content = f.read()
                                    # Check if this repo directory name appears in repos file
                                    if repo_dir.name in repos_content:
                                        should_keep = True
                            except Exception:
                                logger.warning("Could not check repos.txt, keeping all repos")
                                should_keep = True

                        if not should_keep and repo_dir.stat().st_mtime < cutoff_time:
                            try:
                                shutil.rmtree(repo_dir)
                                removed_count += 1
                                logger.info(f"Removed old repository: {repo_dir}")
                            except Exception as e:
                                logger.error(f"Failed to remove repo directory {repo_dir}: {e}")

        return removed_count

    def get_disk_usage_percent(self) -> float:
        """Get current disk usage percentage for the data directory."""
        try:
            usage = psutil.disk_usage(str(self.data_dir))
            return (usage.used / usage.total) * 100
        except Exception:
            # Fallback to checking the root of the data dir
            try:
                usage = psutil.disk_usage(str(self.data_dir.parent))
                return (usage.used / usage.total) * 100
            except Exception:
                logger.warning("Could not determine disk usage")
                return 0.0

    def cleanup_if_needed(self, threshold_percent: float = 80.0) -> dict:
        """Perform cleanup if disk usage exceeds threshold.

        Args:
            threshold_percent: Disk usage percentage threshold for cleanup

        Returns:
            Dictionary with cleanup statistics
        """
        disk_usage = self.get_disk_usage_percent()
        logger.info(f"Current disk usage: {disk_usage:.1f}%")

        stats = {"disk_usage_before": disk_usage, "log_files_removed": 0, "empty_dirs_removed": 0, "temp_files_removed": 0, "old_repos_removed": 0}

        if disk_usage > threshold_percent:
            logger.warning(f"Disk usage {disk_usage:.1f}% exceeds threshold {threshold_percent}%, performing cleanup...")

            # Perform various cleanup operations
            stats["log_files_removed"] = self.cleanup_old_logs()
            stats["temp_files_removed"] = self.cleanup_temp_files()
            stats["empty_dirs_removed"] = self.cleanup_empty_directories(self.repos_dir)
            stats["old_repos_removed"] = self.cleanup_old_repos()

            # Update disk usage after cleanup
            stats["disk_usage_after"] = self.get_disk_usage_percent()
            logger.info(f"Cleanup completed. Disk usage after: {stats['disk_usage_after']:.1f}%")
        else:
            stats["disk_usage_after"] = disk_usage

        return stats

    def force_cleanup(self) -> dict:
        """Perform comprehensive cleanup regardless of disk usage.

        Returns:
            Dictionary with cleanup statistics
        """
        logger.info("Starting comprehensive disk cleanup...")

        stats = {
            "log_files_removed": self.cleanup_old_logs(),
            "temp_files_removed": self.cleanup_temp_files(),
            "empty_dirs_removed": self.cleanup_empty_directories(self.repos_dir),
            "old_repos_removed": self.cleanup_old_repos(),
        }

        stats["disk_usage_after"] = self.get_disk_usage_percent()
        logger.info(f"Comprehensive cleanup completed. Disk usage: {stats['disk_usage_after']:.1f}%")

        return stats
