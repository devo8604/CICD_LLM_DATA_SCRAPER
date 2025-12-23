"""Service layer for file processing operations."""

import hashlib
import os
from contextlib import contextmanager

import structlog
from tqdm import tqdm

from src.core.config import AppConfig
from src.core.error_handling import TimeoutManager
from src.core.utils import calculate_dynamic_timeout
from src.data.db_manager import DBManager
from src.llm.llm_client import LLMClient

# Get logger for this module
logger = structlog.get_logger(__name__)


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
        self._processed_count = 0

    def calculate_file_hash(self, file_path: str) -> str | None:
        """Calculates the SHA256 hash of a file's content."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read the file in chunks to handle large files efficiently
                # Use chunk size from config for better performance tuning
                for chunk in iter(lambda: f.read(self.config.model.processing.chunk_read_size), b""):
                    hasher.update(chunk)
        except OSError as e:
            logger.error("OS error calculating hash", file_path=file_path, error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error calculating hash", file_path=file_path, error=str(e))
            return None
        return hasher.hexdigest()

    @contextmanager
    def _process_file_context(self, file_path: str, pbar: tqdm | None = None):
        """Context manager for file processing to handle resources properly."""
        try:
            yield
        except KeyboardInterrupt:
            logger.warning("Processing cancelled for file", file_path=file_path)
            raise
        except Exception as e:
            logger.error("Unexpected error during file processing", file_path=file_path, error=str(e), exc_info=True)
            raise
        finally:
            # Clear MLX memory periodically (every 10 files) to balance performance and memory usage
            if self.config.model.use_mlx and hasattr(self.llm_client, "clear_mlx_memory"):
                self._processed_count += 1
                if self._processed_count % 10 == 0:
                    try:
                        self.llm_client.clear_mlx_memory()
                    except Exception as e:
                        logger.warning("Failed to clear MLX memory", error=str(e))

    def _read_file_content(self, file_path: str) -> str | None:
        """Synchronously read file content with encoding detection."""

        # List of encodings to try in order of preference
        encodings_to_try = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings_to_try:
            try:
                with open(file_path, encoding=encoding) as f:
                    content = f.read()
                    logger.debug(f"Successfully read file with {encoding} encoding", file_path=file_path)
                    return content
            except UnicodeDecodeError:
                continue  # Try next encoding
            except FileNotFoundError:
                logger.error("File not found", file_path=file_path)
                return None
            except PermissionError:
                logger.error("Permission denied reading file", file_path=file_path)
                return None
            except OSError as e:
                logger.error("OS error reading file", file_path=file_path, error=str(e))
                return None

        # If all encodings fail, try with utf-8 and errors='replace'
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                logger.warning("Read file with replacement characters due to encoding issues", file_path=file_path)
                return content
        except Exception as e:
            logger.warning("Failed to read file", file_path=file_path, error=str(e))
            return None

    def process_single_file(self, file_path: str, repo_name: str, pbar: tqdm | None = None, cancellation_event=None) -> tuple[bool, int]:
        """
        Process a single file: check hash, generate Q&A, save to DB.

        Returns:
            tuple: (success: bool, qa_pairs_generated: int)
        """
        # Check for cancellation at the start
        if cancellation_event and cancellation_event.is_set():
            logger.info("File processing cancelled immediately.")
            return (False, 0)

        # Process with retry logic for robustness
        max_retries = self.config.model.llm.max_retries if hasattr(self.config, "LLM_MAX_RETRIES") else 3

        for attempt in range(max_retries):
            try:
                # Check cancellation before retry attempts
                if cancellation_event and cancellation_event.is_set():
                    logger.info("File processing cancelled before retry.")
                    return (False, 0)

                result = self._process_single_file_impl(file_path, repo_name, pbar, cancellation_event)
                return result
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error("Failed to process file after multiple attempts", file_path=file_path, max_retries=max_retries, error=str(e))
                    self.db_manager.add_failed_file(
                        file_path,
                        f"Processing error after {max_retries} retries: {str(e)}",
                    )
                    return (False, 0)
                else:
                    logger.warning("Attempt failed for file, retrying...", attempt=attempt + 1, file_path=file_path, error=str(e))
                    # Exponential backoff with jitter: 1s, 2s, 4s + random jitter
                    import random
                    import time

                    backoff_time = min(2**attempt + random.uniform(0, 1), 10)  # Cap at 10 seconds
                    time.sleep(backoff_time)

    def _process_single_file_impl(self, file_path: str, repo_name: str, pbar: tqdm | None = None, cancellation_event=None) -> tuple[bool, int]:
        """
        Implementation for processing a single file: check hash, generate Q&A, save to DB.

        Returns:
            tuple: (success: bool, qa_pairs_generated: int)
        """
        with self._process_file_context(file_path, pbar):
            # Check cancellation
            if cancellation_event and cancellation_event.is_set():
                return (False, 0)

            file_name = os.path.basename(file_path)

            if pbar is not None:
                pbar.set_description(f"File: {file_name[:64]:<64} | Hashing")

            # Skip if not a regular file (e.g., a FIFO or socket)
            if not os.path.isfile(file_path):
                logger.warning("Skipping non-regular file", file_name=file_name, repo_name=repo_name)
                if pbar is not None:
                    pbar.update(100)
                return (True, 0)

            # Calculate current hash and check against stored hash
            current_file_hash = self.calculate_file_hash(file_path)
            if current_file_hash is None:
                logger.error("Could not calculate hash, skipping", file_path=file_path)
                return (False, 0)

            stored_file_hash = self.db_manager.get_file_hash(file_path)

            if stored_file_hash == current_file_hash:
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Unchanged")
                    pbar.update(100)
                else:  # Fallback for when no pbar is passed
                    logger.info("File is unchanged, skipping", file_name=file_name)
                return (True, 0)
            elif stored_file_hash is not None:
                logger.info("File has been updated, reprocessing", file_name=file_name)

            file_processed_successfully = True
            current_file_qa_entries: list[dict[str, str]] = []

            if pbar is not None:
                pbar.set_description(f"File: {file_name[:64]:<64} | Reading")

            # Read file content with timeout protection
            content = self._read_file_content(file_path)
            if content is None:
                self.db_manager.add_failed_file(file_path, "Failed to read file content")
                return (False, 0)

            if not content.strip():
                logger.info("Skipping empty file", file_name=file_name)
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Empty")
                    pbar.update(100)
                return (True, 0)

            if pbar is not None:
                pbar.set_description(f"File: {file_name[:64]:<64} | Gen Qs")

            # Update progress tracker
            try:
                from src.ui.progress_tracker import get_progress_tracker

                tracker = get_progress_tracker()
                file_size = os.path.getsize(file_path)
                tracker.update_current_file_with_size(file_path, file_size)
                tracker.update_file_progress(10.0)
            except Exception:
                pass

            # Generate questions with retry logic
            if cancellation_event and cancellation_event.is_set():
                logger.info("Cancelled before question generation")
                return (False, 0)

            all_questions_for_file = None
            max_question_retries = self.config.model.llm.max_retries if hasattr(self.config, "LLM_MAX_RETRIES") else 3

            for question_attempt in range(max_question_retries):
                try:
                    logger.info("Attempting to generate questions", file_name=file_name, attempt=question_attempt + 1)

                    # Calculate dynamic timeout based on file size
                    timeout_seconds = calculate_dynamic_timeout(file_path)

                    if hasattr(self.llm_client, "context_window"):  # MLXClient
                        all_questions_for_file = TimeoutManager.run_with_timeout_sync(
                            self.llm_client.generate_questions,
                            timeout_seconds,
                            content,
                            self.config.model.generation.default_temperature,
                            self.config.model.generation.default_max_tokens,
                            pbar,
                        )
                    else:
                        all_questions_for_file = TimeoutManager.run_with_timeout_sync(
                            self.llm_client.generate_questions,
                            timeout_seconds,
                            content,
                            self.config.model.generation.default_temperature,
                            self.config.model.generation.default_max_tokens,
                            pbar,
                        )

                    if all_questions_for_file:
                        logger.info("Successfully generated questions", file_name=file_name, count=len(all_questions_for_file))
                    else:
                        logger.warning("Generated 0 questions", file_name=file_name)
                    break
                except Exception as e:
                    # Handle various types of exceptions including connection issues
                    import socket

                    import httpx

                    if isinstance(e, httpx.TimeoutException | socket.timeout):
                        logger.warning("Request timeout generating questions", file_name=file_name, attempt=question_attempt + 1)
                    elif isinstance(e, httpx.ConnectError | httpx.NetworkError | socket.gaierror | ConnectionError):
                        logger.warning("Connection error generating questions", file_name=file_name, attempt=question_attempt + 1)
                        # Optionally reset connection if supported by the client
                        if hasattr(self.llm_client, "reset_connection"):
                            try:
                                self.llm_client.reset_connection()
                            except Exception:
                                logger.warning("Failed to reset connection", file_name=file_name)
                    elif isinstance(e, httpx.HTTPStatusError):
                        logger.warning(f"HTTP error {e.response.status_code} generating questions", file_name=file_name, attempt=question_attempt + 1)
                    else:
                        logger.warning("Error generating questions", file_name=file_name, attempt=question_attempt + 1, error=str(e))

                    if question_attempt == max_question_retries - 1:
                        logger.error("Error generating questions after maximum attempts", file_name=file_name, max_attempts=max_question_retries, error=str(e))
                        self.db_manager.add_failed_file(file_path, f"Question generation error after {max_question_retries} attempts: {str(e)}")
                        return (False, 0)
                    else:
                        logger.warning("Question generation error, retrying...", attempt=question_attempt + 1, error=str(e))
                        import random
                        import time

                        time.sleep(min(2**question_attempt + random.uniform(0, 1), 5))

            if all_questions_for_file is None:
                logger.error("LLM failed to generate questions", file_name=file_name)
                self.db_manager.add_failed_file(file_path, "LLM failed to generate questions after retries")
                return (False, 0)

            self.llm_client.clear_context()
            processed_hashes = self.db_manager.get_processed_question_hashes(file_path)
            unanswered_questions = [q for q in all_questions_for_file if hashlib.sha256(q.encode("utf-8")).hexdigest() not in processed_hashes]

            logger.debug("New questions to process", file_name=file_name, count=len(unanswered_questions))

            if pbar is not None:
                pbar.total = len(unanswered_questions)
                pbar.refresh()

            # Process questions
            for i, question in enumerate(unanswered_questions):
                if cancellation_event and cancellation_event.is_set():
                    logger.info("Cancelled during answer generation loop")
                    return (False, 0)

                # Update progress
                if len(unanswered_questions) > 0:
                    file_progress = ((i + 1) / len(unanswered_questions)) * 100
                    try:
                        from src.ui.progress_tracker import get_progress_tracker

                        tracker = get_progress_tracker()
                        tracker.update_file_progress(file_progress)
                    except Exception:
                        pass

                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Ans Q {i + 1}/{len(unanswered_questions)}")

                # Get answer
                answer = None
                max_answer_retries = self.config.model.llm.max_retries if hasattr(self.config, "LLM_MAX_RETRIES") else 3
                answer_success = False

                for answer_attempt in range(max_answer_retries):
                    try:
                        # Use dynamic timeout for answers too
                        timeout_seconds = calculate_dynamic_timeout(file_path)

                        answer = TimeoutManager.run_with_timeout_sync(
                            self.llm_client.get_answer_single,
                            timeout_seconds,
                            question,
                            content,
                            self.config.model.generation.default_temperature,
                            self.config.model.generation.default_max_tokens,
                            pbar,
                        )
                        answer_success = True
                        break
                    except Exception as e:
                        # Handle various types of exceptions including connection issues
                        import socket

                        import httpx

                        if isinstance(e, httpx.TimeoutException | socket.timeout):
                            logger.warning("Request timeout getting answer", file_name=file_name, attempt=answer_attempt + 1)
                        elif isinstance(e, httpx.ConnectError | httpx.NetworkError | socket.gaierror | ConnectionError):
                            logger.warning("Connection error getting answer, may need to reset connection", file_name=file_name, attempt=answer_attempt + 1)
                            # Optionally reset connection if supported by the client
                            if hasattr(self.llm_client, "reset_connection"):
                                try:
                                    self.llm_client.reset_connection()
                                except Exception:
                                    logger.warning("Failed to reset connection", file_name=file_name)
                        elif isinstance(e, httpx.HTTPStatusError):
                            logger.warning(f"HTTP error {e.response.status_code} getting answer", file_name=file_name, attempt=answer_attempt + 1)
                        else:
                            logger.warning("Error getting answer", file_name=file_name, attempt=answer_attempt + 1, error=str(e))

                        if answer_attempt == max_answer_retries - 1:
                            logger.error("Error getting answer after maximum attempts", file_name=file_name, attempt=i + 1, error=str(e))
                        else:
                            logger.warning("Answer generation error, retrying...", attempt=answer_attempt + 1, error=str(e))
                            import random
                            import time

                            time.sleep(min(2**answer_attempt + random.uniform(0, 1), 5))

                if not answer_success or answer is None:
                    logger.error("LLM failed to generate answer", file_name=file_name, question_index=i + 1)
                    file_processed_successfully = False
                    continue

                current_file_qa_entries.append({"question": question, "answer": answer})
                if pbar is not None:
                    pbar.update(1)

            # Batch save QA samples
            if file_processed_successfully and current_file_qa_entries:
                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Saving")

                qa_pairs = [(entry["question"], entry["answer"]) for entry in current_file_qa_entries]
                self.db_manager.training_data_repo.add_qa_samples_batch(file_path, qa_pairs)
                logger.info("Batch inserted QA samples", file_name=file_name, count=len(qa_pairs))

                self.db_manager.save_file_hash(file_path, current_file_hash)
                self.db_manager.remove_failed_file(file_path)

                try:
                    from src.ui.progress_tracker import get_progress_tracker

                    tracker = get_progress_tracker()
                    tracker.update_file_progress(100.0)
                except Exception:
                    pass

                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | Done")
                return (True, len(current_file_qa_entries))
            else:
                self.db_manager.save_file_hash(file_path, current_file_hash)
                self.db_manager.remove_failed_file(file_path)

                try:
                    from src.ui.progress_tracker import get_progress_tracker

                    tracker = get_progress_tracker()
                    tracker.update_file_progress(100.0)
                except Exception:
                    pass

                if pbar is not None:
                    pbar.set_description(f"File: {file_name[:64]:<64} | No new Qs")
                return (True, 0)

        if pbar is not None:
            pbar.update(1)
