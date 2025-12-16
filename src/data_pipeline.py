import os
import sys
import logging
import json
import hashlib
import time  # Import time for sleep in pause_on_low_battery
import asyncio
from urllib.parse import urlparse

from tqdm import tqdm

from src.llm_client import LLMClient
from src.utils import (
    check_battery_status,
    pause_on_low_battery,  # Now imported from utils
    get_repo_urls_from_file,
    get_repos_from_github_page,
    clone_or_update_repos,
)
from src.db_manager import DBManager
from src.file_manager import FileManager
from src.config import AppConfig

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class DataPipeline:
    def __init__(
        self,
        llm_client,  # Injected dependency
        db_manager,  # Injected dependency
        file_manager,  # Injected dependency
        base_dir=".",
        max_tokens=500,
        temperature=0.7,
        data_dir="data",
    ):
        self.base_dir = base_dir
        self.repos_dir = os.path.join(self.base_dir, "repos")
        self.data_dir = os.path.join(self.base_dir, data_dir)
        self.llm_client = llm_client  # Use injected instance
        self.db_manager = db_manager  # Use injected instance
        self.file_manager = file_manager  # Use injected instance
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.config = AppConfig()  # Config instance for accessing settings

        self.state = self._load_state()

        os.makedirs(self.repos_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def _load_state(self):
        state = self.db_manager.get_state()
        return {
            "current_repo_name": state.get("current_repo_name"),
            "processed_repos_count": state.get("processed_repos_count", 0),
            "current_file_path_in_repo": state.get("current_file_path_in_repo"),
            "processed_files_count_in_repo": state.get(
                "processed_files_count_in_repo", 0
            ),
        }

    def _save_state(self):
        self.db_manager.save_state(self.state)

    def _calculate_file_hash(self, file_path: str) -> str | None:
        """Calculates the SHA256 hash of a file's content."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read the file in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
        except Exception as e:
            tqdm_logger.error(f"Error calculating hash for {file_path}: {e}")
            return None  # Return None if hash calculation fails
        return hasher.hexdigest()

    async def _process_single_file(
        self,
        file_path: str,
        repo_name: str,
        pbar: tqdm | None = None
    ) -> tuple[bool, int]:
        """
        Process a single file: check hash, generate Q&A, save to DB.

        Returns:
            tuple: (success: bool, qa_pairs_generated: int)
        """
        file_name = os.path.basename(file_path)
        if pbar is not None:
            pbar.set_description(f"File: {file_name[:64]:<64} | Hashing")

        # Skip if not a regular file (e.g., a FIFO or socket)
        if not os.path.isfile(file_path):
            tqdm_logger.warning(
                f"Skipping non-regular file: {file_name} in repo '{repo_name}'"
            )
            if pbar is not None:
                pbar.update(100)
                pbar.close()
            return (True, 0)

        # Calculate current hash and check against stored hash
        current_file_hash = self._calculate_file_hash(file_path)
        if current_file_hash is None:
            tqdm_logger.error(f"Could not calculate hash for {file_path}. Skipping.")
            if pbar is not None:
                pbar.close()
            return (False, 0)

        stored_file_hash = self.db_manager.get_file_hash(file_path)

        if stored_file_hash == current_file_hash:
            if pbar is not None:
                pbar.set_description(f"File: {file_name[:64]:<64} | Unchanged")
                pbar.update(100)
                pbar.close()
            else: # Fallback for when no pbar is passed
                tqdm_logger.info(f"File {file_name} is unchanged. Skipping processing.")
            return (True, 0)
        elif stored_file_hash is not None:
            tqdm_logger.info(f"File {file_name} has been updated. Reprocessing.")

        file_processed_successfully = True
        current_file_qa_entries = []

        try:
            if pbar is not None: pbar.set_description(f"File: {file_name[:64]:<64} | Reading")
            def read_file_content():
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()

            try:
                content = await asyncio.wait_for(
                    asyncio.to_thread(read_file_content), timeout=60.0
                )
            except asyncio.TimeoutError:
                tqdm_logger.warning(f"Timeout reading file: {file_name}. Skipping.")
                if pbar is not None: pbar.close()
                self.db_manager.add_failed_file(file_path, "Timeout reading file")
                return (False, 0)

            if not content.strip():
                tqdm_logger.info(f"Skipping empty file: {file_name}")
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Empty")
                    pbar.update(100)
                    pbar.close()
                return (True, 0)

            if pbar is not None: pbar.set_description(f"File: {file_name[:64]:<64} | Gen Qs")
            all_questions_for_file = await self.llm_client.generate_questions(
                content, self.temperature, self.max_tokens, pbar
            )

            if all_questions_for_file is None:
                tqdm_logger.error(f"LLM failed to generate questions for {file_name}.")
                if pbar is not None: pbar.close()
                self.db_manager.add_failed_file(file_path, "LLM failed to generate questions")
                return (False, 0)

            self.llm_client.clear_context()
            processed_hashes = self.db_manager.get_processed_question_hashes(file_path)
            unanswered_questions = [
                q for q in all_questions_for_file
                if hashlib.sha256(q.encode("utf-8")).hexdigest() not in processed_hashes
            ]
            tqdm_logger.debug(f"Found {len(unanswered_questions)} new questions for {file_name}.")
            
            if pbar is not None:
                pbar.total = len(unanswered_questions)
                pbar.refresh()

            for i, question in enumerate(unanswered_questions):
                if pbar is not None: pbar.set_description(f"File: {file_name[:64]:<64} | Ans Q {i+1}/{len(unanswered_questions)}")
                answer = await self.llm_client.get_answer_single(
                    question, content, self.temperature, self.max_tokens, pbar
                )

                if answer is None:
                    tqdm_logger.error(f"LLM failed to generate answer in {file_name}.")
                    file_processed_successfully = False
                    self.db_manager.add_failed_file(file_path, "LLM failed to generate answer")
                    continue
                current_file_qa_entries.append({"question": question, "answer": answer})
                if pbar is not None:
                    pbar.update(1)

            if file_processed_successfully and current_file_qa_entries:
                if pbar is not None: pbar.set_description(f"File: {file_name[:64]:<64} | Saving")
                for entry in current_file_qa_entries:
                    self.db_manager.add_qa_sample(file_path, entry["question"], entry["answer"])
                self.db_manager.save_file_hash(file_path, current_file_hash)
                self.db_manager.remove_failed_file(file_path) # Remove from failed list on success
                if pbar is not None: pbar.set_description(f"File: {file_name[:64]:<64} | Done")
                return (True, len(current_file_qa_entries))
            else: # No new entries or processing failed
                if pbar is not None: pbar.set_description(f"File: {file_name[:64]:<64} | No new Qs")
                return (True, 0)

        except Exception as e:
            tqdm_logger.error(f"Error processing {file_name}: {e}", exc_info=True)
            self.db_manager.add_failed_file(file_path, str(e))
            return (False, 0)
        finally:
            if pbar is not None:
                pbar.close()

    async def _process_files_batch(
        self,
        files: list[str],
        repo_name: str,
        semaphore: asyncio.Semaphore,
        batch_num: int,
        total_batches: int,
        repo_file_pbar: tqdm | None = None,
    ) -> list[tuple[str, bool, int]]:
        results = []
        tasks = []

        async def process_with_semaphore(file_path: str, pbar_position: int):
            async with semaphore:
                pause_on_low_battery()
                # Create a temporary pbar for the individual file's Q/A progress
                pbar = tqdm(total=1, desc=f"Starting {os.path.basename(file_path)[:64]}...", position=pbar_position, leave=False, dynamic_ncols=True, unit="Q")
                success, qa_count = await self._process_single_file(file_path, repo_name, pbar=pbar)
                
                # Update the main file progress bar for the repo
                if repo_file_pbar:
                    repo_file_pbar.update(1)

                # Log results after processing
                if success:
                    if qa_count > 0:
                        tqdm_logger.debug(f"    ✓ Processed {os.path.basename(file_path)}: {qa_count} Q&A pairs")
                    else:
                         tqdm_logger.debug(f"    - Skipped {os.path.basename(file_path)} (unchanged or no new Qs)")
                else:
                    tqdm_logger.warning(f"    ✗ Failed to process {os.path.basename(file_path)}")

                return (file_path, success, qa_count)

        async with asyncio.TaskGroup() as tg:
            for i, file_path in enumerate(files):
                # The position for the file-specific progress bar, cycling through available slots
                pbar_pos = (i % self.config.MAX_CONCURRENT_FILES) + 2
                task = tg.create_task(process_with_semaphore(file_path, pbar_pos))
                tasks.append(task)
            
            for task in tasks:
                try:
                    result = await task
                    results.append(result)
                except Exception as e:
                    # This part might be redundant if errors are caught inside process_with_semaphore
                    # but it's good for catching unexpected task-level failures.
                    tqdm_logger.error(f"A task in the batch failed unexpectedly: {e}", exc_info=True)

        return results

    async def scrape(self):
        root_logger = logging.getLogger()
        root_logger.info("Starting scrape operation: Cloning or updating repositories...")
        initial_urls = get_repo_urls_from_file()
        all_repos_to_clone = []

        for url in initial_urls:
            parsed_url = urlparse(url)

            if "github.com" in parsed_url.netloc:
                path_segments = [s for s in parsed_url.path.split("/") if s]

                if len(path_segments) == 1:
                    root_logger.info(f"Detected GitHub user/organization page: {url}")
                    discovered_repos = get_repos_from_github_page(url)
                    if discovered_repos:
                        root_logger.info(
                            f"Discovered {len(discovered_repos)} repositories from {url}"
                        )
                        all_repos_to_clone.extend(discovered_repos)
                    else:
                        root_logger.warning(
                            f"No repositories discovered from {url}. It might be empty or my scraping logic needs adjustment."
                        )
                elif len(path_segments) >= 2:
                    root_logger.info(
                        f"Detected direct GitHub repository or path within: {url}"
                    )
                    all_repos_to_clone.append(url)
                else:
                    root_logger.warning(
                        f"Unknown GitHub URL format: {url}. Treating as direct repo."
                    )
                    all_repos_to_clone.append(url)
            else:
                root_logger.info(
                    f"Detected non-GitHub URL: {url}. Treating as direct repo."
                )
                all_repos_to_clone.append(url)

        all_repos_to_clone = list(set(all_repos_to_clone))

        root_logger.info(f"Total unique repositories to process: {len(all_repos_to_clone)}")
        await clone_or_update_repos(self.repos_dir, all_repos_to_clone)
        
        # After cloning/updating, count the actual number of repositories
        repo_count = 0
        for root, dirs, files in os.walk(self.repos_dir):
            if ".git" in dirs:
                repo_count += 1
                dirs[:] = [] # Prune search
        
        # Save the count
        count_file_path = os.path.join(self.data_dir, "repo_count.txt")
        with open(count_file_path, "w") as f:
            f.write(str(repo_count))
            
        root_logger.info(f"Found {repo_count} total repositories. Count saved to {count_file_path}.")
        root_logger.info("Scrape operation completed.")

    async def prepare(self):
        tqdm_logger.info("Starting prepare operation: Processing files and generating Q&A...")

        # --- Cleanup ---
        tracked_files = self.db_manager.get_all_tracked_files()
        tqdm_logger.info(f"Checking {len(tracked_files)} previously tracked files for existence...")
        removed_files_count = 0
        for file_path in tracked_files:
            if not os.path.exists(file_path):
                tqdm_logger.info(f"File '{file_path}' no longer exists. Removing associated data.")
                self.db_manager.delete_samples_for_file(file_path)
                self.db_manager.delete_file_hash(file_path)
                removed_files_count += 1
        if removed_files_count > 0:
            tqdm_logger.info(f"Cleaned up data for {removed_files_count} removed files.")

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
        if self.state["current_repo_name"] and self.state["current_repo_name"] in all_repos:
            repo_start_index = all_repos.index(self.state["current_repo_name"])
            # The initial value of the progress bar will be this index.
            tqdm_logger.info(f"Resuming from repository {repo_start_index + 1}/{total_repos}: {os.path.basename(self.state['current_repo_name'])}")
        else:
            self.state["current_repo_name"] = None
            self.state["processed_repos_count"] = 0

        # --- Main Processing Loop ---
        repo_tqdm = tqdm(total=total_repos, initial=repo_start_index, desc="Total Repo Progress", unit="repo", dynamic_ncols=True, position=0, leave=True)
        repo_file_pbar = tqdm(total=0, desc="Files", unit="file", dynamic_ncols=True, position=1, leave=True)
        
        for repo_path in all_repos[repo_start_index:]:
            repo_name = os.path.basename(repo_path)
            repo_tqdm.set_description(f"Total Repo Progress (Current: {repo_name})")
            
            self.state["current_repo_name"] = repo_path
            self._save_state()

            all_files_in_repo = sorted(self.file_manager.get_all_files_in_repo(repo_path))
            total_files_in_repo = len(all_files_in_repo)
            
            file_start_index = 0
            if self.state.get("current_file_path_in_repo") and os.path.dirname(self.state["current_file_path_in_repo"]) == repo_path:
                try:
                    file_start_index = all_files_in_repo.index(self.state["current_file_path_in_repo"])
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
                        pause_on_low_battery()
                        pbar = tqdm(total=1, desc=f"Starting {os.path.basename(file_path)[:64]}...", position=2, leave=False, dynamic_ncols=True, unit="Q")
                        success, qa_count = await self._process_single_file(file_path, repo_name, pbar=pbar)
                        repo_file_pbar.update(1)
                        if success and qa_count > 0:
                            tqdm_logger.debug(f"    ✓ Processed {os.path.basename(file_path)}: {qa_count} Q&A pairs")
                        elif not success:
                            tqdm_logger.warning(f"    ✗ Failed to process {os.path.basename(file_path)}")
                else:
                    # Concurrent batch processing
                    total_batches = (len(files_to_process) + self.config.FILE_BATCH_SIZE - 1) // self.config.FILE_BATCH_SIZE
                    for i, batch_start in enumerate(range(0, len(files_to_process), self.config.FILE_BATCH_SIZE)):
                        batch_files = files_to_process[batch_start : batch_start + self.config.FILE_BATCH_SIZE]
                        
                        await self._process_files_batch(batch_files, repo_name, semaphore, i + 1, total_batches, repo_file_pbar=repo_file_pbar)
                        
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
            self.state["processed_files_count_in_repo"] = 0 # Reset for next repo
            self._save_state()

        repo_tqdm.close()
        repo_file_pbar.close()

        # Final state reset
        self.state = {"current_repo_name": None, "processed_repos_count": 0, "current_file_path_in_repo": None, "processed_files_count_in_repo": 0}
        self._save_state()
        
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

        repo_file_pbar = tqdm(total=len(failed_files), desc="Retrying failed files", unit="file", dynamic_ncols=True, position=0, leave=True)

        for file_path, reason in failed_files:
            repo_name = os.path.basename(os.path.dirname(file_path))
            tqdm_logger.info(f"Retrying {file_path} (reason: {reason})")
            
            pbar = tqdm(total=1, desc=f"Retrying {os.path.basename(file_path)[:64]}...", position=1, leave=False, dynamic_ncols=True, unit="Q")
            
            success, qa_count = await self._process_single_file(file_path, repo_name, pbar=pbar)
            
            if success:
                tqdm_logger.info(f"Successfully processed {file_path}. Removing from failed list.")
                self.db_manager.remove_failed_file(file_path)
            else:
                tqdm_logger.error(f"Failed to process {file_path} again.")
            
            repo_file_pbar.update(1)

        repo_file_pbar.close()
        tqdm_logger.info("Retry operation completed.")
        self.db_manager.close_db()

    def close(self):
        try:
            self.db_manager.close_db()
        except:
            pass  # Already closed or error, ignore
