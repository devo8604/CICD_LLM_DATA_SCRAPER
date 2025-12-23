"""Utility for scanning and managing files in repositories."""

import logging
import os
from pathlib import Path


class FileManager:
    """Handles discovery and filtering of files within repositories."""

    def __init__(self, repos_dir: str | Path, max_file_size: int, allowed_extensions: list[str] = None, allowed_json_md_files: list[str] = None):
        """
        Initialize FileManager.

        Args:
            repos_dir: Directory containing cloned repositories
            max_file_size: Maximum file size to process in bytes
            allowed_extensions: List of allowed file extensions
            allowed_json_md_files: List of specifically allowed JSON/MD filenames (e.g. README.md)
        """
        self.repos_dir = Path(repos_dir)
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions or [
            ".py",
            ".js",
            ".ts",
            ".go",
            ".rs",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".java",
            ".rb",
            ".php",
            ".sh",
            ".yaml",
            ".yml",
            ".sql",
            ".md",
        ]
        self.allowed_json_md_files = allowed_json_md_files or ["readme.md", "README.md", "readme.txt"]

    def get_all_files_in_repo(self, current_repo_path: str | Path) -> list[str]:
        """
        Scan a repository for processable files.

        Args:
            current_repo_path: Path to the repository to scan

        Returns:
            Sorted list of file paths ready for processing
        """
        all_files_in_repo = []
        skipped_count_in_repo = 0
        current_repo_path = Path(current_repo_path)

        # Directories to ignore
        IGNORED_DIRS = {"node_modules", "__pycache__", "venv", "env", ".git", ".idea", ".vscode", "dist", "build", "target", "vendor", "bin", "obj", "out"}

        try:
            for root, dirs, files in os.walk(current_repo_path):
                # Exclude dot directories and other ignored directories
                # Modify dirs in-place to prevent os.walk from recursing into them
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]

                for file in files:
                    if file.startswith("."):
                        skipped_count_in_repo += 1
                        continue

                    file_path = Path(root) / file

                    if not file_path.is_file():
                        skipped_count_in_repo += 1
                        continue

                    try:
                        if file_path.stat().st_size > self.max_file_size:
                            logging.debug(f"    Skipping large file (>{self.max_file_size / (1024 * 1024):.1f}MB): {file_path.name}")
                            skipped_count_in_repo += 1
                            continue
                    except OSError:
                        skipped_count_in_repo += 1
                        continue

                    # Check if file has an allowed extension
                    allowed = False
                    filename = file_path.name.lower()

                    # Check if it's a special allowed file (like README)
                    if filename in self.allowed_json_md_files:
                        allowed = True
                    else:
                        # Check if file has an allowed extension
                        for ext in self.allowed_extensions:
                            if filename.endswith(ext):
                                allowed = True
                                break

                    # For JSON and MD files specifically, only allow if they're explicitly in allowed_json_md_files
                    if filename.endswith((".json", ".md")):
                        if filename not in self.allowed_json_md_files:
                            allowed = False

                    if not allowed:
                        skipped_count_in_repo += 1
                        continue

                    all_files_in_repo.append(str(file_path))
        except Exception as e:
            logging.error(f"Error scanning repository {current_repo_path}: {e}")

        logging.info(f"Finished scanning {current_repo_path}. Found {len(all_files_in_repo)} files for processing. {skipped_count_in_repo} files filtered out.")
        all_files_in_repo.sort()
        return all_files_in_repo

    def cleanup_temporary_artifacts(self) -> int:
        """
        Cleanup empty directories and other artifacts.

        Returns:
            Number of items removed.
        """
        removed_count = 0
        if not self.repos_dir.exists():
            return 0

        # Walk bottom-up to remove leaf directories first
        for root, dirs, files in os.walk(self.repos_dir, topdown=False):
            for d in dirs:
                dir_path = Path(root) / d
                try:
                    # Only remove if it's a directory and empty
                    if dir_path.is_dir() and not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        removed_count += 1
                        logging.debug(f"Removed empty directory: {dir_path}")
                except OSError as e:
                    logging.warning(f"Failed to remove directory {dir_path}: {e}")

        return removed_count
