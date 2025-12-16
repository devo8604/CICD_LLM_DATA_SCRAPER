"""Service layer for batch processing of files."""

import asyncio
import logging
import os
from typing import List, Tuple

import tqdm.asyncio
from tqdm import tqdm

from src.config import AppConfig
from src.db_manager import DBManager
from src.services.file_processing_service import FileProcessingService
from src.utils import pause_on_low_battery

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class BatchProcessingService:
    """Handles concurrent batch processing of files."""

    def __init__(
        self,
        file_processing_service: FileProcessingService,
        db_manager: DBManager,
        config: AppConfig,
    ):
        self.file_processing_service = file_processing_service
        self.db_manager = db_manager
        self.config = config

    async def process_files_batch(
        self,
        files: List[str],
        repo_name: str,
        semaphore: asyncio.Semaphore,
        batch_num: int,
        total_batches: int,
        repo_file_pbar: tqdm | None = None,
    ) -> List[Tuple[str, bool, int]]:
        """Process a batch of files concurrently with specified semaphore."""
        results = []
        tasks = []

        async def process_with_semaphore(file_path: str, pbar_position: int):
            async with semaphore:
                pause_on_low_battery()
                # Create a temporary pbar for the individual file's Q/A progress
                pbar = tqdm(
                    total=1,
                    desc=f"Starting {os.path.basename(file_path)[:64]}...",
                    position=pbar_position,
                    leave=False,
                    dynamic_ncols=True,
                    unit="Q",
                )
                success, qa_count = (
                    await self.file_processing_service.process_single_file(
                        file_path, repo_name, pbar=pbar
                    )
                )

                # Update the main file progress bar for the repo
                if repo_file_pbar:
                    repo_file_pbar.update(1)

                # Log results after processing
                if success:
                    if qa_count > 0:
                        tqdm_logger.debug(
                            f"    ✓ Processed {os.path.basename(file_path)}: {qa_count} Q&A pairs"
                        )
                    else:
                        tqdm_logger.debug(
                            f"    - Skipped {os.path.basename(file_path)} (unchanged or no new Qs)"
                        )
                else:
                    tqdm_logger.warning(
                        f"    ✗ Failed to process {os.path.basename(file_path)}"
                    )

                return (file_path, success, qa_count)

        # Create tasks for concurrent processing with proper exception handling
        # MLX operations are now thread-safe using locks, so concurrent processing is safe
        for i, file_path in enumerate(files):
            # The position for the file-specific progress bar, cycling through available slots
            pbar_pos = (i % self.config.MAX_CONCURRENT_FILES) + 2
            task = asyncio.create_task(process_with_semaphore(file_path, pbar_pos))
            tasks.append(task)

        # Wait for all tasks to complete, handling exceptions individually
        for i, task in enumerate(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                # Log the error and add a failure result for this file
                tqdm_logger.error(
                    f"A task in the batch failed unexpectedly: {e}", exc_info=True
                )
                # Add a failure result matching the expected format (file_path, success, qa_count)
                file_path = files[i] if i < len(files) else "unknown_file"
                results.append((file_path, False, 0))

        return results
