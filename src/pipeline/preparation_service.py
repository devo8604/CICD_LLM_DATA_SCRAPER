"""Service layer for preparing repositories and files for Q&A generation."""

import os
from datetime import datetime

import structlog
from tqdm import tqdm

from src.core.config import AppConfig
from src.core.utils import pause_on_low_battery
from src.data.db_manager import DBManager
from src.data.file_manager import FileManager
from src.pipeline.batch_processing_service import BatchProcessingService
from src.pipeline.file_processing_service import FileProcessingService
from src.pipeline.state_management_service import StateManagementService
from src.utils.disk_cleanup import DiskCleanupManager

try:
    from src.ui.progress_tracker import get_progress_tracker
except ImportError:
    get_progress_tracker = None

logger = structlog.get_logger(__name__)


class PreparationService:
    def __init__(
        self,
        db_manager: DBManager,
        file_manager: FileManager,
        file_processing_service: FileProcessingService,
        batch_processing_service: BatchProcessingService,
        state_management_service: StateManagementService,
        config: AppConfig,
    ):
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.file_processing_service = file_processing_service
        self.batch_processing_service = batch_processing_service
        self.state_service = state_management_service
        self.config = config
        self.repos_dir = os.path.join(self.config.model.base_dir, "repos")
        self.progress_tracker = get_progress_tracker() if get_progress_tracker else None
        self.last_cleanup_time = datetime.now()
        self.cleanup_manager = DiskCleanupManager(config)

    def prepare(self, processing_started_callback=None, cancellation_event=None):
        logger.info("Starting prepare operation")
        if self.progress_tracker:
            self.progress_tracker.start()

        try:
            self._cleanup_tracked_files()
            all_repos, total_files, all_repos_files = self._discover_repositories_and_files()

            if self.progress_tracker:
                self.progress_tracker.update_total_repos(len(all_repos))
                self.progress_tracker.update_total_files(total_files)

            repo_start_index = self._get_repo_start_index(all_repos)

            if processing_started_callback:
                processing_started_callback()

            self._process_repositories(all_repos, all_repos_files, repo_start_index, cancellation_event)

            self.state_service.reset_state()
            logger.info("Prepare operation completed")
        finally:
            self.db_manager.close_db()

            # Unload LLM model if supported to free up memory
            if hasattr(self.file_processing_service.llm_client, "unload_model"):
                try:
                    self.file_processing_service.llm_client.unload_model()
                except Exception as e:
                    logger.warning("Failed to unload model", error=str(e))

    def _cleanup_tracked_files(self):
        tracked_files = self.db_manager.get_all_tracked_files()
        logger.info("Checking tracked files for existence", count=len(tracked_files))
        removed_files_count = 0
        for file_path in tracked_files:
            if not os.path.exists(file_path):
                logger.debug("File no longer exists, removing data", file_path=file_path)
                self.db_manager.delete_samples_for_file(file_path)
                self.db_manager.delete_file_hash(file_path)
                removed_files_count += 1
        if removed_files_count > 0:
            logger.info("Cleaned up data for removed files", count=removed_files_count)

    def _discover_repositories_and_files(self):
        all_repos = []
        for root, dirs, files in os.walk(self.repos_dir):
            if ".git" in dirs:
                all_repos.append(root)
                dirs[:] = []
        all_repos.sort()

        total_files = 0
        all_repos_files = {}
        for repo_path in all_repos:
            files_in_repo = sorted(self.file_manager.get_all_files_in_repo(repo_path))
            all_repos_files[repo_path] = files_in_repo
            total_files += len(files_in_repo)

        return all_repos, total_files, all_repos_files

    def _get_repo_start_index(self, all_repos):
        repo_start_index = 0
        current_repo = self.state_service.state["current_repo_name"]
        if current_repo and current_repo in all_repos:
            repo_start_index = all_repos.index(current_repo)
            logger.info("Resuming preparation", repo=os.path.basename(current_repo), index=repo_start_index+1, total=len(all_repos))
        else:
            self.state_service.state["current_repo_name"] = None
            self.state_service.state["processed_repos_count"] = 0
        return repo_start_index

    def _process_repositories(self, all_repos, all_repos_files, repo_start_index, cancellation_event=None):
        repo_tqdm = tqdm(
            total=len(all_repos),
            initial=repo_start_index,
            desc="Total Repo Progress",
            unit="repo",
            position=0,
            leave=True,
        )
        repo_file_pbar = tqdm(
            total=0,
            desc="Files",
            unit="file",
            position=1,
            leave=True,
        )

        for repo_path in all_repos[repo_start_index:]:
            if cancellation_event and cancellation_event.is_set():
                logger.info("Prepare operation cancelled")
                break

            self._process_single_repository(
                repo_path,
                all_repos,
                all_repos_files,
                repo_tqdm,
                repo_file_pbar,
                cancellation_event,
            )

        repo_tqdm.close()
        repo_file_pbar.close()

    def _process_single_repository(
        self,
        repo_path,
        all_repos,
        all_repos_files,
        repo_tqdm,
        repo_file_pbar,
        cancellation_event=None,
    ):
        repo_name = os.path.basename(repo_path)
        repo_tqdm.set_description(f"Total Repo Progress (Current: {repo_name})")

        self.state_service.state["current_repo_name"] = repo_path
        self.state_service.save_state()

        files_in_repo = all_repos_files[repo_path]
        total_files_in_repo = len(files_in_repo)

        file_start_index = self._get_file_start_index(files_in_repo)

        if self.progress_tracker:
            current_repo_index = all_repos.index(repo_path)
            self.progress_tracker.update_current_repo(current_repo_index, repo_name, total_files_in_repo)
            self.progress_tracker.current_repo_files_processed = file_start_index

        repo_file_pbar.reset(total=total_files_in_repo)
        repo_file_pbar.set_description(f"Files in {repo_name}")
        repo_file_pbar.update(file_start_index)

        files_to_process = files_in_repo[file_start_index:]

        if self.config.model.processing.max_concurrent_files == 1:
            self._process_files_sequentially(files_to_process, repo_name, repo_file_pbar, cancellation_event)
        else:
            self._process_files_concurrently(files_to_process, repo_name, repo_file_pbar, cancellation_event)

        repo_tqdm.update(1)

        if self.progress_tracker:
            if self.progress_tracker.current_repo_index < len(all_repos) - 1:
                self.progress_tracker.current_repo_files_processed = 0
                self.progress_tracker.current_file_path = ""

        self.state_service.state["processed_repos_count"] = repo_tqdm.n
        self.state_service.state["current_file_path_in_repo"] = None
        self.state_service.state["processed_files_count_in_repo"] = 0
        self.state_service.save_state()

    def _get_file_start_index(self, files_in_repo):
        file_start_index = 0
        current_file = self.state_service.state.get("current_file_path_in_repo")
        if current_file and files_in_repo and os.path.dirname(current_file) == os.path.dirname(files_in_repo[0]):
            try:
                file_start_index = files_in_repo.index(current_file)
            except ValueError:
                file_start_index = 0
        return file_start_index

    def _run_periodic_cleanup(self):
        """Run cleanup if enough time has passed or disk usage is high."""
        current_time = datetime.now()
        time_since_cleanup = (current_time - self.last_cleanup_time).total_seconds()

        # Cleanup every 30 minutes or if disk usage is high
        if time_since_cleanup > 1800:  # 30 minutes
            stats = self.cleanup_manager.cleanup_if_needed(threshold_percent=70.0)
            self.last_cleanup_time = current_time
            if stats.get("log_files_removed", 0) > 0 or stats.get("temp_files_removed", 0) > 0:
                logger.info(f"Periodic cleanup completed: {stats}")

    def _process_files_sequentially(self, files_to_process, repo_name, repo_file_pbar, cancellation_event=None):
        for idx, file_path in enumerate(files_to_process):
            if cancellation_event and cancellation_event.is_set():
                logger.info("File processing cancelled")
                break

            # Run periodic cleanup every 100 files to avoid too frequent checks
            if idx % 100 == 0:
                self._run_periodic_cleanup()

            if self.progress_tracker:
                self.progress_tracker.current_file_path = file_path

            pause_on_low_battery(self.config)
            pbar = tqdm(
                total=1,
                desc=f"Starting {os.path.basename(file_path)[:64]}...",
                position=2,
                leave=False,
                dynamic_ncols=True,
                unit="Q",
            )
            success, qa_count = self.file_processing_service.process_single_file(
                file_path, repo_name, pbar=pbar, cancellation_event=cancellation_event
            )
            repo_file_pbar.update(1)

            if self.progress_tracker:
                self.progress_tracker.increment_repo_files_processed()

            if success and qa_count > 0:
                logger.debug("Processed file", file=os.path.basename(file_path), count=qa_count)
            elif not success:
                logger.warning("Failed to process file", file=os.path.basename(file_path))

    def _process_files_concurrently(self, files_to_process, repo_name, repo_file_pbar, cancellation_event=None):
        total_batches = (len(files_to_process) + self.config.model.processing.file_batch_size - 1) // self.config.model.processing.file_batch_size
        for i, batch_start in enumerate(range(0, len(files_to_process), self.config.model.processing.file_batch_size)):
            if cancellation_event and cancellation_event.is_set():
                logger.info("Concurrent processing cancelled")
                break

            # Run periodic cleanup every 5 batches to avoid too frequent checks
            if i % 5 == 0:
                self._run_periodic_cleanup()

            batch_files = files_to_process[batch_start : batch_start + self.config.model.processing.file_batch_size]

            if self.progress_tracker and batch_files:
                self.progress_tracker.current_file_path = batch_files[0]

            self.batch_processing_service.process_files_batch(
                batch_files,
                repo_name,
                i + 1,
                total_batches,
                repo_file_pbar=repo_file_pbar,
                cancellation_event=cancellation_event,
            )

            if self.progress_tracker:
                for _ in batch_files:
                    self.progress_tracker.increment_repo_files_processed()

            self.state_service.state["current_file_path_in_repo"] = batch_files[-1]
            self.state_service.save_state()