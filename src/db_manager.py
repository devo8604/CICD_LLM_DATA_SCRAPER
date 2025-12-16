"""Database manager facade that delegates to specialized components."""

import logging
from pathlib import Path

from src.state_manager import StateManager
from src.training_data_repository import TrainingDataRepository


class DBManager:
    """
    Facade for database operations.

    Delegates state management to StateManager and training data operations
    to TrainingDataRepository for better separation of concerns.
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path

        # Initialize specialized managers
        self.state_manager = StateManager(self.db_path)
        self.training_data_repo = TrainingDataRepository(self.db_path)

        logging.info(f"Connected to database: {self.db_path}")

    # State management methods (delegate to StateManager)

    def get_state(self) -> dict[str, any]:
        """Retrieve pipeline state from database."""
        return self.state_manager.get_state()

    def save_state(self, state_dict: dict[str, any]) -> None:
        """Save pipeline state to database."""
        self.state_manager.save_state(state_dict)

    # Training data methods (delegate to TrainingDataRepository)

    def add_qa_sample(
        self, file_path: str, question_text: str, answer_text: str
    ) -> int:
        """
        Add a Q&A sample to the database.

        Args:
            file_path: Source file path for the Q&A
            question_text: Question text
            answer_text: Answer text

        Returns:
            The sample_id of the created sample
        """
        return self.training_data_repo.add_qa_sample(
            file_path, question_text, answer_text
        )

    def get_processed_question_hashes(self, file_path: str) -> set[str]:
        """
        Get hashes of all processed questions for a file.

        Args:
            file_path: Path to the file

        Returns:
            Set of question hashes
        """
        return self.training_data_repo.get_processed_question_hashes(file_path)

    def get_file_hash(self, file_path: str) -> str | None:
        """
        Get stored hash for a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA256 hash of file contents, or None if not found
        """
        return self.training_data_repo.get_file_hash(file_path)

    def save_file_hash(
        self, file_path: str, content_hash: str, sample_id: int | None = None
    ) -> None:
        """
        Save file hash to database.

        Args:
            file_path: Path to the file
            content_hash: SHA256 hash of file contents
            sample_id: Optional sample_id to associate with this file
        """
        self.training_data_repo.save_file_hash(file_path, content_hash, sample_id)

    def delete_file_hash(self, file_path: str) -> None:
        """
        Delete file hash from database.

        Args:
            file_path: Path to the file
        """
        self.training_data_repo.delete_file_hash(file_path)

    def get_all_tracked_files(self) -> list[str]:
        """
        Get all tracked file paths.

        Returns:
            List of file paths
        """
        return self.training_data_repo.get_all_tracked_files()

    def delete_samples_for_file(self, file_path: str) -> None:
        """
        Delete all samples and turns for a removed file.

        Args:
            file_path: Path to the removed file
        """
        self.training_data_repo.delete_samples_for_file(file_path)

    # Failed file methods (delegate to TrainingDataRepository)

    def add_failed_file(self, file_path: str, reason: str) -> None:
        """
        Add a failed file to the database.
        Args:
            file_path: Path to the failed file
            reason: Reason for failure
        """
        self.training_data_repo.add_failed_file(file_path, reason)

    def get_failed_files(self) -> list[tuple[str, str]]:
        """
        Get all failed files from the database.
        Returns:
            List of tuples containing file_path and reason
        """
        return self.training_data_repo.get_failed_files()

    def remove_failed_file(self, file_path: str) -> None:
        """
        Remove a failed file from the database.
        Args:
            file_path: Path to the file to remove
        """
        self.training_data_repo.remove_failed_file(file_path)

    def close_db(self) -> None:
        """Close all database connections."""
        try:
            self.state_manager.close()
            self.training_data_repo.close()
            logging.info("Database connections closed.")
        except Exception as e:
            logging.error(f"Error closing database connections: {e}")
