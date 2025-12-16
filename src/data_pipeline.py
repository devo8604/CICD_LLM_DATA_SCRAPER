import os
import sys
import logging
import asyncio
from typing import Optional

from tqdm import tqdm

from src.llm_client import LLMClient
from src.db_manager import DBManager
from src.file_manager import FileManager
from src.config import AppConfig
from src.services.file_processing_service import FileProcessingService
from src.services.repository_service import RepositoryService
from src.services.state_management_service import StateManagementService
from src.services.batch_processing_service import BatchProcessingService

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class DataPipeline:
    def __init__(
        self,
        db_manager: DBManager,
        file_manager: FileManager,
        llm_client: Optional[LLMClient] = None,
        base_dir: str = ".",
        max_tokens: int = 500,
        temperature: float = 0.7,
        data_dir: str = "data",
        config: Optional[AppConfig] = None,
    ):
        self.base_dir = base_dir
        self.repos_dir = os.path.join(self.base_dir, "repos")
        self.data_dir = os.path.join(self.base_dir, data_dir)
        self._llm_client = llm_client  # Store as private, lazy init
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.config = config or AppConfig()

        # Initialize services that don't require LLM
        # FileProcessingService will be initialized lazily when llm_client is accessed
        self._file_processing_service = None
        self._batch_processing_service = None
        self.repository_service = RepositoryService(config=self.config)
        self.state_service = StateManagementService(
            db_manager=self.db_manager, config=self.config
        )

        os.makedirs(self.repos_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    @property
    def llm_client(self) -> LLMClient:
        """Lazy initialization of LLM client."""
        if self._llm_client is None:
            # Import here to avoid circular dependency and only when needed
            from src.pipeline_factory import PipelineFactory

            factory = PipelineFactory(self.config)
            self._llm_client = factory.create_llm_client()
        return self._llm_client

    @property
    def file_processing_service(self) -> FileProcessingService:
        """Lazy initialization of file processing service."""
        if self._file_processing_service is None:
            self._file_processing_service = FileProcessingService(
                llm_client=self.llm_client,
                db_manager=self.db_manager,
                config=self.config,
            )
        return self._file_processing_service

    @property
    def batch_processing_service(self) -> BatchProcessingService:
        """Lazy initialization of batch processing service."""
        if self._batch_processing_service is None:
            self._batch_processing_service = BatchProcessingService(
                file_processing_service=self.file_processing_service,
                db_manager=self.db_manager,
                config=self.config,
            )
        return self._batch_processing_service

    @property
    def state(self):
        """Access to state from the state service."""
        return self.state_service.state

    def _save_state(self):
        """Save the current state."""
        self.state_service.save_state()

    async def scrape(self):
        """Scrape repositories based on repos.txt file."""
        await self.repository_service.scrape_repositories(self.repos_dir)

    async def prepare(self):
        tqdm_logger.info(
            "Starting prepare operation: Processing files and generating Q&A..."
        )

        # --- Cleanup ---
        tracked_files = self.db_manager.get_all_tracked_files()
        tqdm_logger.info(
            f"Checking {len(tracked_files)} previously tracked files for existence..."
        )
        removed_files_count = 0
        for file_path in tracked_files:
            if not os.path.exists(file_path):
                tqdm_logger.info(
                    f"File '{file_path}' no longer exists. Removing associated data."
                )
                self.db_manager.delete_samples_for_file(file_path)
                self.db_manager.delete_file_hash(file_path)
                removed_files_count += 1
        if removed_files_count > 0:
            tqdm_logger.info(
                f"Cleaned up data for {removed_files_count} removed files."
            )

        # --- Discover Repos and Set Total for Progress Bar ---
        all_repos = []
        for root, dirs, files in os.walk(self.repos_dir):
            if ".git" in dirs:
                all_repos.append(root)
                dirs[:] = []  # Prune search to avoid descending into .git or sub-repos
        all_repos.sort()
        total_repos = len(all_repos)

        # --- Resume Logic ---
        repo_start_index = 0
        if (
            self.state["current_repo_name"]
            and self.state["current_repo_name"] in all_repos
        ):
            repo_start_index = all_repos.index(self.state["current_repo_name"])
            # The initial value of the progress bar will be this index.
            tqdm_logger.info(
                f"Resuming from repository {repo_start_index + 1}/{total_repos}: {os.path.basename(self.state['current_repo_name'])}"
            )
        else:
            self.state["current_repo_name"] = None
            self.state["processed_repos_count"] = 0

        # --- Main Processing Loop ---
        repo_tqdm = tqdm(
            total=total_repos,
            initial=repo_start_index,
            desc="Total Repo Progress",
            unit="repo",
            dynamic_ncols=True,
            position=0,
            leave=True,
        )
        repo_file_pbar = tqdm(
            total=0,
            desc="Files",
            unit="file",
            dynamic_ncols=True,
            position=1,
            leave=True,
        )

        for repo_path in all_repos[repo_start_index:]:
            repo_name = os.path.basename(repo_path)
            repo_tqdm.set_description(f"Total Repo Progress (Current: {repo_name})")

            self.state["current_repo_name"] = repo_path
            self._save_state()

            all_files_in_repo = sorted(
                self.file_manager.get_all_files_in_repo(repo_path)
            )
            total_files_in_repo = len(all_files_in_repo)

            file_start_index = 0
            if (
                self.state.get("current_file_path_in_repo")
                and os.path.dirname(self.state["current_file_path_in_repo"])
                == repo_path
            ):
                try:
                    file_start_index = all_files_in_repo.index(
                        self.state["current_file_path_in_repo"]
                    )
                except ValueError:
                    file_start_index = 0

            # Reset and configure the file progress bar for the current repo
            repo_file_pbar.reset(total=total_files_in_repo)
            repo_file_pbar.set_description(f"Files in {repo_name}")
            repo_file_pbar.update(file_start_index)

            semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_FILES)

            try:
                files_to_process = all_files_in_repo[file_start_index:]

                if self.config.MAX_CONCURRENT_FILES == 1:
                    # Sequential processing
                    for file_path in files_to_process:
                        from src.utils import (
                            pause_on_low_battery,
                        )  # Import here to avoid circular import

                        pause_on_low_battery()
                        pbar = tqdm(
                            total=1,
                            desc=f"Starting {os.path.basename(file_path)[:64]}...",
                            position=2,
                            leave=False,
                            dynamic_ncols=True,
                            unit="Q",
                        )
                        success, qa_count = (
                            await self.file_processing_service.process_single_file(
                                file_path, repo_name, pbar=pbar
                            )
                        )
                        repo_file_pbar.update(1)
                        if success and qa_count > 0:
                            tqdm_logger.debug(
                                f"    ✓ Processed {os.path.basename(file_path)}: {qa_count} Q&A pairs"
                            )
                        elif not success:
                            tqdm_logger.warning(
                                f"    ✗ Failed to process {os.path.basename(file_path)}"
                            )
                else:
                    # Concurrent batch processing
                    total_batches = (
                        len(files_to_process) + self.config.FILE_BATCH_SIZE - 1
                    ) // self.config.FILE_BATCH_SIZE
                    for i, batch_start in enumerate(
                        range(0, len(files_to_process), self.config.FILE_BATCH_SIZE)
                    ):
                        batch_files = files_to_process[
                            batch_start : batch_start + self.config.FILE_BATCH_SIZE
                        ]

                        await self.batch_processing_service.process_files_batch(
                            batch_files,
                            repo_name,
                            semaphore,
                            i + 1,
                            total_batches,
                            repo_file_pbar=repo_file_pbar,
                        )

                        # Update state after each batch
                        self.state["current_file_path_in_repo"] = batch_files[-1]
                        self._save_state()

            except KeyboardInterrupt:
                self._save_state()
                self.db_manager.close_db()
                raise

            repo_tqdm.update(1)
            self.state["processed_repos_count"] = repo_tqdm.n
            self.state["current_file_path_in_repo"] = None
            self.state["processed_files_count_in_repo"] = 0  # Reset for next repo
            self._save_state()

        repo_tqdm.close()
        repo_file_pbar.close()

        # Final state reset
        self.state_service.reset_state()

        tqdm_logger.info("Prepare operation completed.")
        self.db_manager.close_db()

    async def retry_failed_files(self):
        """
        Retry processing files that previously failed.
        """
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

            success, qa_count = await self.file_processing_service.process_single_file(
                file_path, repo_name, pbar=pbar
            )

            if success:
                tqdm_logger.info(
                    f"Successfully processed {file_path}. Removing from failed list."
                )
                self.db_manager.remove_failed_file(file_path)
            else:
                tqdm_logger.error(f"Failed to process {file_path} again.")

            repo_file_pbar.update(1)

        repo_file_pbar.close()
        tqdm_logger.info("Retry operation completed.")
        self.db_manager.close_db()

    def export_data(self, template_name: str, output_file: str):
        """
        Export data using a specified template.
        Args:
            template_name: The name of the template to use for formatting.
            output_file: The path to the output file.
        """
        tqdm_logger.info(
            f"Starting data export with template '{template_name}' to '{output_file}'..."
        )
        from src.exporters import DataExporter  # Import here to avoid circular imports

        exporter = DataExporter(self.db_manager.db_path)
        try:
            exporter.export_data(template_name, output_file)
        except Exception as e:
            tqdm_logger.error(
                f"An error occurred during data export: {e}", exc_info=True
            )
        finally:
            exporter.close()

    def close(self):
        try:
            self.db_manager.close_db()
        except:
            pass  # Already closed or error, ignore
