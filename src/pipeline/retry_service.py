import logging
import os

from tqdm import tqdm

from src.data.db_manager import DBManager
from src.pipeline.file_processing_service import FileProcessingService

tqdm_logger = logging.getLogger("tqdm_logger")


class RetryService:
    def __init__(
        self,
        db_manager: DBManager,
        file_processing_service: FileProcessingService,
    ):
        self.db_manager = db_manager
        self.file_processing_service = file_processing_service

    def retry(self):
        tqdm_logger.info("Starting retry operation for failed files...")
        failed_files = self.db_manager.get_failed_files()

        if not failed_files:
            tqdm_logger.info("No failed files to retry.")
            return

        tqdm_logger.info(f"Found {len(failed_files)} failed files to retry.")

        repo_file_pbar = tqdm(
            total=len(failed_files),
            desc="Retrying failed files",
            unit="file",
            dynamic_ncols=True,
            position=0,
            leave=True,
        )

        for file_path, reason in failed_files:
            repo_name = os.path.basename(os.path.dirname(file_path))
            tqdm_logger.info(f"Retrying {file_path} (reason: {reason})")

            pbar = tqdm(
                total=1,
                desc=f"Retrying {os.path.basename(file_path)[:64]}...",
                position=1,
                leave=False,
                dynamic_ncols=True,
                unit="Q",
            )

            success, qa_count = self.file_processing_service.process_single_file(file_path, repo_name, pbar=pbar)

            if success:
                tqdm_logger.info(f"Successfully processed {file_path}. Removing from failed list.")
                self.db_manager.remove_failed_file(file_path)
            else:
                tqdm_logger.error(f"Failed to process {file_path} again.")

            repo_file_pbar.update(1)

        repo_file_pbar.close()
        tqdm_logger.info("Retry operation completed.")
        self.db_manager.close_db()
