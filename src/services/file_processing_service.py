"""Service layer for file processing operations."""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Tuple

import tqdm.asyncio
from tqdm import tqdm

from src.config import AppConfig
from src.db_manager import DBManager
from src.llm_client import LLMClient
from src.utils import pause_on_low_battery

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class FileProcessingService:
    """Handles processing of individual files to generate Q&A pairs."""

    def __init__(
        self,
        llm_client: LLMClient,
        db_manager: DBManager,
        config: AppConfig,
    ):
        self.llm_client = llm_client
        self.db_manager = db_manager
        self.config = config

    def calculate_file_hash(self, file_path: str) -> str | None:
        """Calculates the SHA256 hash of a file's content."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read the file in chunks to handle large files efficiently
                # Use chunk size from config for better performance tuning
                for chunk in iter(lambda: f.read(self.config.CHUNK_READ_SIZE), b""):
                    hasher.update(chunk)
        except Exception as e:
            tqdm_logger.error(f"Error calculating hash for {file_path}: {e}")
            return None  # Return None if hash calculation fails
        return hasher.hexdigest()

    async def process_single_file(
        self, file_path: str, repo_name: str, pbar: tqdm | None = None
    ) -> Tuple[bool, int]:
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
        current_file_hash = self.calculate_file_hash(file_path)
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
            else:  # Fallback for when no pbar is passed
                tqdm_logger.info(f"File {file_name} is unchanged. Skipping processing.")
            return (True, 0)
        elif stored_file_hash is not None:
            tqdm_logger.info(f"File {file_name} has been updated. Reprocessing.")

        file_processed_successfully = True
        current_file_qa_entries = []

        try:
            if pbar is not None:
                pbar.set_description(f"File: {file_name[:64]:<64} | Reading")

            def read_file_content():
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()

            try:
                content = await asyncio.wait_for(
                    asyncio.to_thread(read_file_content),
                    timeout=self.config.LLM_REQUEST_TIMEOUT,
                )
            except asyncio.TimeoutError:
                tqdm_logger.warning(f"Timeout reading file: {file_name}. Skipping.")
                if pbar is not None:
                    pbar.close()
                self.db_manager.add_failed_file(file_path, "Timeout reading file")
                return (False, 0)

            if not content.strip():
                tqdm_logger.info(f"Skipping empty file: {file_name}")
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Empty")
                    pbar.update(100)
                    pbar.close()
                return (True, 0)

            if pbar is not None:
                pbar.set_description(f"File: {file_name[:64]:<64} | Gen Qs")
            all_questions_for_file = await self.llm_client.generate_questions(
                content,
                self.config.DEFAULT_TEMPERATURE,
                self.config.DEFAULT_MAX_TOKENS,
                pbar,
            )

            if all_questions_for_file is None:
                tqdm_logger.error(f"LLM failed to generate questions for {file_name}.")
                if pbar is not None:
                    pbar.close()
                self.db_manager.add_failed_file(
                    file_path, "LLM failed to generate questions"
                )
                return (False, 0)

            self.llm_client.clear_context()
            processed_hashes = self.db_manager.get_processed_question_hashes(file_path)
            unanswered_questions = [
                q
                for q in all_questions_for_file
                if hashlib.sha256(q.encode("utf-8")).hexdigest() not in processed_hashes
            ]
            tqdm_logger.debug(
                f"Found {len(unanswered_questions)} new questions for {file_name}."
            )

            if pbar is not None:
                pbar.total = len(unanswered_questions)
                pbar.refresh()

            for i, question in enumerate(unanswered_questions):
                if pbar is not None:
                    pbar.set_description(
                        f"File: {file_name[:64]:<64} | Ans Q {i+1}/{len(unanswered_questions)}"
                    )
                answer = await self.llm_client.get_answer_single(
                    question,
                    content,
                    self.config.DEFAULT_TEMPERATURE,
                    self.config.DEFAULT_MAX_TOKENS,
                    pbar,
                )

                if answer is None:
                    tqdm_logger.error(f"LLM failed to generate answer in {file_name}.")
                    file_processed_successfully = False
                    self.db_manager.add_failed_file(
                        file_path, "LLM failed to generate answer"
                    )
                    continue
                current_file_qa_entries.append({"question": question, "answer": answer})
                if pbar is not None:
                    pbar.update(1)

            if file_processed_successfully and current_file_qa_entries:
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Saving")
                for entry in current_file_qa_entries:
                    self.db_manager.add_qa_sample(
                        file_path, entry["question"], entry["answer"]
                    )
                self.db_manager.save_file_hash(file_path, current_file_hash)
                self.db_manager.remove_failed_file(
                    file_path
                )  # Remove from failed list on success
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Done")
                return (True, len(current_file_qa_entries))
            else:  # No new entries or processing failed
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | No new Qs")
                return (True, 0)

        except Exception as e:
            tqdm_logger.error(f"Error processing {file_name}: {e}", exc_info=True)
            self.db_manager.add_failed_file(file_path, str(e))
            return (False, 0)
        finally:
            if pbar is not None:
                pbar.close()
