import os
import logging

from src.config import AppConfig

# Initialize config instance
config = AppConfig()


class FileManager:
    def __init__(self, repos_dir: str, max_file_size: int):
        self.repos_dir = repos_dir
        self.max_file_size = max_file_size

    def get_all_files_in_repo(self, current_repo_path):
        all_files_in_repo = []
        skipped_count_in_repo = 0

        try:
            for root, dirs, files in os.walk(current_repo_path):
                # Exclude dot directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if file.startswith("."):
                        skipped_count_in_repo += 1
                        continue

                    file_path = os.path.join(root, file)

                    if not os.path.isfile(file_path):
                        skipped_count_in_repo += 1
                        continue

                    if os.path.getsize(file_path) > self.max_file_size:
                        logging.info(
                            f"    Skipping large file (>{self.max_file_size / (1024*1024):.1f}MB): {os.path.basename(file_path)}"
                        )
                        skipped_count_in_repo += 1
                        continue

                    if any(
                        file_path.endswith(ext) for ext in config.EXCLUDED_FILE_EXTENSIONS
                    ):
                        skipped_count_in_repo += 1
                        continue
                    all_files_in_repo.append(file_path)
        finally:
            pass  # No spinner to clean up

        logging.info(
            f"  Repo '{os.path.basename(current_repo_path)}': {len(all_files_in_repo)} files found for processing. {skipped_count_in_repo} files filtered out."
        )
        all_files_in_repo.sort()
        return all_files_in_repo
