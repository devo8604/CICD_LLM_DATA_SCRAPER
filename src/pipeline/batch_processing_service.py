"""Service layer for batch processing of files."""

import os

import structlog
from tqdm import tqdm

from src.core.config import AppConfig
from src.core.utils import pause_on_low_battery
from src.data.db_manager import DBManager
from src.pipeline.file_processing_service import FileProcessingService

logger = structlog.get_logger(__name__)


class BatchProcessingService:
    """Handles sequential batch processing of files."""

    def __init__(
        self,
        file_processing_service: FileProcessingService,
        db_manager: DBManager,
        config: AppConfig,
    ):
        self.file_processing_service = file_processing_service
        self.db_manager = db_manager
        self.config = config

    def process_files_batch(
        self,
        files: list[str],
        repo_name: str,
        batch_num: int,
        total_batches: int,
        repo_file_pbar: tqdm | None = None,
        cancellation_event=None,
    ) -> list[tuple[str, bool, int]]:
        """Process a batch of files sequentially."""
        results = []

        logger.info("Processing batch", batch_num=batch_num, total_batches=total_batches, file_count=len(files))

        # Process files sequentially (single-threaded)
        for i, file_path in enumerate(files):
            # Check for cancellation
            if cancellation_event and cancellation_event.is_set():
                logger.info("Batch processing cancelled")
                break

            try:
                pause_on_low_battery(self.config)
                # Create a temporary pbar for the individual file's Q/A progress
                pbar = tqdm(
                    total=1,
                    desc=f"Starting {os.path.basename(file_path)[:64]}...",
                    position=2,  # Fixed position for sequential processing
                    leave=False,
                    dynamic_ncols=True,
                    unit="Q",
                )
                success, qa_count = self.file_processing_service.process_single_file(
                    file_path, repo_name, pbar=pbar, cancellation_event=cancellation_event
                )

                # Update the main file progress bar for the repo
                if repo_file_pbar:
                    repo_file_pbar.update(1)

                # Log results after processing
                if success:
                    if qa_count > 0:
                        logger.debug("Processed file", file=os.path.basename(file_path), count=qa_count)
                    else:
                        logger.debug("Skipped file", file=os.path.basename(file_path), reason="unchanged or no new Qs")
                else:
                    logger.warning("Failed to process file", file=os.path.basename(file_path))

                results.append((file_path, success, qa_count))

            except Exception as e:
                # Log the error and add a failure result for this file
                logger.error("Error processing file in batch", file=file_path, error=str(e), exc_info=True)
                results.append((file_path, False, 0))

        return results