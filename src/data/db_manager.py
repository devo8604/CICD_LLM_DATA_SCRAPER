"""Database manager facade that delegates to specialized components."""

import structlog
from pathlib import Path

from src.data.state_manager import StateManager
from src.data.training_data_repository import TrainingDataRepository

logger = structlog.get_logger(__name__)


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

        Raises:
            TypeError: If db_path is not a string or Path object
        """
        if not isinstance(db_path, (str, Path)):
            raise TypeError(
                f"db_path must be a str or Path, got {type(db_path).__name__}. "
                f"Value: {repr(db_path)}"
            )

        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path

        # Initialize specialized managers
        self.state_manager = StateManager(self.db_path)
        self.training_data_repo = TrainingDataRepository(self.db_path)

        logger.info("Connected to database", db_path=str(self.db_path))

    # State management methods (delegate to StateManager)

    def get_state(self) -> dict[str, any]:
        """Retrieve pipeline state from database."""
        return self.state_manager.get_state()

    def save_state(self, state_dict: dict[str, any]) -> None:
        """Save pipeline state to database."""
        self.state_manager.save_state(state_dict)

    # Training data methods (delegate to TrainingDataRepository)

    def add_qa_sample(self, file_path: str, question_text: str, answer_text: str) -> int:
        """Add a Q&A sample to the database."""
        return self.training_data_repo.add_qa_sample(file_path, question_text, answer_text)

    def get_processed_question_hashes(self, file_path: str) -> set[str]:
        """Get hashes of all processed questions for a file."""
        return self.training_data_repo.get_processed_question_hashes(file_path)

    def get_file_hash(self, file_path: str) -> str | None:
        """Get stored hash for a file."""
        return self.training_data_repo.get_file_hash(file_path)

    def save_file_hash(self, file_path: str, content_hash: str, sample_id: int | None = None) -> None:
        """Save file hash to database."""
        self.training_data_repo.save_file_hash(file_path, content_hash, sample_id)

    def delete_file_hash(self, file_path: str) -> None:
        """Delete file hash from database."""
        self.training_data_repo.delete_file_hash(file_path)

    def get_all_tracked_files(self) -> list[str]:
        """Get all tracked file paths."""
        return self.training_data_repo.get_all_tracked_files()

    def delete_samples_for_file(self, file_path: str) -> None:
        """Delete all samples and turns for a removed file."""
        self.training_data_repo.delete_samples_for_file(file_path)

    def get_all_training_samples(self) -> list[dict[str, any]]:
        """Retrieve all training samples and their conversation turns."""
        return self.training_data_repo.get_all_training_samples()

    # Failed file methods (delegate to TrainingDataRepository)

    def add_failed_file(self, file_path: str, reason: str) -> None:
        """Add a failed file to the database."""
        self.training_data_repo.add_failed_file(file_path, reason)

    def get_failed_files(self) -> list[tuple[str, str]]:
        """Get all failed files from the database."""
        return self.training_data_repo.get_failed_files()

    def remove_failed_file(self, file_path: str) -> None:
        """Remove a failed file from the database."""
        self.training_data_repo.remove_failed_file(file_path)

    def close_db(self) -> None:
        """Close all database connections."""
        try:
            self.state_manager.close()
            self.training_data_repo.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error("Error closing database connections", error=str(e))