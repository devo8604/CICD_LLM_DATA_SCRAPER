"""Service layer for batch processing of files."""

import concurrent.futures
import os

import structlog
from tqdm import tqdm

from src.core.config import AppConfig
from src.core.utils import pause_on_low_battery
from src.data.db_manager import DBManager
from src.pipeline.file_processing_service import FileProcessingService

logger = structlog.get_logger(__name__)


class BatchProcessingService:
    """Handles parallel batch processing of files."""

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
        """Process a batch of files in parallel."""
        results = []

        logger.info("Processing batch", batch_num=batch_num, total_batches=total_batches, file_count=len(files))

        # Determine number of workers from config
        max_workers = self.config.model.processing.max_concurrent_files if hasattr(self.config, "model") else 1

        # If MLX is being used, parallel processing might be limited by VRAM
        # but we can still use small concurrency if the model is small enough.
        # For now, we respect the config.

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Map files to processing tasks
            future_to_file = {}
            for file_path in files:
                if cancellation_event and cancellation_event.is_set():
                    break

                # Check battery before starting each file task
                pause_on_low_battery(self.config)

                future = executor.submit(
                    self.file_processing_service.process_single_file,
                    file_path,
                    repo_name,
                    pbar=None,  # Parallel tasks shouldn't share a pbar or use individual ones that mess up the console
                    cancellation_event=cancellation_event,
                )
                future_to_file[future] = file_path

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    success, qa_count = future.result()
                    results.append((file_path, success, qa_count))

                    # Update the main file progress bar
                    if repo_file_pbar:
                        repo_file_pbar.update(1)

                    if success:
                        if qa_count > 0:
                            logger.debug("Processed file", file=os.path.basename(file_path), count=qa_count)
                        else:
                            logger.debug("Skipped file", file=os.path.basename(file_path), reason="unchanged or no new Qs")
                    else:
                        logger.warning("Failed to process file", file=os.path.basename(file_path))

                except Exception as e:
                    logger.error("Error processing file in batch", file=file_path, error=str(e), exc_info=True)
                    results.append((file_path, False, 0))
                    if repo_file_pbar:
                        repo_file_pbar.update(1)

        return results
